"""Isolated Colab GPU setup and real inference, independent of the web/database app.

Dry runs use only the standard library and never install or run a model. Real
runs retain failure diagnostics; a generated candidate still needs visual review.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSE_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/1/pose_landmarker_full.task"
)
POSE_SHA256 = "5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1"
UV_VERSION = "0.13.0"
SUPPORTED_PYTHON = {(3, 11), (3, 12)}
PACKAGES = (
    "torch", "torchvision", "numpy", "mediapipe", "transformers", "diffusers",
    "accelerate", "huggingface-hub", "safetensors", "opencv-contrib-python",
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def env_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def isolated_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.update({
        "PYTHONNOUSERSITE": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "HF_HOME": str(ROOT / ".runtime/huggingface"),
        "UV_CACHE_DIR": str(ROOT / ".runtime/colab-tools/cache"),
        "UV_PYTHON_INSTALL_DIR": str(ROOT / ".runtime/colab-tools/python"),
        "UV_PYTHON_BIN_DIR": str(ROOT / ".runtime/colab-tools/bin"),
        "UV_PYTHON_INSTALL_BIN": "0",
        "UV_LINK_MODE": "copy",
        "MPLCONFIGDIR": str(ROOT / ".runtime/matplotlib"),
        "MPLBACKEND": "Agg",
    })
    # A notebook's injected PYTHONPATH must not defeat venv isolation.
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def setup_commands(venv: Path) -> list[list[str]]:
    python = str(env_python(venv))
    return [
        [python, "-m", "pip", "install", "--index-url", "https://download.pytorch.org/whl/cu121",
         "torch==2.5.1+cu121", "torchvision==0.20.1+cu121"],
        [python, "-m", "pip", "install", "-r", str(ROOT / "requirements-colab.txt")],
        [python, "-m", "pip", "check"],
        [python, str(ROOT / "scripts/colab_runtime.py"), "_probe"],
        [python, str(ROOT / "scripts/download_vton.py")],
        [python, str(ROOT / "scripts/download_vton_mix.py")],
        [python, str(ROOT / "scripts/download_parser.py")],
        [python, str(ROOT / "scripts/colab_runtime.py"), "_download-pose"],
    ]


def create_environment(venv: Path, env: dict[str, str]) -> None:
    if venv.resolve() == Path(sys.prefix).resolve():
        raise RuntimeError("Refusing to modify the current notebook/global Python environment.")
    if venv.exists():
        if not (venv / "pyvenv.cfg").is_file() and any(venv.iterdir()):
            raise RuntimeError("The requested environment directory contains unrelated files.")
        if env_python(venv).is_file():
            version = subprocess.check_output(
                [str(env_python(venv)), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
                env=env, text=True,
            ).strip()
            if version not in {"3.11", "3.12"}:
                raise RuntimeError(f"Existing inference environment uses unsupported Python {version}.")
            return
    if sys.version_info[:2] in SUPPORTED_PYTHON:
        subprocess.run([sys.executable, "-m", "venv", str(venv)], env=env, check=True)
    else:
        # Colab can change its notebook interpreter. uv obtains a managed 3.12
        # interpreter under this project; the notebook interpreter stays intact.
        tools = ROOT / ".runtime/colab-tools/packages"
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(tools),
             f"uv=={UV_VERSION}"], env=env, check=True,
        )
        uv_env = {**env, "PYTHONPATH": str(tools)}
        subprocess.run(
            [sys.executable, "-m", "uv", "venv", "--python", "3.12",
             "--python-preference", "only-managed", "--seed", str(venv)],
            env=uv_env, check=True,
        )


def runtime_probe() -> dict:
    if sys.version_info[:2] not in SUPPORTED_PYTHON:
        raise RuntimeError("Inference requires the isolated Python 3.11 or 3.12 environment.")
    import torch

    if torch.__version__ != "2.5.1+cu121":
        raise RuntimeError(f"Expected torch 2.5.1+cu121; found {torch.__version__}.")
    if not torch.cuda.is_available():
        raise RuntimeError(
            "No CUDA GPU is available to this runtime. Select a Colab GPU runtime and rerun setup; "
            "the runner does not silently substitute CPU inference or an image overlay."
        )
    gpu = torch.cuda.get_device_properties(0)
    free, total = torch.cuda.mem_get_info(0)
    # Exercise CUDA rather than trusting only driver/device enumeration.
    if not bool(torch.isfinite(torch.ones(4, device="cuda") * 2).all()):
        raise RuntimeError("CUDA numerical smoke test failed.")
    warnings = []
    if total < 8 * 1024**3:
        warnings.append("At least 8 GiB GPU memory is recommended for native-resolution inference.")
    return {
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in PACKAGES},
        "gpu": {"name": gpu.name, "totalGiB": round(total / 1024**3, 2),
                "freeGiB": round(free / 1024**3, 2), "cudaVersion": torch.version.cuda},
        "warnings": warnings,
    }


def download_pose() -> None:
    import requests
    from download_vton import fetch

    destination = ROOT / "assets/bodyModels/pose_landmarker_full.task"
    with requests.Session() as session:
        record = fetch(session, POSE_URL, destination, expected=POSE_SHA256)
    write_json(destination.parent / "pose-download-manifest.json", record)


def setup(args: argparse.Namespace) -> int:
    venv = args.venv.resolve()
    commands = setup_commands(venv)
    if args.dry_run:
        print(json.dumps({"status": "dry-run", "venv": str(venv), "commands": commands,
                          "pythonBootstrap": "venv with Python 3.11/3.12, otherwise workspace uv-managed 3.12"}, indent=2))
        return 0
    if platform.system() != "Linux":
        raise RuntimeError("The Colab setup profile targets Linux. The local Windows environment is unchanged.")
    env = isolated_environment()
    if args.check_only:
        subprocess.run([str(env_python(venv)), str(Path(__file__).resolve()), "_probe"],
                       cwd=ROOT, env=env, check=True)
        return 0
    report = {"status": "running", "startedAt": datetime.now(timezone.utc).isoformat(),
              "venv": str(venv), "completedCommands": []}
    report_path = ROOT / "experiments/colab-setup-report.json"
    write_json(report_path, report)
    try:
        create_environment(venv, env)
        for command in commands:
            subprocess.run(command, cwd=ROOT, env=env, check=True)
            report["completedCommands"].append(command)
            write_json(report_path, report)
        frozen = subprocess.check_output(
            [str(env_python(venv)), "-m", "pip", "freeze"], cwd=ROOT, env=env, text=True,
        )
        (ROOT / "experiments/colab-resolved-requirements.txt").write_text(frozen, encoding="utf-8")
        report["status"] = "installed"
    except Exception as exc:
        report.update(status="failed", error=str(exc), traceback=traceback.format_exc())
        raise
    finally:
        write_json(report_path, report)
    return 0


def run_plan(args: argparse.Namespace) -> dict:
    checkpoint = getattr(args, "checkpoint", "mix")
    height = getattr(args, "height", 1024)
    return {"model": "CatVTON", "checkpoint": "mix-48k-1024" if checkpoint == "mix" else "vitonhd-16k-512", "nativeResolution": [height * 3 // 4, height],
            "inferenceSteps": 50, "guidanceScale": args.guidance, "seed": args.seed,
            "person": str(args.person.resolve()), "garment": str(args.garment.resolve()),
            "category": args.category, "outputDirectory": str(args.output.resolve()),
            "visualAcceptance": "not evaluated"}


def run(args: argparse.Namespace) -> int:
    plan = run_plan(args)
    if args.dry_run:
        print(json.dumps({"status": "dry-run", **plan}, indent=2))
        return 0
    # Colab exports its inline notebook backend to child processes. The
    # isolated inference environment deliberately has no notebook UI packages;
    # MediaPipe imports pyplot even though this pipeline never displays plots.
    os.environ["MPLBACKEND"] = "Agg"
    output = args.output.resolve()
    if args.check_only:
        state = runtime_probe()
        for path in (args.person, args.garment):
            if not path.is_file():
                raise FileNotFoundError(path)
        sys.path.insert(0, str(ROOT))
        from ml.vton.service import PretrainedTryOn
        availability = PretrainedTryOn(ROOT / "assets/vton", checkpoint=args.checkpoint, height=args.height).availability()
        print(json.dumps({"status": "checked", "runtime": state, "availability": availability}))
        return 0 if availability["available"] else 1
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("Output directory is not empty. Choose a new run directory to avoid stale results.")
    output.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "startedAt": datetime.now(timezone.utc).isoformat(), **plan}
    write_json(output / "report.json", report)
    start = time.perf_counter()
    try:
        report["runtime"] = runtime_probe()
        import torch

        torch.cuda.reset_peak_memory_stats()
        person_data, garment_data = args.person.read_bytes(), args.garment.read_bytes()
        report["inputSha256"] = {"person": hashlib.sha256(person_data).hexdigest(),
                                  "garment": hashlib.sha256(garment_data).hexdigest()}
        (output / "personInput.bin").write_bytes(person_data)
        (output / "garmentInput.bin").write_bytes(garment_data)
        sys.path.insert(0, str(ROOT))
        from ml.preprocessing.images import PersonPreprocessor
        from ml.vton.service import PretrainedTryOn

        processor = PersonPreprocessor(ROOT / "assets/bodyModels/pose_landmarker_full.task")
        service = PretrainedTryOn(ROOT / "assets/vton", "cuda", checkpoint=args.checkpoint, height=args.height,
                                   guidance_scale=args.guidance, seed=args.seed)
        features = processor.detect(person_data, output)
        diagnostics = service.render(features, garment_data, args.category, output)
        if not (output / "tryon-2d.png").is_file():
            raise RuntimeError("Inference returned without writing the final image.")
        report.update(status="generated", diagnostics=diagnostics,
                      visualAcceptance="pending visual review", qualityValidated=False)
        report["peakGpuAllocatedMiB"] = round(torch.cuda.max_memory_allocated() / 1024**2, 1)
    except Exception as exc:
        report.update(status="failed", code=getattr(exc, "code", type(exc).__name__),
                      error=str(exc), visualAcceptance="not accepted")
        (output / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        # The service retains native predictions and fidelity diagnostics on rejection.
        # No placeholder image or geometry overlay is created here.
    finally:
        report["seconds"] = round(time.perf_counter() - start, 3)
        report["artifacts"] = {str(path.relative_to(output)): {"bytes": path.stat().st_size,
                                  "sha256": sha256(path)} for path in sorted(output.rglob("*"))
                               if path.is_file() and path.name != "report.json"}
        write_json(output / "report.json", report)
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report["status"] == "generated" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("setup")
    install.add_argument("--venv", type=Path, default=ROOT / ".venv-colab")
    infer = commands.add_parser("run")
    infer.add_argument("--person", type=Path, required=True)
    infer.add_argument("--garment", type=Path, required=True)
    infer.add_argument("--category", choices=["t-shirt", "shirt"], default="t-shirt")
    infer.add_argument("--output", type=Path, required=True)
    infer.add_argument("--guidance", type=float, default=2.5)
    infer.add_argument("--seed", type=int, default=42)
    infer.add_argument("--checkpoint", choices=["mix", "vitonhd"], default="mix")
    infer.add_argument("--height", type=int, choices=[512, 1024], default=1024)
    for command in (install, infer):
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--check-only", action="store_true")
    commands.add_parser("_probe", help=argparse.SUPPRESS)
    commands.add_parser("_download-pose", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.command == "setup":
        return setup(args)
    if args.command == "run":
        return run(args)
    if args.command == "_probe":
        print(json.dumps(runtime_probe(), indent=2))
    else:
        download_pose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

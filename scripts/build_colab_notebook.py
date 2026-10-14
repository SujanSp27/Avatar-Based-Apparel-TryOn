"""Package the audited 2D inference source into a self-contained Colab notebook.

This is an explicit file allowlist, not a repository upload. Model weights,
private uploaded photos, database files, credentials and environments never
enter the archive. Re-run after changing an included inference source file.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import stat
import textwrap
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_LIMIT = 12 * 1024 * 1024
SOURCE_FILES = (
    "ml/__init__.py",
    "ml/errors.py",
    "ml/progress.py",
    "ml/preprocessing/__init__.py",
    "ml/preprocessing/images.py",
    "ml/vton/__init__.py",
    "ml/vton/attention.py",
    "ml/vton/catvton.py",
    "ml/vton/conditioning.py",
    "ml/vton/masking.py",
    "ml/vton/parsing.py",
    "ml/vton/precision.py",
    "ml/vton/quality.py",
    "ml/vton/runtime.py",
    "ml/vton/service.py",
    "ml/vton/vendor/catvton/__init__.py",
    "ml/vton/vendor/catvton/LICENSE",
    "ml/vton/vendor/catvton/UPSTREAM.md",
    "ml/vton/vendor/catvton/utils.py",
    "ml/vton/vendor/catvton/model/__init__.py",
    "ml/vton/vendor/catvton/model/attn_processor.py",
    "ml/vton/vendor/catvton/model/pipeline.py",
    "ml/vton/vendor/catvton/model/utils.py",
    "ml/vton/vendor/fashn_human_parser/__init__.py",
    "ml/vton/vendor/fashn_human_parser/LICENSE",
    "ml/vton/vendor/fashn_human_parser/UPSTREAM.md",
    "ml/vton/vendor/fashn_human_parser/labels.py",
    "ml/vton/vendor/fashn_human_parser/parser.py",
    "scripts/download_vton.py",
    "scripts/download_vton_mix.py",
    "scripts/download_parser.py",
    "scripts/colab_runtime.py",
    "requirements-colab.txt",
    "data/raw/studio-person.jpg",
    "data/raw/garment-demo.png",
    "data/raw/vton-official/person-model-5.png",
    "data/raw/vton-official/garment-number-95.jpg",
    "data/raw/vton-official/garment-rhude.jpg",
    "data/raw/vton-official/manifest.json",
)
FIXTURE_SHA256 = {
    "data/raw/studio-person.jpg": "1d450d545f08a2945217f76908d229c14381cd59bb3b8c936c1c0e1a938bad8f",
    "data/raw/garment-demo.png": "28b6ff594200c1264146b10fab679b4343ae0ee520083e5b3389816963e67535",
    "data/raw/vton-official/person-model-5.png": "5faaea84635da215bd0819cf5ce65512ca1b742c39ee8fd67176b19e084ed872",
    "data/raw/vton-official/garment-number-95.jpg": "332036128caffe010e377f7ecb1852791804c53ebc4865d377339b9762c6689f",
    "data/raw/vton-official/garment-rhude.jpg": "3929f83104c547bcf4a74985999438c05f887d97445c700029414466680eeee3",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or "\\" in name
        or ":" in name
        or any(part in {"", ".", ".."} for part in name.split("/"))
        or name != path.as_posix()
    ):
        raise ValueError(f"Unsafe archive path: {name!r}")


def source_archive(root: Path = ROOT) -> tuple[bytes, dict]:
    root = root.resolve()
    content = {}
    for name in SOURCE_FILES:
        validate_member_name(name)
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Source must be a regular file inside the project: {name}")
        data = path.read_bytes()
        expected = FIXTURE_SHA256.get(name)
        if expected and sha256(data) != expected:
            raise ValueError(f"Regression fixture changed: {name}")
        content[name] = data
    manifest = {
        "formatVersion": 1,
        "scope": "Explicit inference source and five research regression images only.",
        "excluded": [
            ".env", "credentials", "data/processed", "private uploads", "backend",
            "database", "checkpoints", ".venv", "node_modules",
        ],
        "fixturePurpose": "Unpaired visual regression; not training data or ground truth.",
        "files": {
            name: {"sha256": sha256(data), "bytes": len(data)}
            for name, data in sorted(content.items())
        },
    }
    content["SOURCE_MANIFEST.json"] = json.dumps(manifest, sort_keys=True, indent=2).encode()
    if sum(map(len, content.values())) > ARCHIVE_LIMIT:
        raise ValueError("Source archive exceeds the explicit small-source size limit")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(content.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    return buffer.getvalue(), manifest


# The same extraction implementation is embedded and tested locally. It needs
# only stdlib; the notebook does not execute unverified archive code to unpack it.
EXTRACTOR = '''
def extract_verified_source(payload, expected_sha256, destination):
    import hashlib
    import io
    import json
    import stat
    import zipfile
    from pathlib import Path, PurePosixPath

    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("Embedded archive checksum mismatch")
    destination = Path(destination).resolve()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or len(entries) > 100:
            raise ValueError("Duplicate or excessive archive entries")
        if sum(entry.file_size for entry in entries) > 12 * 1024 * 1024:
            raise ValueError("Expanded archive is unexpectedly large")
        for entry in entries:
            name = entry.orig_filename
            path = PurePosixPath(name)
            mode = entry.external_attr >> 16
            if (not name or path.is_absolute() or "\\\\" in name or ":" in name
                    or any(part in {"", ".", ".."} for part in name.split("/"))
                    or name != path.as_posix() or entry.is_dir()
                    or (mode and not stat.S_ISREG(mode))):
                raise ValueError(f"Unsafe archive member: {name!r}")
            target = destination / name
            if target.is_symlink() or not target.resolve().is_relative_to(destination):
                raise ValueError(f"Unsafe extraction destination: {name!r}")
        manifest = json.loads(archive.read("SOURCE_MANIFEST.json"))
        expected_names = set(manifest["files"]) | {"SOURCE_MANIFEST.json"}
        if set(names) != expected_names:
            raise ValueError("Archive contents disagree with source manifest")
        verified = {}
        for name, expected in manifest["files"].items():
            data = archive.read(name)
            if (len(data) != expected["bytes"]
                    or hashlib.sha256(data).hexdigest() != expected["sha256"]):
                raise ValueError(f"Source checksum mismatch: {name}")
            verified[name] = data
        verified["SOURCE_MANIFEST.json"] = archive.read("SOURCE_MANIFEST.json")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in verified.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return manifest
'''.strip()


def cell(kind: str, identifier: str, source: str) -> dict:
    item = {
        "cell_type": kind, "id": identifier, "metadata": {},
        "source": textwrap.dedent(source).strip().splitlines(keepends=True),
    }
    if kind == "code":
        item.update(execution_count=None, outputs=[])
    return item


def make_notebook(payload: bytes) -> dict:
    digest = sha256(payload)
    encoded = base64.b64encode(payload).decode("ascii")
    bootstrap = (
        "import base64\nfrom pathlib import Path\n\n" + EXTRACTOR
        + f'\n\nSOURCE_SHA256 = "{digest}"\n'
        + f'EMBEDDED_SOURCE = "{encoded}"\n'
        + 'PROJECT = Path("/content") / ("avatar-vton-" + SOURCE_SHA256[:12])\n'
        + "SOURCE_MANIFEST = extract_verified_source(\n"
        + "    base64.b64decode(EMBEDDED_SOURCE, validate=True), SOURCE_SHA256, PROJECT\n)\n"
        + "del EMBEDDED_SOURCE\n"
        + 'print(f"Verified {len(SOURCE_MANIFEST[\'files\'])} source files in {PROJECT}")\n'
    )
    cells = [
        cell("markdown", "purpose", """
            # GPU virtual try-on: real person, real uploaded garment

            This notebook contains the current project inference source and exact retained
            striped-shirt regression images. It uses the pinned pretrained **CatVTON
            mix-48k-1024** checkpoint at **768 × 1024**, 50 steps, guidance 2.5, seed 42,
            with the FASHN human parser and identity-preserving composition.

            The earlier local output lost the stripes and was rejected. More GPU memory
            permits the larger checkpoint and resolution; it does **not** establish
            image quality. Every generated image below requires visual inspection.
            A rejected model output is shown only as a labeled diagnostic, never a success.
            No pasted-garment fallback is used. The independent brand size engine remains
            in the application; this inference notebook does not invent body measurements
            or sizes.

            Use a GPU runtime. The supplied cells install into a separate Python
            environment without replacing Colab's preinstalled packages. The notebook
            contains no credentials, private upload directory, database, or model weights.
            It downloads pinned model assets from their official hosts. Google Drive is
            not accessed unless the optional persistence cell is explicitly enabled.

            Research use only: bundled upstream code/models retain their own licenses
            (including CatVTON CC-BY-NC-SA-4.0 and the FASHN parser's license).
            The five example photos are unpaired evaluation fixtures, **not** a valid
            training/fine-tuning dataset. No training is launched by this notebook.
        """),
        cell("code", "verified-source", bootstrap),
        cell("code", "isolated-setup", """
            import json
            import platform
            import subprocess
            import sys

            print("Notebook Python:", platform.python_version())
            if platform.system() != "Linux":
                raise RuntimeError("This notebook targets a Linux Colab GPU runtime.")
            VENV = PROJECT / ".venv-colab"
            subprocess.run([
                sys.executable, str(PROJECT / "scripts/colab_runtime.py"),
                "setup", "--venv", str(VENV),
            ], cwd=PROJECT, check=True)
            PYTHON = VENV / "bin/python"
            if not PYTHON.is_file():
                raise RuntimeError("The isolated inference environment was not created.")
            print("Inference environment:", PYTHON)
        """),
        cell("markdown", "evaluation-scope", """
            ## Evaluate the actual inputs sequentially

            Four separate processes test the reported striped garment, another garment,
            another person, and the supported shirt category. Processes run sequentially
            to release GPU memory between cases. Dresses and trousers remain unsupported
            by this project's 2D adapter. Inputs and every saved intermediate stay under
            this notebook's `/content/avatar-vton-...` directory.

            Each input checksum is checked against the embedded source manifest. A model
            error or quality rejection is retained in the report and does not turn into
            an overlay. A completed inference is still **pending visual review**.
        """),
        cell("code", "run-regressions", """
            import hashlib
            import time
            from datetime import datetime, timezone

            RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            RUNS = PROJECT / "experiments/colab-runs" / RUN_ID
            RUNS.mkdir(parents=True, exist_ok=True)
            CASES = [
                ("reported-striped-shirt", "data/raw/studio-person.jpg",
                 "data/raw/garment-demo.png", "t-shirt"),
                ("different-garment", "data/raw/studio-person.jpg",
                 "data/raw/vton-official/garment-number-95.jpg", "t-shirt"),
                ("different-person", "data/raw/vton-official/person-model-5.png",
                 "data/raw/vton-official/garment-rhude.jpg", "t-shirt"),
                ("shirt-category", "data/raw/studio-person.jpg",
                 "data/raw/vton-official/garment-rhude.jpg", "shirt"),
            ]
            CASE_RECORDS = []
            for name, person, garment, category in CASES:
                for relative in (person, garment):
                    actual = hashlib.sha256((PROJECT / relative).read_bytes()).hexdigest()
                    if actual != SOURCE_MANIFEST["files"][relative]["sha256"]:
                        raise RuntimeError(f"Fixture checksum changed: {relative}")
                destination = RUNS / name
                print(f"\\nRunning {name}: {category}", flush=True)
                start = time.monotonic()
                completed = subprocess.run([
                    str(PYTHON), str(PROJECT / "scripts/colab_runtime.py"), "run",
                    "--person", str(PROJECT / person),
                    "--garment", str(PROJECT / garment),
                    "--category", category, "--output", str(destination),
                ], cwd=PROJECT, check=False)
                record = {
                    "case": name, "person": person, "garment": garment,
                    "category": category, "returnCode": completed.returncode,
                    "seconds": round(time.monotonic() - start, 3),
                    "visualAcceptance": "pending visual review",
                }
                CASE_RECORDS.append(record)
                (RUNS / "notebook-cases.json").write_text(
                    json.dumps({"sourceSha256": SOURCE_SHA256, "cases": CASE_RECORDS}, indent=2),
                    encoding="utf-8",
                )
                print(json.dumps(record), flush=True)
        """),
        cell("code", "inspect-results", """
            from IPython.display import Markdown, display
            from PIL import Image

            def show_image(path, caption):
                display(Markdown(caption))
                with Image.open(path) as original:
                    preview = original.convert("RGB")
                    preview.thumbnail((768, 1024))
                    display(preview)

            for record in CASE_RECORDS:
                name = record["case"]
                destination = RUNS / name
                display(Markdown(f"### {name}"))
                show_image(PROJECT / record["person"], "**Original person**")
                show_image(PROJECT / record["garment"], "**Actual garment conditioning image**")
                report_path = destination / "report.json"
                if report_path.is_file():
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    print(json.dumps(report, indent=2))
                output = destination / "tryon-2d.png"
                if record["returnCode"] == 0 and output.is_file():
                    show_image(output, "**Generated candidate — pending visual review, not validated fitting**")
                else:
                    display(Markdown("**FAILED / REJECTED — no successful try-on result.**"))
                    diagnostic = destination / "vton-model-output.png"
                    if diagnostic.is_file():
                        show_image(diagnostic, "**Raw diagnostic only — not a final try-on result**")
                display(Markdown(
                    "Inspect uploaded pattern/colors, neckline, shoulders, both sleeves and hem; "
                    "look for any old-shirt fragments, missing skin, halo or seams. Compare the "
                    "face/hair/hands and background with the original. Do not mark acceptance "
                    "from an API exit code or an automated stripe check alone."
                ))
        """),
        cell("code", "download-results", """
            import zipfile
            from google.colab import files

            RESULTS_ZIP = PROJECT / "colab-tryon-results.zip"
            allowed_suffixes = {".png", ".jpg", ".jpeg", ".json", ".txt", ".log"}
            with zipfile.ZipFile(RESULTS_ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(RUNS.rglob("*")):
                    if (path.is_file() and not path.is_symlink()
                            and path.resolve().is_relative_to(RUNS.resolve())
                            and path.suffix.lower() in allowed_suffixes):
                        archive.write(path, path.relative_to(PROJECT))
                archive.write(PROJECT / "SOURCE_MANIFEST.json", "SOURCE_MANIFEST.json")
            print("Actual run artifacts:", RESULTS_ZIP, RESULTS_ZIP.stat().st_size, "bytes")
            files.download(str(RESULTS_ZIP))
        """),
        cell("markdown", "optional-drive-note", """
            ## Optional result persistence

            The next cell is disabled by default. Enabling it requests Google Drive
            authorization and copies **only the result ZIP** to `MyDrive/AvatarVTON`.
            It does not enumerate, read or modify any unrelated Drive files. Checkpoints
            are not copied. Standard browser download above does not require Drive access.
        """),
        cell("code", "optional-drive", """
            SAVE_RESULTS_TO_DRIVE = False
            if SAVE_RESULTS_TO_DRIVE:
                import shutil
                from google.colab import drive
                drive.mount("/content/drive")
                drive_output = Path("/content/drive/MyDrive/AvatarVTON")
                drive_output.mkdir(parents=True, exist_ok=True)
                target = drive_output / ("results-" + SOURCE_SHA256[:12] + ".zip")
                shutil.copy2(RESULTS_ZIP, target)
                print("Saved this run's result archive:", target)
            else:
                print("Drive persistence disabled; no Drive access requested.")
        """),
    ]
    return {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
            "accelerator": "GPU",
            "colab": {"name": "Virtual_TryOn_GPU.ipynb", "provenance": []},
            "avatarVton": {"sourceArchiveSha256": digest, "qualityValidated": False},
        },
        "cells": cells,
    }


def validate_notebook(notebook: dict) -> dict:
    if notebook["nbformat"] != 4 or notebook["nbformat_minor"] != 5:
        raise ValueError("Notebook must use nbformat 4.5")
    identifiers = [item["id"] for item in notebook["cells"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Notebook cell IDs must be unique")
    code_cells = 0
    for item in notebook["cells"]:
        if item["cell_type"] == "code":
            compile("".join(item["source"]), f"<colab:{item['id']}>", "exec")
            if item["outputs"] or item["execution_count"] is not None:
                raise ValueError("Packaged notebook must not contain retained execution outputs")
            code_cells += 1
    return {"nbformat": "4.5", "codeCellsCompile": code_cells, "uniqueCellIds": True}


def build(root: Path = ROOT) -> dict:
    payload, manifest = source_archive(root)
    notebook = make_notebook(payload)
    checks = validate_notebook(notebook)
    destination = root / "notebooks/Virtual_TryOn_GPU.ipynb"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
    report = {
        "status": "packaged_and_static_checks_passed",
        "cloudExecution": "not performed by notebook builder",
        "visualAcceptance": "not evaluated by notebook builder",
        "notebook": str(destination.relative_to(root)),
        "notebookSha256": sha256(destination.read_bytes()),
        "notebookBytes": destination.stat().st_size,
        "sourceArchiveSha256": sha256(payload),
        "sourceArchiveBytes": len(payload),
        "checks": checks,
        "sourceManifest": manifest,
    }
    report_path = root / "experiments/colab-notebook-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = build(args.root.resolve())
    print(json.dumps({key: value for key, value in report.items() if key != "sourceManifest"}, indent=2))


if __name__ == "__main__":
    main()

"""Fetch the pinned, minimal CatVTON inference files; never download full snapshots."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e"
BASE_REPO = "stable-diffusion-v1-5/stable-diffusion-inpainting"
BASE_REVISION = "8a4288a76071f7280aedbdb3253bdb9e9d5d84bb"
ATTN_REPO = "zhengchong/CatVTON"
ATTN_REVISION = "2969fcf85fe62f2036605716f0b56f0b81d01d79"
VAE_REPO = "stabilityai/sd-vae-ft-mse"
VAE_REVISION = "31f26fdeee1355a5c34592e401dd41e45d25a493"

# Sizes and SHA-256 are the official Hugging Face LFS object metadata.
ASSETS = [
    (BASE_REPO, BASE_REVISION, "unet/config.json", "base/unet/config.json", 748, None),
    (
        BASE_REPO,
        BASE_REVISION,
        "scheduler/scheduler_config.json",
        "base/scheduler/scheduler_config.json",
        313,
        None,
    ),
    (
        BASE_REPO,
        BASE_REVISION,
        "unet/diffusion_pytorch_model.fp16.safetensors",
        "base/unet/diffusion_pytorch_model.fp16.safetensors",
        1719154104,
        "24b788b4a777748377cc20364eea4ae113c8c42f4468c16bc8c02fdae5492af9",
    ),
    (
        ATTN_REPO,
        ATTN_REVISION,
        "vitonhd-16k-512/attention/model.safetensors",
        "attention/vitonhd-16k-512/attention/model.safetensors",
        198303368,
        "915df7bf19a33bee36a28d5f9ceaef1e2267c47526f98ca9e4c49e90ae5f0fd0",
    ),
    (VAE_REPO, VAE_REVISION, "config.json", "vae/config.json", 547, None),
    (
        VAE_REPO,
        VAE_REVISION,
        "diffusion_pytorch_model.safetensors",
        "vae/diffusion_pytorch_model.safetensors",
        334643276,
        "a1d993488569e928462932c8c38a0760b874d166399b14414135bd9c42df5815",
    ),
    (
        BASE_REPO,
        BASE_REVISION,
        "safety_checker/config.json",
        "base/safety_checker/config.json",
        4777,
        None,
    ),
    (
        BASE_REPO,
        BASE_REVISION,
        "feature_extractor/preprocessor_config.json",
        "base/feature_extractor/preprocessor_config.json",
        342,
        None,
    ),
    (
        BASE_REPO,
        BASE_REVISION,
        "safety_checker/model.fp16.safetensors",
        "base/safety_checker/model.fp16.safetensors",
        608018440,
        "08902f19b1cfebd7c989f152fc0507bef6898c706a91d666509383122324b511",
    ),
]


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def fetch(
    session: requests.Session,
    url: str,
    target: Path,
    size: int | None = None,
    expected: str | None = None,
) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    if (
        target.is_file()
        and (size is None or target.stat().st_size == size)
        and (expected is None or sha256(target) == expected)
    ):
        print(f"Verified {target.name}: {target.stat().st_size:,} bytes", flush=True)
    else:
        partial = target.with_name(target.name + ".partial")
        for attempt in range(3):
            try:
                offset = partial.stat().st_size if partial.is_file() else 0
                headers = {"Range": f"bytes={offset}-"} if offset else {}
                with session.get(url, stream=True, timeout=(30, 120), headers=headers) as response:
                    response.raise_for_status()
                    append = offset and response.status_code == 206
                    written = offset if append else 0
                    announced = written
                    with partial.open("ab" if append else "wb") as output:
                        for chunk in response.iter_content(1024 * 1024):
                            output.write(chunk)
                            written += len(chunk)
                            if written - announced >= 64 * 1024 * 1024:
                                print(f"{target.name}: {written / 1048576:.0f} MiB", flush=True)
                                announced = written
                if size is not None and partial.stat().st_size != size:
                    raise RuntimeError(f"Unexpected size for {target.name}")
                if expected is not None and sha256(partial) != expected:
                    raise RuntimeError(f"Checkpoint SHA-256 mismatch for {target.name}")
                partial.replace(target)
                print(
                    f"Downloaded and verified {target.name}: {target.stat().st_size:,} bytes",
                    flush=True,
                )
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(2)
    return {"url": url, "sha256": sha256(target), "bytes": target.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=ROOT / "assets/vton/catvton")
    args = parser.parse_args()
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    vendor = ROOT / "ml/vton/vendor/catvton"
    source_files = []
    for filename in (
        "model/pipeline.py",
        "model/attn_processor.py",
        "model/utils.py",
        "utils.py",
        "LICENSE",
    ):
        url = f"https://raw.githubusercontent.com/Zheng-Chong/CatVTON/{SOURCE_COMMIT}/{filename}"
        response = session.get(url, timeout=60)
        response.raise_for_status()
        raw = response.content
        code = raw.decode("utf-8")
        if filename.startswith("model/"):
            code = code.replace("from model.attn_processor import", "from .attn_processor import")
            code = code.replace("from model.utils import", "from .utils import")
            code = code.replace("from utils import", "from ..utils import")
        target = vendor / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8", newline="\n")
        source_files.append(
            {
                "file": filename,
                "url": url,
                "upstreamSha256": hashlib.sha256(raw).hexdigest(),
                "localSha256": sha256(target),
            }
        )
    for folder in (vendor, vendor / "model"):
        (folder / "__init__.py").write_text("", encoding="utf-8")
    (vendor / "UPSTREAM.md").write_text(
        "# CatVTON vendored inference\n\n"
        f"Source: https://github.com/Zheng-Chong/CatVTON/tree/{SOURCE_COMMIT}\n\n"
        "Only package-relative imports are changed. The application subclasses the official pipeline "
        "for verified local loading, FP16, sequential classifier-free guidance and memory management. "
        "The original NVIDIA/Creative Commons notices are retained; CatVTON code/checkpoints use "
        "CC BY-NC-SA 4.0 and are not cleared for commercial deployment.\n\n"
        "The official pipeline accepts a caller-provided binary inpainting mask. The application "
        "uses FASHN semantic parsing rather than CatVTON's optional SCHP/DensePose automatic mask generator.\n",
        encoding="utf-8",
    )
    manifest = {"sourceCommit": SOURCE_COMMIT, "sourceFiles": source_files, "files": []}
    for repo, revision, remote, local, size, expected in ASSETS:
        url = f"https://huggingface.co/{repo}/resolve/{revision}/{remote}"
        entry = fetch(session, url, destination / local, size, expected)
        manifest["files"].append({"file": local, "repo": repo, "revision": revision, **entry})
    (destination / "download-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"CatVTON assets ready: {destination}", flush=True)


if __name__ == "__main__":
    main()

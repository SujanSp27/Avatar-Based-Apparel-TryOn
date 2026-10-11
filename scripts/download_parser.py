"""Download pinned official FASHN parser source and safetensors for local inference."""

import argparse
import base64
import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "f2771f2fb8655349e87e2869bbde7ace0bd06f2c"
MODEL_REVISION = "1f80c34dbab321c5730dda5c3fea279fd3e97498"
WEIGHTS_SHA256 = "e43c8c8a9b04f28798f0a4630cf18caa2cdb27a0d454fae43a5716e6f7078244"
CONFIG_SHA256 = "87bd5b66419dbfa7c02cfbeb94e292454863b1606c5df29526b19a6c1de70d9f"
MODEL_ID = "fashn-ai/fashn-human-parser"
VENDOR = ROOT / "ml/vton/vendor/fashn_human_parser"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=ROOT / "assets/vton/parser")
    args = parser.parse_args()
    args.destination = args.destination.resolve()
    args.destination.mkdir(parents=True, exist_ok=True)
    VENDOR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "sourceCommit": SOURCE_COMMIT,
        "modelId": MODEL_ID,
        "modelRevision": MODEL_REVISION,
        "files": [],
    }
    session = requests.Session()
    for filename in ("__init__.py", "labels.py", "parser.py", "LICENSE"):
        source_path = filename if filename == "LICENSE" else f"src/fashn_human_parser/{filename}"
        url = f"https://api.github.com/repos/fashn-AI/fashn-human-parser/contents/{source_path}?ref={SOURCE_COMMIT}"
        response = session.get(url, timeout=60)
        response.raise_for_status()
        content = base64.b64decode(response.json()["content"])
        target = VENDOR / filename
        target.write_bytes(content)
        manifest["files"].append(
            {
                "file": str(target.relative_to(ROOT)),
                "url": url,
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
            }
        )
        print(f"Vendored {filename}", flush=True)
    for filename in ("config.json", "preprocessor_config.json", "model.safetensors", "README.md"):
        url = f"https://huggingface.co/{MODEL_ID}/resolve/{MODEL_REVISION}/{filename}"
        target = args.destination / filename
        expected = {"model.safetensors": WEIGHTS_SHA256, "config.json": CONFIG_SHA256}.get(filename)
        if expected and target.is_file() and sha256(target) == expected:
            print(f"Verified existing {filename}", flush=True)
        else:
            partial = target.with_suffix(target.suffix + ".partial")
            with session.get(url, stream=True, timeout=(30, 120)) as response:
                response.raise_for_status()
                with partial.open("wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        output.write(chunk)
            if expected and sha256(partial) != expected:
                raise RuntimeError(f"Parser {filename} SHA-256 does not match the pinned asset")
            partial.replace(target)
            print(f"Downloaded {filename}: {target.stat().st_size:,} bytes", flush=True)
        manifest["files"].append(
            {
                "file": str(target.relative_to(ROOT) if target.is_relative_to(ROOT) else target),
                "url": url,
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
            }
        )
    (args.destination / "download-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (VENDOR / "UPSTREAM.md").write_text(
        "# Vendored FASHN Human Parser\n\n"
        "Official source: https://github.com/fashn-AI/fashn-human-parser\n\n"
        f"Pinned commit: `{SOURCE_COMMIT}`. The three Python files and LICENSE "
        "are unmodified. The upstream license notice and its NVIDIA license link are retained in LICENSE.\n\n"
        "The local adapter reuses official preprocessing/prediction but bypasses the upstream "
        "constructor to enforce local_files_only=True and safetensors loading. No model or "
        "image is uploaded by inference. The model uses 18 labels; neck/left/right limbs are "
        "not separate predicted classes.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

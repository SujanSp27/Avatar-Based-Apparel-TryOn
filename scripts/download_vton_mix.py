"""Download the optional official multi-dataset CatVTON attention checkpoint.

The baseline 512 checkpoint and its manifest are left intact. This file only
prepares the mixed checkpoint; loading it is an explicit adapter choice.
"""

import argparse
import json
from pathlib import Path

import requests
from download_vton import ATTN_REPO, ATTN_REVISION, SOURCE_COMMIT, fetch

ROOT = Path(__file__).resolve().parents[1]
REMOTE_PATH = "mix-48k-1024/attention/model.safetensors"
LOCAL_PATH = "attention/" + REMOTE_PATH
# Verified against the official Hugging Face tree API at this exact revision.
WEIGHTS_BYTES = 198303368
WEIGHTS_SHA256 = "a1fc093f1b6744623079e6f4e7313411f524e388c4b7467df1e0e7f577cba23a"
METADATA_URL = (
    f"https://huggingface.co/api/models/{ATTN_REPO}/tree/"
    f"{ATTN_REVISION}/mix-48k-1024/attention"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "assets/vton/catvton")
    args = parser.parse_args()
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/{ATTN_REPO}/resolve/{ATTN_REVISION}/{REMOTE_PATH}"
    with requests.Session() as session:
        record = fetch(
            session,
            url,
            destination / LOCAL_PATH,
            size=WEIGHTS_BYTES,
            expected=WEIGHTS_SHA256,
        )
    manifest = {
        "sourceCommit": SOURCE_COMMIT,
        "modelId": ATTN_REPO,
        "attentionRevision": ATTN_REVISION,
        "attentionCheckpoint": "mix-48k-1024",
        "trainedResolution": [768, 1024],
        "officialLfsMetadataUrl": METADATA_URL,
        "files": [
            {
                "file": LOCAL_PATH,
                "repo": ATTN_REPO,
                "revision": ATTN_REVISION,
                **record,
            }
        ],
        "limitations": (
            "Checkpoint download and hash verification do not establish inference "
            "compatibility or output quality. Validate memory use, garment fidelity, "
            "and identity preservation before enabling this checkpoint."
        ),
    }
    partial = destination / "mix-download-manifest.json.partial"
    partial.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    partial.replace(destination / "mix-download-manifest.json")
    print(f"Optional CatVTON mixed checkpoint ready: {destination / LOCAL_PATH}", flush=True)


if __name__ == "__main__":
    main()

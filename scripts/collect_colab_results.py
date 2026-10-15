"""Import a Colab result ZIP for local inspection without executing its contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 200 * 1024 * 1024


def collect(
    archive_path: Path, destination: Path, *, expected_manifest: dict | None = None,
) -> dict:
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Use an empty result directory; existing evidence will not be overwritten")
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        names = [entry.orig_filename for entry in entries]
        if len(entries) > 1000 or len(names) != len(set(names)):
            raise ValueError("Duplicate or excessive archive entries")
        if sum(entry.file_size for entry in entries) > LIMIT:
            raise ValueError("Result archive exceeds 200 MiB expanded")
        for entry in entries:
            name = entry.orig_filename
            path = PurePosixPath(name)
            mode = entry.external_attr >> 16
            if (path.is_absolute() or "\\" in name or ":" in name
                    or any(part in {"", ".", ".."} for part in name.split("/"))
                    or entry.is_dir() or stat.S_ISLNK(mode)
                    or path.suffix.lower() not in {".json", ".png", ".jpg", ".jpeg", ".txt", ".log"}
                    or not (name == "SOURCE_MANIFEST.json" or name.startswith("experiments/colab-runs/"))):
                raise ValueError(f"Unexpected result archive member: {name}")
            target = destination / name
            if target.is_symlink() or not target.resolve().is_relative_to(destination):
                raise ValueError("Result path escapes the destination")
        payloads = {entry.orig_filename: archive.read(entry) for entry in entries}
    manifest = json.loads(payloads["SOURCE_MANIFEST.json"]) if "SOURCE_MANIFEST.json" in payloads else None
    if expected_manifest is not None:
        if not isinstance(expected_manifest.get("files"), dict) or not expected_manifest["files"]:
            raise ValueError("Expected source manifest must contain file hashes")
        if manifest is None or manifest.get("files") != expected_manifest["files"]:
            raise ValueError("Source manifest mismatch: this archive is from a different source revision")
    cases = []
    for name, data in payloads.items():
        if not name.endswith("/report.json"):
            continue
        report = json.loads(data)
        directory = str(PurePosixPath(name).parent)
        if report["status"] == "generated" and f"{directory}/tryon-2d.png" not in payloads:
            raise ValueError(f"Generated case is missing its final image: {directory}")
        for artifact, expected in report.get("artifacts", {}).items():
            key = f"{directory}/{artifact}"
            if key in payloads:
                actual = payloads[key]
                if len(actual) != expected["bytes"] or hashlib.sha256(actual).hexdigest() != expected["sha256"]:
                    raise ValueError(f"Artifact checksum mismatch: {key}")
        cases.append({
            "case": PurePosixPath(name).parent.name,
            "report": name, "status": report["status"],
            "error": report.get("error"), "code": report.get("code"),
            "seconds": report.get("seconds"), "runtime": report.get("runtime"),
            "checkpoint": report.get("checkpoint"),
            "run": PurePosixPath(name).parent.parent.name,
            "inputSha256": report.get("inputSha256"),
            "nativeImage": f"{directory}/vton-model-output.png" if f"{directory}/vton-model-output.png" in payloads else None,
            "finalImage": f"{directory}/tryon-2d.png" if f"{directory}/tryon-2d.png" in payloads else None,
            "visualAcceptance": "pending local inspection" if report["status"] == "generated" else "not accepted",
        })
    if not cases:
        raise ValueError("The archive contains no inference case reports")
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in payloads.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    result = {
        "archiveSha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "sourceManifestSha256": (
            hashlib.sha256(payloads["SOURCE_MANIFEST.json"]).hexdigest() if manifest else None
        ),
        "sourceRevisionMatched": expected_manifest is not None,
        "files": len(payloads), "cases": cases,
        "qualityValidated": False,
    }
    (destination / "collection-report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path,
                        help="Require this SOURCE_MANIFEST.json before importing any files")
    args = parser.parse_args()
    expected = json.loads(args.expected_manifest.read_text(encoding="utf-8")) if args.expected_manifest else None
    report = collect(args.archive, args.output, expected_manifest=expected)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

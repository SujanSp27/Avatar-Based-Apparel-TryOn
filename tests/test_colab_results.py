import hashlib
import json
import zipfile

import pytest

from scripts.collect_colab_results import collect


def make_archive(tmp_path, *, changed=False, extra=None):
    path = tmp_path / "results.zip"
    root = "experiments/colab-runs/test/reported-striped-shirt"
    data = b"diagnostic bytes"
    report = {
        "status": "failed", "code": "vton_garment_fidelity_failed",
        "error": "Stripes missing", "artifacts": {"traceback.txt": {
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        }},
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{root}/report.json", json.dumps(report))
        archive.writestr(f"{root}/traceback.txt", b"changed" if changed else data)
        if extra:
            archive.writestr(extra, b"unexpected")
    return path


def test_collect_retains_failed_run_without_claiming_image_success(tmp_path):
    output = tmp_path / "collected"
    report = collect(make_archive(tmp_path), output)
    assert report["qualityValidated"] is False
    assert report["cases"][0]["status"] == "failed"
    assert report["cases"][0]["visualAcceptance"] == "not accepted"
    assert report["cases"][0]["finalImage"] is None
    assert (output / "collection-report.json").is_file()


def test_collect_refuses_corrupt_artifact_before_writing(tmp_path):
    output = tmp_path / "collected"
    with pytest.raises(ValueError, match="checksum mismatch"):
        collect(make_archive(tmp_path, changed=True), output)
    assert not output.exists()


@pytest.mark.parametrize("extra", ["../outside.txt", "backend/execute.py", "experiments/colab-runs/../secret.txt"])
def test_collect_refuses_unexpected_paths_before_writing(tmp_path, extra):
    output = tmp_path / "collected"
    with pytest.raises(ValueError, match="Unexpected result"):
        collect(make_archive(tmp_path, extra=extra), output)
    assert not output.exists()


def test_collect_preserves_existing_evidence(tmp_path):
    output = tmp_path / "collected"
    output.mkdir()
    (output / "keep.txt").write_text("keep")
    with pytest.raises(ValueError, match="empty result directory"):
        collect(make_archive(tmp_path), output)
    assert (output / "keep.txt").read_text() == "keep"


@pytest.mark.parametrize("actual", [None, {"files": {"ml/vton/masking.py": {"sha256": "old", "bytes": 1}}}])
def test_collect_rejects_old_or_unidentified_run_before_writing(tmp_path, actual):
    archive = make_archive(tmp_path)
    if actual is not None:
        with zipfile.ZipFile(archive, "a") as bundle:
            bundle.writestr("SOURCE_MANIFEST.json", json.dumps(actual))
    expected = {"files": {"ml/vton/masking.py": {"sha256": "new", "bytes": 1}}}
    output = tmp_path / "collected"
    with pytest.raises(ValueError, match="Source manifest mismatch"):
        collect(archive, output, expected_manifest=expected)
    assert not output.exists()


def test_collect_identifies_matching_run_without_claiming_quality(tmp_path):
    archive = make_archive(tmp_path)
    manifest = {"files": {"ml/vton/masking.py": {"sha256": "test", "bytes": 1}}}
    with zipfile.ZipFile(archive, "a") as bundle:
        bundle.writestr("SOURCE_MANIFEST.json", json.dumps(manifest))
    report = collect(archive, tmp_path / "collected", expected_manifest=manifest)
    assert report["sourceRevisionMatched"] is True
    assert report["cases"][0]["run"] == "test"
    assert report["qualityValidated"] is False


def test_collect_rejects_generated_status_without_image(tmp_path):
    archive = tmp_path / "results.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("experiments/colab-runs/test/case/report.json", '{"status": "generated"}')
    output = tmp_path / "collected"
    with pytest.raises(ValueError, match="missing its final image"):
        collect(archive, output)
    assert not output.exists()

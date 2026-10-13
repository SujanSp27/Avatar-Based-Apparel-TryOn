"""The Colab package must be reproducible, private-by-default, and executable."""

import base64
import io
import json
import stat
import zipfile
from pathlib import Path

import pytest

from scripts import build_colab_notebook as builder


def extractor():
    scope = {}
    exec(builder.EXTRACTOR, scope)
    return scope["extract_verified_source"]


def archive_with(entries: dict[str, bytes], *, symlink: str | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            # ZipInfo normalizes backslashes on Windows; retain the malicious
            # wire-format spelling so this actually exercises the extractor.
            info.filename = name
            info.create_system = 3
            info.external_attr = ((stat.S_IFLNK if name == symlink else stat.S_IFREG) | 0o644) << 16
            archive.writestr(info, data)
    return output.getvalue()


def test_real_archive_is_reproducible_and_explicit():
    assert len(builder.SOURCE_FILES) == len(set(builder.SOURCE_FILES))
    first, first_manifest = builder.source_archive()
    second, second_manifest = builder.source_archive()
    assert first == second
    assert first_manifest == second_manifest
    assert len(first) < builder.ARCHIVE_LIMIT
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        names = set(archive.namelist())
        assert names == set(builder.SOURCE_FILES) | {"SOURCE_MANIFEST.json"}
        assert {name for name in names if name.endswith((".jpg", ".png"))} == set(builder.FIXTURE_SHA256)
        assert not any(
            forbidden in name
            for name in names
            for forbidden in (".env", "data/processed", "backend/", "assets/", ".venv", "__pycache__")
        )
        assert "ml/vton/vendor/catvton/LICENSE" in names
        assert "ml/vton/vendor/fashn_human_parser/LICENSE" in names
        for name, entry in first_manifest["files"].items():
            assert builder.sha256(archive.read(name)) == entry["sha256"]


def test_real_archive_extracts_and_checks_all_bytes(tmp_path):
    payload, manifest = builder.source_archive()
    destination = tmp_path / "isolated"
    assert extractor()(payload, builder.sha256(payload), destination) == manifest
    for relative, entry in manifest["files"].items():
        actual = destination.joinpath(relative).read_bytes()
        assert len(actual) == entry["bytes"]
        assert builder.sha256(actual) == entry["sha256"]


def test_notebook_code_compiles_without_executing_installs_or_inference():
    payload, _ = builder.source_archive()
    notebook = builder.make_notebook(payload)
    result = builder.validate_notebook(notebook)
    assert result["codeCellsCompile"] == 6
    assert notebook["metadata"]["accelerator"] == "GPU"
    assert notebook["metadata"]["avatarVton"]["qualityValidated"] is False
    bootstrap = next(item for item in notebook["cells"] if item["id"] == "verified-source")
    source = "".join(bootstrap["source"])
    assert base64.b64encode(payload).decode("ascii") in source
    assert "extract_verified_source" in source
    assert all(item.get("outputs", []) == [] for item in notebook["cells"])
    combined = "\n".join("".join(item["source"]) for item in notebook["cells"])
    assert "SAVE_RESULTS_TO_DRIVE = False" in combined
    assert "pending visual review" in combined
    assert "check=False" in combined  # failure reports retained; no fake success


@pytest.mark.parametrize("name", ["../outside", "/outside", "C:/secret", "ml/../outside", "ml\\outside", "ml//bad", "./bad"])
def test_builder_refuses_unsafe_member_names(name):
    with pytest.raises(ValueError, match="Unsafe archive path"):
        builder.validate_member_name(name)


@pytest.mark.parametrize("name", ["../outside", "/outside", "C:/secret", "ml/../outside", "ml\\outside", "ml//bad", "./bad"])
def test_embedded_extractor_rejects_traversal_before_writing(name, tmp_path):
    payload = archive_with({name: b"not safe", "SOURCE_MANIFEST.json": b"{}"})
    destination = tmp_path / "unpacked"
    with pytest.raises(ValueError, match="Unsafe archive member"):
        extractor()(payload, builder.sha256(payload), destination)
    assert not destination.exists()


def test_extractor_rejects_archive_hash_mismatch(tmp_path):
    with pytest.raises(ValueError, match="archive checksum mismatch"):
        extractor()(b"bad payload", "0" * 64, tmp_path / "unpacked")


def test_extractor_rejects_symlink_before_writing(tmp_path):
    payload = archive_with({"ml/link": b"../../secret", "SOURCE_MANIFEST.json": b"{}"}, symlink="ml/link")
    with pytest.raises(ValueError, match="Unsafe archive member"):
        extractor()(payload, builder.sha256(payload), tmp_path / "unpacked")


def test_extractor_rejects_manifest_file_mismatch(tmp_path):
    manifest = {"files": {"ml/module.py": {"sha256": builder.sha256(b"expected"), "bytes": 8}}}
    payload = archive_with({"ml/module.py": b"tampered", "SOURCE_MANIFEST.json": json.dumps(manifest).encode()})
    with pytest.raises(ValueError, match="Source checksum mismatch"):
        extractor()(payload, builder.sha256(payload), tmp_path / "unpacked")
    assert not (tmp_path / "unpacked").exists()


def test_extractor_rejects_unlisted_file(tmp_path):
    payload = archive_with({"unlisted.py": b"bad", "SOURCE_MANIFEST.json": b'{"files": {}}'})
    with pytest.raises(ValueError, match="contents disagree"):
        extractor()(payload, builder.sha256(payload), tmp_path / "unpacked")


def test_extractor_rejects_duplicate_archive_entries(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("same", b"first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("same", b"second")
    payload = buffer.getvalue()
    with pytest.raises(ValueError, match="Duplicate"):
        extractor()(payload, builder.sha256(payload), tmp_path / "unpacked")


def test_saved_notebook_contains_current_source():
    path = Path(builder.ROOT) / "notebooks/Virtual_TryOn_GPU.ipynb"
    if not path.exists():
        pytest.skip("Build artifact is checked after the source package is built")
    notebook = json.loads(path.read_text(encoding="utf-8"))
    payload, _ = builder.source_archive()
    assert notebook["metadata"]["avatarVton"]["sourceArchiveSha256"] == builder.sha256(payload)
    builder.validate_notebook(notebook)


def test_combined_execution_guards_gpu_before_setup_and_omits_drive(monkeypatch):
    monkeypatch.syspath_prepend(str(builder.ROOT / "scripts"))
    from colab_notebook_control import execution_source

    payload, _ = builder.source_archive()
    source = execution_source(builder.make_notebook(payload))
    assert "drive.mount" not in source
    assert "show_image(" not in source
    assert source.index("/dev/nvidia") < source.index("extract_verified_source(")
    assert source.index('"setup",') < source.index("CASE_RECORDS = []")
    assert source.index("CASE_RECORDS = []") < source.index("files.download(")
    monkeypatch.setattr("glob.glob", lambda pattern: [])
    with pytest.raises(RuntimeError, match="Select a Colab GPU"):
        exec(compile(source, "<colab-test>", "exec"), {})

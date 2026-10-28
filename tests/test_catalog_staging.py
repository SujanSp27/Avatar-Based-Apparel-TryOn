"""Staged licensed sources never publish or overwrite existing product records."""
import hashlib
import io
import json

import pytest
from PIL import Image

from scripts import download_catalog, evaluate_wardrobe


def fixture_manifest(tmp_path):
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    buf = io.BytesIO()
    Image.new("RGB", (384, 512), "white").save(buf, "PNG")
    (raw / "candidate.png").write_bytes(buf.getvalue())
    row = dict(id="staged-fixture", name="Staged fixture", category="shirt", photoType="flat-lay",
               filename="candidate.png", commercial_use=True, image_sha256=hashlib.sha256(buf.getvalue()).hexdigest(),
               source_image_sha256=hashlib.sha256(buf.getvalue()).hexdigest(), asset_transform="none",
               asset_url="https://example.com/candidate.png")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps([row]))
    return path, row, buf.getvalue()


def test_staged_manifest_checks_hash_id_and_paths(tmp_path, monkeypatch):
    path, row, _ = fixture_manifest(tmp_path)
    monkeypatch.setattr(evaluate_wardrobe, "ROOT", tmp_path)
    assert evaluate_wardrobe.catalog_rows(path) == [row]
    for change in ({"id": "../../other"}, {"filename": "../../secret"}, {"photoType": "back"}, {"image_sha256": "0" * 64}):
        path.write_text(json.dumps([{**row, **change}]))
        with pytest.raises(ValueError):
            evaluate_wardrobe.catalog_rows(path)
    path.write_text(json.dumps([row, row]))
    with pytest.raises(ValueError):
        evaluate_wardrobe.catalog_rows(path)


def test_asset_restore_never_overwrites_local_edits(tmp_path, monkeypatch):
    path, _, _ = fixture_manifest(tmp_path)
    monkeypatch.setattr(download_catalog, "ROOT", tmp_path)
    monkeypatch.setattr(download_catalog.requests, "get", lambda *a, **kw: pytest.fail("No network expected"))
    download_catalog.restore(path)
    (tmp_path / "data/raw/candidate.png").write_bytes(b"existing local work")
    with pytest.raises(RuntimeError, match="preserve"):
        download_catalog.restore(path)


def test_unmodified_web_asset_restore_preserves_exact_bytes(tmp_path, monkeypatch):
    path, _, content = fixture_manifest(tmp_path)
    monkeypatch.setattr(download_catalog, "ROOT", tmp_path)
    target = tmp_path / "data/raw/candidate.png"
    target.unlink()

    class Response:
        def raise_for_status(self):
            pass

    response = Response()
    response.content = content
    monkeypatch.setattr(download_catalog.requests, "get", lambda *a, **kw: response)
    download_catalog.restore(path)
    assert target.read_bytes() == content

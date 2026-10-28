"""The review ledger retains failed attempts and cannot inflate quality evidence."""
import json

import pytest

from scripts import report_wardrobe_trials as ledger
from scripts.evaluate_wardrobe import digest, save


def case(folder, *, status="generated", seconds=29.5):
    target = folder / "cases/product/studio"
    save(target / "trial.json", {
        "status": status, "productId": "product", "personId": "studio",
        "jobId": folder.name, "inputs": {}, "outputSha256": digest(b"output"),
        "observedEndToEndSeconds": seconds,
    })
    if status == "generated":
        (target / "after.png").write_bytes(b"output")
    return target


def review(target, **changes):
    value = {
        "outputSha256": digest(b"output"), "decision": "visual_pass",
        "fullResolutionInspected": True, "majorArtifacts": False,
        "reviewer": "Test fixture", "reviewedAt": "2026-10-28T00:00:00Z",
        "notes": "Fixture review, not actual inference evidence.",
        "ratings": dict.fromkeys(("reference_fidelity", "anatomy", "boundaries", "preservation"), 4),
    }
    value.update(changes)
    save(target / "visual-review.json", value)


@pytest.mark.parametrize("changes", [
    {"notes": ""}, {"reviewer": ""}, {"reviewedAt": None},
    {"fullResolutionInspected": False}, {"majorArtifacts": True},
    {"decision": "approved"}, {"ratings": {}},
    {"ratings": dict.fromkeys(("reference_fidelity", "anatomy", "boundaries", "preservation"), True)},
    {"ratings": dict.fromkeys(("reference_fidelity", "anatomy", "boundaries", "preservation"), 3)},
])
def test_incomplete_or_failing_reviews_never_count_as_visual_pass(tmp_path, changes):
    target = case(tmp_path)
    review(target, **changes)
    assert ledger.collect(tmp_path, "input")[0]["visualDecision"] == "pending_or_stale"


def test_completed_review_tracks_output_and_job_state(tmp_path):
    target = case(tmp_path)
    review(target)
    assert ledger.collect(tmp_path, "input")[0]["visualDecision"] == "visual_pass"
    # A leftover image/review cannot certify an unsuccessful replacement attempt.
    case(tmp_path, status="failed")
    assert ledger.collect(tmp_path, "input")[0]["visualDecision"] == "pending_or_stale"


def test_separate_retry_keeps_failure_and_duplicate_paths_do_not_inflate_counts(tmp_path, monkeypatch):
    original, experiment, retry = (tmp_path / name for name in ("original", "experiment", "retry"))
    case(original, status="failed", seconds=2)
    reviewed = case(retry)
    review(reviewed, decision="failed", majorArtifacts=True)
    save(tmp_path / "data/catalog/wardrobe-approved-v1.json", {"enforced": False, "garments": []})
    monkeypatch.setattr(ledger, "ROOT", tmp_path)
    monkeypatch.setattr(ledger, "catalog_rows", lambda: [{"id": "product", "name": "Fixture garment"}])
    destination = tmp_path / "report"
    result = ledger.write_report(original, experiment, destination, [retry, retry / ".", original])
    assert result["trialCount"] == 2
    assert result["inferenceFailures"] == 1
    assert result["generatedCount"] == result["reviewedOutputs"] == 1
    assert result["visuallyPassingCases"] == result["publishedCount"] == 0
    rows = json.loads((destination / "summary.json").read_text())["cases"]
    assert {row["jobId"] for row in rows} == {"original", "retry"}
    assert all(row["under30Seconds"] for row in rows)

"""Benchmark orchestration tests; fixture responses are not real GPU evidence."""
import json

import pytest

from ml.errors import PipelineError
from scripts import benchmark_online_vton as benchmark


@pytest.mark.parametrize("elapsed,expected", [(29.999, True), (30.0, False), (30.001, False)])
def test_timing_excludes_artifact_retrieval_and_uses_strict_target(tmp_path, monkeypatch, elapsed, expected):
    person, garment, output = (tmp_path / name for name in ("person.png", "garment.png", "trial"))
    person.write_bytes(b"person fixture")
    garment.write_bytes(b"garment fixture")
    monkeypatch.setattr(benchmark.sys, "argv", ["benchmark", "--person", str(person), "--garment",
                        str(garment), "--output", str(output), "--steps", "20"])
    for key in ("online_vton_steps", "online_vton_input_encoding", "online_vton_timeout"):
        monkeypatch.setattr(benchmark.settings, key, getattr(benchmark.settings, key))
    ticks = iter([100.0, 100.0 + elapsed])
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: next(ticks))
    calls = []

    class Worker:
        def render(self, supplied_person, supplied_garment, category, photo_type, destination):
            calls.append((supplied_person, supplied_garment, category, photo_type))
            assert destination == output
            return {"steps": 20, "runPath": "/content/formfit-online/runs/1234567890"}

    def audit(destination, report, connection):
        saved = json.loads((destination / "benchmark.json").read_text())
        assert saved["status"] == "generated"
        assert saved["endToEndSeconds"] == pytest.approx(elapsed)
        assert saved["visualAcceptance"] == "pending inspection"
        return {"status": "unavailable", "reason": "fixture_endpoint_expired"}

    monkeypatch.setattr(benchmark, "OnlineTryOn", Worker)
    monkeypatch.setattr(benchmark, "retrieve_http", audit)
    benchmark.main()
    saved = json.loads((output / "benchmark.json").read_text())
    assert len(calls) == 1
    assert saved["timingTargetMet"] is expected
    assert saved["status"] == "generated"
    assert saved["auditRetrieval"]["status"] == "unavailable"
    # An existing folder cannot silently replace the original run or its evidence.
    with pytest.raises(FileExistsError):
        benchmark.main()
    assert len(calls) == 1


def test_failed_generation_does_not_fetch_audits_or_repeat_inference(tmp_path, monkeypatch):
    person, garment, output = (tmp_path / name for name in ("person.png", "garment.png", "trial"))
    person.write_bytes(b"person fixture")
    garment.write_bytes(b"garment fixture")
    monkeypatch.setattr(benchmark.sys, "argv", ["benchmark", "--person", str(person), "--garment",
                        str(garment), "--output", str(output)])
    for key in ("online_vton_steps", "online_vton_input_encoding", "online_vton_timeout"):
        monkeypatch.setattr(benchmark.settings, key, getattr(benchmark.settings, key))
    calls = []

    class Worker:
        def render(self, *args):
            calls.append(True)
            raise PipelineError("online_gpu_connection", "Connection interrupted")

    monkeypatch.setattr(benchmark, "OnlineTryOn", Worker)
    monkeypatch.setattr(benchmark, "retrieve_http", lambda *args: pytest.fail("No completed run to retrieve"))
    with pytest.raises(SystemExit) as exc:
        benchmark.main()
    assert exc.value.code == 1
    saved = json.loads((output / "benchmark.json").read_text())
    assert saved["status"] == "failed"
    assert saved["timingTargetMet"] is False
    assert saved["inputs"]["steps"] == 20
    assert len(calls) == 1

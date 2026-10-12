"""Protect isolation and honest failure reporting in the cloud runner."""

import argparse
import json
import os
from pathlib import Path

import pytest

from scripts import colab_runtime as runner


def run_args(tmp_path, **updates):
    values = dict(person=tmp_path / "person.png", garment=tmp_path / "garment.png",
                  category="t-shirt", output=tmp_path / "output", guidance=2.5,
                  seed=42, dry_run=False, check_only=False)
    values.update(updates)
    return argparse.Namespace(**values)


def test_dry_run_does_not_import_model_or_create_result(tmp_path, monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("Dry run attempted execution")

    monkeypatch.setattr(runner, "runtime_probe", unexpected)
    monkeypatch.setattr(runner.subprocess, "run", unexpected)
    args = run_args(tmp_path, dry_run=True)
    assert runner.run(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["checkpoint"] == "mix-48k-1024"
    assert report["nativeResolution"] == [768, 1024]
    assert report["status"] == "dry-run"
    assert not args.output.exists()


def test_setup_dry_run_does_not_create_environment(tmp_path, monkeypatch, capsys):
    def unexpected(*args, **kwargs):
        raise AssertionError("Dry run attempted setup")

    monkeypatch.setattr(runner, "create_environment", unexpected)
    args = argparse.Namespace(venv=tmp_path / "env", dry_run=True, check_only=False)
    assert runner.setup(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dry-run"
    assert not args.venv.exists()


def test_setup_uses_isolated_interpreter_and_includes_mixed_checkpoint(tmp_path):
    venv = tmp_path / "env"
    commands = runner.setup_commands(venv)
    assert all(command[0] == str(runner.env_python(venv)) for command in commands)
    assert any("torch==2.5.1+cu121" in command for command in commands)
    assert any(any(arg.endswith("download_vton_mix.py") for arg in command) for command in commands)


def test_environment_ignores_notebook_pythonpath(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "unrelated-notebook-packages")
    monkeypatch.setenv("PYTHONHOME", "unrelated-interpreter")
    env = runner.isolated_environment()
    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert os.environ["PYTHONPATH"] == "unrelated-notebook-packages"
    assert env["PYTHONNOUSERSITE"] == "1"


def test_refuses_current_interpreter_environment():
    with pytest.raises(RuntimeError, match="current notebook/global"):
        runner.create_environment(Path(runner.sys.prefix), runner.isolated_environment())


def test_refuses_unrelated_existing_directory(tmp_path):
    (tmp_path / "keep.txt").write_text("keep")
    with pytest.raises(RuntimeError, match="unrelated files"):
        runner.create_environment(tmp_path, runner.isolated_environment())
    assert (tmp_path / "keep.txt").read_text() == "keep"


def test_runtime_failure_retains_report_without_success_image(tmp_path, monkeypatch, capsys):
    def unavailable():
        raise RuntimeError("No CUDA GPU is available")

    monkeypatch.setattr(runner, "runtime_probe", unavailable)
    args = run_args(tmp_path)
    assert runner.run(args) == 1
    report = json.loads((args.output / "report.json").read_text())
    assert report["status"] == "failed"
    assert report["visualAcceptance"] == "not accepted"
    assert "No CUDA GPU" in report["error"]
    assert (args.output / "traceback.txt").is_file()
    assert not (args.output / "tryon-2d.png").exists()


def test_refuses_stale_result_directory(tmp_path):
    args = run_args(tmp_path)
    args.output.mkdir()
    (args.output / "tryon-2d.png").write_bytes(b"previous run")
    with pytest.raises(RuntimeError, match="not empty"):
        runner.run(args)
    assert (args.output / "tryon-2d.png").read_bytes() == b"previous run"


def test_unsupported_category_rejected_by_cli(tmp_path):
    with pytest.raises(SystemExit) as exc:
        runner.main(["run", "--person", "person", "--garment", "garment",
                     "--category", "dress", "--output", str(tmp_path), "--dry-run"])
    assert exc.value.code == 2

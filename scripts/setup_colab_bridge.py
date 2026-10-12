"""Install Google's Colab bridge in an isolated, workspace-owned environment.

No project .venv, global Python, shell profile, or Codex configuration is changed.
Network downloads are pinned to an official Google source revision and uv wheel.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".runtime" / "colab-mcp-tools"
REVISION = "b9ab3899e0f1fa493390b1fd6d54aa2e464ecdf1"
UV_VERSION = "0.13.0"
UV_URL = (
    "https://files.pythonhosted.org/packages/b2/00/73abae6cafcdb868d42b2c71bf12c9c2e"
    "b06a8d229a09569760c41b7948d/uv-0.13.0-py3-none-win_amd64.whl"
)
UV_SHA256 = "0367b4e0ae4dcef32da4aa2ad2f3853b6ad81d50c187abe50d343d892b8fea21"
SOURCE_URL = f"https://codeload.github.com/googlecolab/colab-mcp/zip/{REVISION}"
SOURCE_SHA256 = "e2dc465f144dc48686677c20fca6f881144acf46b4d2c622dc3ef5cd016fbae5"
LOCK = ROOT / "scripts" / "requirements-colab-bridge.lock.txt"


def fetch(url: str, target: Path, expected: str | None = None) -> str:
    if not target.exists():
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        partial = target.with_suffix(target.suffix + ".partial")
        with opener.open(url, timeout=60) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.replace(target)
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if expected and digest != expected:
        raise RuntimeError(f"SHA256 verification failed for {target.name}")
    return digest


def main() -> None:
    if os.name != "nt":
        raise RuntimeError("This installer currently targets Windows x64.")
    TOOLS.mkdir(parents=True, exist_ok=True)
    env = {
        key: value for key, value in os.environ.items()
        if key.lower() not in {"http_proxy", "https_proxy", "all_proxy"}
    }
    env.update({
        "UV_CACHE_DIR": str(TOOLS / "cache"),
        "UV_PYTHON_INSTALL_DIR": str(TOOLS / "python"),
        "UV_PYTHON_BIN_DIR": str(TOOLS / "bin"),
        "UV_PYTHON_INSTALL_BIN": "0",
        "UV_NO_PROGRESS": "1",
        "UV_LINK_MODE": "copy",
    })
    wheel = TOOLS / f"uv-{UV_VERSION}.whl"
    fetch(UV_URL, wheel, UV_SHA256)
    uv = TOOLS / "uv.exe"
    if not uv.exists():
        with zipfile.ZipFile(wheel) as archive:
            entry = next(name for name in archive.namelist() if name.endswith("/uv.exe"))
            uv.write_bytes(archive.read(entry))
    source_zip = TOOLS / f"colab-mcp-{REVISION}.zip"
    source_digest = fetch(SOURCE_URL, source_zip, SOURCE_SHA256)
    source = TOOLS / f"colab-mcp-{REVISION}"
    if not source.exists():
        with zipfile.ZipFile(source_zip) as archive:
            for entry in archive.infolist():
                destination = (TOOLS / entry.filename).resolve()
                if not destination.is_relative_to(TOOLS.resolve()):
                    raise RuntimeError("Unsafe source archive path")
            archive.extractall(TOOLS)

    def run(*args: str, capture: bool = False) -> str:
        result = subprocess.run(
            [str(uv), "--no-config", *args], env=env, cwd=TOOLS,
            check=True, text=True, capture_output=capture,
        )
        return result.stdout.strip() if capture else ""

    run("python", "install", "3.13.16", "--no-bin", "--no-registry")
    python_base = run("python", "find", "3.13.16", "--managed-python", capture=True)
    venv = TOOLS / "venv"
    python = venv / "Scripts" / "python.exe"
    if not python.exists():
        run("venv", str(venv), "--python", python_base, "--no-project")
    dependency_input = TOOLS / "requirements.in"
    dependency_input.write_text("psutil==7.0.0\n", encoding="utf-8")
    if not LOCK.exists():
        run(
            "pip", "compile", str(source / "pyproject.toml"), str(dependency_input),
            "--python", str(python),
            "--generate-hashes", "--output-file", str(LOCK), capture=True,
        )
    run("pip", "install", "--python", str(python), "--require-hashes", "-r", str(LOCK))
    run("pip", "install", "--python", str(python), "--no-deps", str(source))
    run("pip", "check", "--python", str(python))
    version = subprocess.check_output([str(python), "--version"], text=True).strip()
    (TOOLS / "setup-manifest.json").write_text(json.dumps({
        "source": "https://github.com/googlecolab/colab-mcp",
        "revision": REVISION,
        "sourceArchiveSha256": source_digest,
        "uvVersion": UV_VERSION,
        "uvWheelSha256": UV_SHA256,
        "pythonVersion": version,
        "pythonExecutable": str(python),
        "requirementsLock": str(LOCK.relative_to(ROOT)),
        "requirementsLockSha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
    }, indent=2), encoding="utf-8")
    print(f"Colab bridge environment ready: {python}")


if __name__ == "__main__":
    main()

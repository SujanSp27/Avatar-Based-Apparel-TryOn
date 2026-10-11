"""Install official portable PostgreSQL binaries inside the workspace."""

import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://get.enterprisedb.com/postgresql/postgresql-17.11-1-windows-x64-binaries.zip"
target = ROOT / ".runtime"
archive = target / "postgres.zip"
target.mkdir(exist_ok=True)
if not archive.exists():
    with urllib.request.urlopen(URL, timeout=120) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
with zipfile.ZipFile(archive) as bundle:
    # Exclude pgAdmin/StackBuilder and documentation; retain server dependencies.
    for item in bundle.infolist():
        if item.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
            resolved = (target / item.filename).resolve()
            if not resolved.is_relative_to(target.resolve()):
                raise ValueError("Unsafe archive member")
            bundle.extract(item, target)
(target / "postgres-download.json").write_text(
    json.dumps(
        {"url": URL, "sha256": hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()},
        indent=2,
    )
)
print("Portable PostgreSQL extracted", flush=True)

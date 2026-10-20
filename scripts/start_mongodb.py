"""Start the project's loopback MongoDB, or verify the explicitly configured server."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from backend.app.anthropometry.repository import MeasurementRepository
from backend.app.config import settings


def main():
    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=800)
    try:
        client.admin.command("ping")
    except PyMongoError:
        if settings.mongodb_uri != "mongodb://127.0.0.1:27018":
            raise RuntimeError("Configured MongoDB is unavailable; refusing to start a different database.")
        executable = shutil.which("mongod")
        if not executable:
            candidates = sorted(Path("C:/Program Files/MongoDB/Server").glob("*/bin/mongod.exe"), reverse=True)
            executable = str(candidates[0]) if candidates else None
        if not executable:
            raise RuntimeError("Install MongoDB Community or start the 'measurements-db' Docker service.")
        runtime = ROOT / ".runtime/mongodb"
        runtime.mkdir(parents=True, exist_ok=True)
        process = subprocess.Popen(
            [executable, "--dbpath", str(runtime), "--bind_ip", "127.0.0.1",
             "--port", "27018", "--logpath", str(runtime / "mongod.log"), "--logappend",
             "--wiredTigerCacheSizeGB", "0.25"],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        (runtime / "process.json").write_text(json.dumps({"pid": process.pid}), encoding="utf-8")
        for _ in range(40):
            if process.poll() is not None:
                raise RuntimeError("MongoDB exited. Inspect .runtime/mongodb/mongod.log.")
            try:
                client.admin.command("ping")
                break
            except PyMongoError:
                time.sleep(0.25)
        else:
            raise RuntimeError("MongoDB did not become ready; inspect its log.")
    repository = MeasurementRepository(client)
    repository.initialize()
    print(f"MongoDB ready; {len(repository.list_charts())} apparel chart versions available.")
    client.close()


if __name__ == "__main__":
    main()

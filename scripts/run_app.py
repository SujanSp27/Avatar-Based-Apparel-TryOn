import os
import sys
import time
import subprocess
import shutil
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    print("=" * 60)
    print("Starting VastraView Services in Daemon Mode...")
    print("=" * 60)

    # 1. Start PostgreSQL
    print("[1/5] Starting PostgreSQL 17 on port 5433...")
    pg_script = ROOT / "scripts/start-postgres.ps1"
    pg_res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(pg_script)], cwd=ROOT)
    if pg_res.returncode != 0:
        print("Warning: PostgreSQL startup returned non-zero code, checking connection...")

    # 2. Alembic Migrations
    print("[2/5] Running database migrations...")
    python_exe = sys.executable
    subprocess.run([python_exe, "-m", "alembic", "upgrade", "head"], cwd=ROOT)

    # 3. Start MongoDB
    print("[3/5] Starting MongoDB on port 27018...")
    mongo_script = ROOT / "scripts/start_mongodb.py"
    subprocess.run([python_exe, str(mongo_script)], cwd=ROOT)

    # 4. Start FastAPI Backend
    print("[4/5] Launching FastAPI backend on http://127.0.0.1:8000...")
    backend_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT
    )

    # 5. Start Vite Frontend
    print("[5/5] Launching Vite Frontend on http://127.0.0.1:5173...")
    vite_bin = ROOT / "frontend/node_modules/vite/bin/vite.js"
    frontend_proc = subprocess.Popen(
        ["node", str(vite_bin), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        cwd=ROOT / "frontend"
    )

    # 6. Readiness Probe
    print("Waiting for endpoints to become ready...")
    ready = False
    for attempt in range(50):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as resp:
                if resp.status == 200:
                    with urllib.request.urlopen("http://127.0.0.1:5173", timeout=2) as f_resp:
                        if f_resp.status == 200:
                            ready = True
                            break
        except Exception:
            time.sleep(0.5)

    if ready:
        print("\n" + "=" * 60)
        print(">>> VASTRAVIEW IS RUNNING AND READY! <<<")
        print("Frontend Studio:   http://127.0.0.1:5173")
        print("API Documentation: http://127.0.0.1:8000/docs")
        print("Health Endpoint:   http://127.0.0.1:8000/api/health")
        print("=" * 60 + "\n")
    else:
        print("Warning: Timed out waiting for 200 OK, but processes are running.")

    # Keep alive indefinitely
    try:
        while True:
            if backend_proc.poll() is not None:
                print("Backend process exited unexpectedly.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend process exited unexpectedly.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping services...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    main()

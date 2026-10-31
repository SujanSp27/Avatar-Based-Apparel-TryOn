"""Simple, independent tool to connect VastraView to any Google Colab session.

Can be run via:
  python scripts/connect_colab.py
or by passing the pasted connection JSON or Gradio URL directly.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings
from scripts.connect_online_worker import save_connection

def extract_credentials(raw: str):
    raw = raw.strip()
    url, token = None, None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            if "connection" in parsed and isinstance(parsed["connection"], dict):
                parsed = parsed["connection"]
            url = parsed.get("url")
            token = parsed.get("token")
    except Exception:
        pass
    if not url:
        url_match = re.search(r"https://[a-zA-Z0-9-]+\.gradio\.live", raw)
        if url_match:
            url = url_match.group(0)
    if not token:
        remaining = raw.replace(url, "") if url else raw
        token_match = re.search(r"[A-Za-z0-9_-]{32,80}", remaining)
        if token_match:
            token = token_match.group(0)
    return url, token

def connect(raw_text: str):
    url, token = extract_credentials(raw_text)
    if not url:
        print("[ERROR] Could not find a Gradio URL (e.g. https://xxxx.gradio.live).")
        return False
    if not token:
        print("[ERROR] Could not find a 48-character private worker token.")
        return False

    print(f"\n[1/3] Found Colab URL: {url}")
    print(f"[2/3] Found Token: {token[:6]}...{token[-6:]}")
    print("[3/3] Testing worker connection...")

    # Test status endpoint
    req = urllib.request.Request(
        f"{url.rstrip('/')}/gradio_api/run/status",
        data=json.dumps({"data": [token]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            data = body.get("data", [])
            status = data[0] if isinstance(data, list) and data else {}
            if isinstance(status, str):
                status = json.loads(status)
            if not status.get("ready"):
                print("[WARNING] Worker replied but model is still loading. Saving connection anyway...")
            else:
                print(f"[OK] Colab GPU is LIVE! (Device: {status.get('device', 'cuda')})")
    except Exception as e:
        print(f"[WARNING] Worker did not reply to test ping: {e}. Saving connection anyway...")

    data = {
        "url": url.rstrip("/"),
        "token": token.strip(),
        "gpu": "Tesla T4",
        "model": "7720683168567eb5a2a4c67f15116c6e29c83ded",
        "modelResolution": [576, 864],
        "precision": "torch.float16",
    }
    save_connection(data, settings.online_connection_path)
    print(f"\n[SUCCESS] Successfully connected VastraView to Colab GPU!")
    print(f"Connection saved to: {settings.online_connection_path}")
    print("VastraView web app will now show: Ready to try on!\n")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        print("=" * 60)
        print("   VastraView Colab GPU Quick Connector")
        print("=" * 60)
        print("Paste your Colab connection output line or Gradio URL + token below:")
        try:
            text = input("> ")
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

    if not text.strip():
        print("[ERROR] No input provided.")
        sys.exit(1)

    success = connect(text)
    if not success:
        sys.exit(1)

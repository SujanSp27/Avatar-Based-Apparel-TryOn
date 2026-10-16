"""Recover the active Colab connection without printing its private token."""
import json
from pathlib import Path
from urllib.parse import urlparse

if __package__:
    from .colab_control import ROOT
    from .colab_notebook_control import result
else:
    from colab_control import ROOT
    from colab_notebook_control import result


def save_connection(connection: dict, target: Path):
    """Atomically adopt credentials returned by the saved private notebook."""
    parsed = urlparse(connection.get('url', ''))
    token = connection.get('token')
    if (parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.gradio.live')
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {'', '/'} or parsed.port not in {None, 443}
            or not isinstance(token, str) or len(token) < 32):
        raise ValueError('Colab did not return a valid private worker connection')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.partial')
    temporary.write_text(json.dumps(connection), encoding='utf-8')
    temporary.replace(target)


def main():
    state = json.loads((ROOT / ".runtime/online-deployment.json").read_text())
    request = state["requests"][-1]
    response = result(request["id"])
    lines = "".join("".join(o.get("text", [])) for o in response.get("outputs", []) if o.get("output_type") == "stream")
    status = json.loads(lines.strip())
    connection = status.get("connection")
    if not status.get("setupComplete") or not connection or not connection.get("url", "").startswith("https://"):
        raise RuntimeError("The latest Colab status does not report a ready worker.")
    connection["token"] = (ROOT / ".runtime/online-worker-token.txt").read_text().strip()
    target = ROOT / ".runtime/online-connection.json"
    save_connection(connection, target)
    print("Saved private Colab connection; the running app adopts it automatically.")


if __name__ == "__main__":
    main()

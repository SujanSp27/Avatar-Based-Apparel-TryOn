"""Launch pinned official Colab MCP against a specified existing notebook.

Only its browser target is configured. The official authentication, origin
checks and notebook tools are unchanged; no scratch notebook is substituted.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def notebook_path(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "colab.research.google.com"
        or parsed.query or parsed.fragment
        or not re.fullmatch(r"/drive/[A-Za-z0-9_-]{10,150}", parsed.path)
    ):
        raise ValueError("Use an existing https://colab.research.google.com/drive/... notebook URL without query or fragment")
    return parsed.path


if __name__ == "__main__":
    import colab_mcp
    import colab_mcp.session

    config = Path(__file__).resolve().parents[1] / ".runtime/colab-bridge/connection.json"
    target = json.loads(config.read_text(encoding="utf-8"))["notebookUrl"]
    colab_mcp.session.SCRATCH_PATH = notebook_path(target)
    colab_mcp.main()

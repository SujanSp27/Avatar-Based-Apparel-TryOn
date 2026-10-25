"""Use the supplied logo unchanged; embed its monogram in an SVG favicon viewport."""
import base64
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    source = ROOT / "assets/logo.jpeg"
    public = ROOT / "frontend/public/brand"
    public.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, public / "vastraview.jpeg")
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    (public / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="100 50 510 510">'
        '<title>VastraView</title><rect x="100" y="50" width="510" height="510" fill="#fbf9f2"/>'
        f'<image width="1600" height="597" href="data:image/jpeg;base64,{encoded}"/></svg>', encoding="utf-8")

if __name__ == "__main__":
    main()

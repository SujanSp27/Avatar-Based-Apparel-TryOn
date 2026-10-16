"""Run inside the existing Colab runtime, not on the user's computer."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = "7c0f10af3f91ad4048fe9729c470a13ef905d25a"
MODEL = "7720683168567eb5a2a4c67f15116c6e29c83ded"
POSE = "548b5df25b84d9f4aac0611dfa1c2a7a12f15571"
PARSER = "1f80c34dbab321c5730dda5c3fea279fd3e97498"


def main():
    if sys.platform != "linux" or not list(Path("/dev").glob("nvidia[0-9]*")):
        raise RuntimeError("This installer runs only in the connected Colab GPU runtime.")
    root = Path("/content/formfit-online")
    root.mkdir(exist_ok=True)
    python = root / ".venv/bin/python"
    if not python.exists():
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError("This Colab runtime needs uv to seed its isolated Python environment.")
        subprocess.run([uv, "venv", "--system-site-packages", "--seed", "--python", sys.executable, str(root / ".venv")], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                    f"git+https://github.com/fashn-AI/fashn-vton-1.5.git@{SOURCE}",
                    "gradio==5.49.1", "fashn-human-parser==0.1.1", "transformers==4.49.0"], check=True)
    # Download pinned assets in the isolated interpreter. No local model loading.
    downloader = f'''
import hashlib,json
from pathlib import Path
from huggingface_hub import hf_hub_download,snapshot_download
root=Path({str(root)!r})
records=[]
for repo,revision,names,relative in [
 ("fashn-ai/fashn-vton-1.5",{MODEL!r},["model.safetensors"],"weights"),
 ("fashn-ai/DWPose",{POSE!r},["yolox_l.onnx","dw-ll_ucoco_384.onnx"],"weights/dwpose"),
 ("fashn-ai/fashn-human-parser",{PARSER!r},["config.json","model.safetensors"],"weights/parser")]:
 for name in names:
  path=Path(hf_hub_download(repo,filename=name,revision=revision,local_dir=str(root/relative)))
  digest=hashlib.sha256()
  with path.open("rb") as stream:
   for block in iter(lambda:stream.read(1024*1024),b""):digest.update(block)
  records.append({{"repository":repo,"revision":revision,"file":name,"sha256":digest.hexdigest()}})
(root/"weights-manifest.json").write_text(json.dumps(records,indent=2))
print("PINNED_WEIGHTS_READY",flush=True)
'''
    subprocess.run([str(python), "-c", downloader], check=True)
    with (root / "installed.lock.txt").open("w") as stream:
        subprocess.run([str(python), "-m", "pip", "freeze"], stdout=stream, check=True)
    (root / "setup-complete.json").write_text(json.dumps({"source": SOURCE, "model": MODEL}))
    print("ONLINE_WORKER_SETUP_COMPLETE", flush=True)


if __name__ == "__main__":
    main()

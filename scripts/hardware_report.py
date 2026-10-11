import json
import platform
import shutil
import subprocess
from pathlib import Path

import psutil
import torch

root = Path(__file__).resolve().parents[1]
try:
    gpu = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version",
            "--format=csv,noheader",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
except (FileNotFoundError, subprocess.TimeoutExpired):
    gpu = None
report = {
    "platform": platform.platform(),
    "python": platform.python_version(),
    "ramGB": round(psutil.virtual_memory().total / 1024**3, 2),
    "freeDiskGB": round(shutil.disk_usage(root).free / 1024**3, 2),
    "torchVersion": torch.__version__,
    "torchCudaAvailable": torch.cuda.is_available(),
    "nvidiaSmi": gpu,
    "inferenceDevice": "cpu",
    "reason": "MediaPipe Tasks runs CPU in this Windows baseline. CUDA torch install exhausted disk; CPU torch installed instead.",
}
# Execute an actual tensor operation to detect broken/partial PyTorch installations.
assert torch.equal(torch.ones(2, 2) @ torch.ones(2, 2), torch.full((2, 2), 2.0))
(root / "experiments/hardware.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))

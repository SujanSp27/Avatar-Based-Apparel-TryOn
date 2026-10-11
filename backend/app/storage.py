import json
import shutil
from pathlib import Path
from uuid import UUID


class AssetStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, run_id: str) -> Path:
        return self.root / str(UUID(run_id))

    def create(self, run_id: str) -> Path:
        folder = self.folder(run_id)
        folder.mkdir(exist_ok=False)
        return folder

    def url(self, run_id: str, name: str) -> str:
        path = self.folder(run_id) / name
        if not path.is_file() or path.parent != self.folder(run_id):
            raise FileNotFoundError(name)
        return f"/assets/{run_id}/{name}"

    def write_json(self, run_id: str, name: str, value: dict) -> None:
        (self.folder(run_id) / name).write_text(
            json.dumps(value, indent=2, allow_nan=False), encoding="utf-8"
        )

    def delete(self, run_id: str) -> None:
        target = self.folder(run_id).resolve()
        if target.parent != self.root or target == self.root:
            raise ValueError("Refusing deletion outside the asset root")
        if target.exists():
            shutil.rmtree(target)

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "sqlite:///./.runtime/tryon.db"
    asset_root: Path = ROOT / "data/processed"
    model_path: Path = ROOT / "assets/pose/pose_landmarker_full.task"
    online_vton_url: str = ""
    online_vton_token: str = ""
    online_vton_timeout: int = 180
    online_vton_steps: int = 20
    vton_root: Path = ROOT / "assets/vton"
    vton_device: str = "cpu"
    vton_conditioning: Literal["official", "reference-anchor"] = "reference-anchor"
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    max_upload_mb: int = 12
    admin_token: str = ""


settings = Settings()

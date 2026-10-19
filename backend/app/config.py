from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "sqlite:///./.runtime/tryon.db"
    asset_root: Path = ROOT / "data/processed"
    online_vton_url: str = ""
    online_vton_token: str = ""
    # Cold T4 generations currently exceed 180s. Keep recovery from aborting a
    # valid remote event; this timeout is not a latency or speed claim.
    online_vton_timeout: int = Field(default=600, ge=10, le=900)
    online_vton_steps: int = Field(default=20, ge=10, le=50)
    online_vton_input_encoding: Literal["lossless", "jpeg95"] = "lossless"
    online_connection_path: Path = ROOT / ".runtime/online-connection.json"
    online_auto_connect: bool = True
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    max_upload_mb: int = 12
    admin_token: str = ""


settings = Settings()

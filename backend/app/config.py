from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "sqlite:///./.runtime/tryon.db"
    asset_root: Path = ROOT / "data/processed"
    online_vton_url: str = ""
    online_vton_token: str = ""
    # Allow recovery of a valid event despite cold starts or network delays.
    # This timeout is not a latency target or a speed claim.
    online_vton_timeout: int = Field(default=600, ge=10, le=900)
    # Measured Colab research preset; see docs/online-performance.md for quality
    # limits. Cold starts and network latency are not a 30-second guarantee.
    online_vton_steps: int = Field(default=10, ge=10, le=50)
    online_vton_input_encoding: Literal["lossless", "jpeg95"] = "jpeg95"
    online_connection_path: Path = ROOT / ".runtime/online-connection.json"
    online_auto_connect: bool = True
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    max_upload_mb: int = 12
    admin_token: str = ""
    mongodb_uri: str = "mongodb://127.0.0.1:27018"
    mongodb_database: str = Field(default="formfit_measurements", pattern=r"^[a-zA-Z0-9_-]{1,63}$")
    measurement_model_path: Path = ROOT / "assets/pose/pose_landmarker_full.task"
    measurement_output_root: Path = ROOT / "data/processed/measurements"

    @field_validator("online_vton_steps")
    @classmethod
    def supported_inference_steps(cls, value: int) -> int:
        # BaseSettings reads environment values as strings. Parse the integer
        # before checking the worker's supported presets.
        if value not in (10, 15, 20, 30, 50):
            raise ValueError("ONLINE_VTON_STEPS must be 10, 15, 20, 30 or 50")
        return value


settings = Settings()

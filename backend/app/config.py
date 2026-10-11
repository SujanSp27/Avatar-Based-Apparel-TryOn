from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "sqlite:///./.runtime/tryon.db"
    asset_root: Path = ROOT / "data/processed"
    model_path: Path = ROOT / "assets/bodyModels/pose_landmarker_full.task"
    human_backend: str = "mediapipe_template"
    hmr2_root: str = ""
    hmr2_checkpoint: str = ""
    smpl_model_path: str = ""
    vton_root: Path = ROOT / "assets/vton"
    vton_device: str = "cuda"
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    max_upload_mb: int = 12
    admin_token: str = ""


settings = Settings()

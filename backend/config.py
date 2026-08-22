"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
import os


def _find_env_file() -> str:
    """Locate the .env file robustly, regardless of the current working dir.

    Historically ``env_file = ".env"`` was relative to CWD, so running
    ``python main.py`` from the ``backend/`` folder while the .env lived in the
    project root meant the file was never loaded (and the app silently fell
    back to the localhost default). We now search a few known locations and
    return an absolute path to the first one that exists.

    Search order:
      1. backend/.env            (next to this config.py)
      2. <project root>/.env     (one level up from backend/)
      3. ./.env                  (current working directory)
    """
    here = Path(__file__).resolve().parent            # .../backend
    candidates = [
        here / ".env",                                # backend/.env
        here.parent / ".env",                         # project-root/.env
        Path.cwd() / ".env",                          # wherever you launched from
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    # Fall back to the default name; pydantic will just use env vars/defaults.
    return ".env"


_ENV_FILE = _find_env_file()


class Settings(BaseSettings):
    """Main application settings."""

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 5000
    app_env: str = "development"
    app_secret_key: str = "change-this-in-production"

    # AWS Configuration
    aws_region: str = "ap-south-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # AWS Bedrock
    bedrock_model_id: str = "meta.llama3-70b-instruct-v1:0"
    bedrock_max_tokens: int = 512
    bedrock_temperature: float = 0.5
    bedrock_top_p: float = 0.9

    # AWS Polly
    polly_voice_id: str = "Aditi"
    polly_engine: str = "neural"
    polly_language_code: str = "en-IN"

    # AWS Transcribe
    transcribe_language_code: str = "en-IN"

    # Database (MySQL).
    # Default points at the EC2 MySQL server. Override via DATABASE_URL in .env
    # (use 127.0.0.1 if the backend runs on the same host as MySQL).
    # NOTE: the '@' in the password must be URL-encoded as %40.
    database_url: str = "mysql+asyncmy://appuser:StrongPassword%40123@13.201.70.108:3306/myapp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Face Recognition
    face_similarity_threshold: float = 0.6
    face_embedding_model: str = "buffalo_l"
    max_faces_per_frame: int = 10

    # Camera
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30

    # Avatar
    avatar_model_path: str = "./models/avatar"
    avatar_idle_video: str = "./assets/avatar_idle.mp4"

    # D-ID (real-human talking avatar via the Talks API).
    # Set DID_API_KEY in .env to enable. Never hardcode the key.
    # DID_SOURCE_URL must be a PUBLICLY reachable image of a REAL human face
    # (D-ID downloads it). A stylized/AI image may be rejected by face
    # detection — use a real headshot. If empty, D-ID uses a default presenter.
    did_api_key: Optional[str] = None
    did_source_url: str = ""
    did_api_base: str = "https://api.d-id.com"
    # Optional Microsoft/D-ID voice for the spoken audio in the generated video.
    # Indian English female by default to match the app's en-IN setting.
    did_voice_id: str = "en-IN-NeerjaNeural"

    @property
    def did_enabled(self) -> bool:
        return bool(self.did_api_key and self.did_api_key.strip())

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        # Absolute path resolved at import time so the .env is found no matter
        # which directory the process was started from.
        env_file = _ENV_FILE
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()

# Make it obvious at startup which .env was loaded and where the DB points,
# so a stale/misplaced .env (the classic "still localhost" bug) is easy to spot.
try:
    _db_host = settings.database_url.split("@")[-1]
    print(f"[config] Loaded env file: {_ENV_FILE}")
    print(f"[config] DATABASE target: {_db_host}")
    _k = (settings.did_api_key or "").strip()
    print(f"[config] D-ID enabled: {settings.did_enabled}" + (f" (key {_k[:6]}…)" if _k else " (no DID_API_KEY)"))
    if "DATABASE_URL=" in _db_host:
        print("[config] ⚠️  DATABASE_URL looks doubled — remove the extra 'DATABASE_URL=' prefix in your .env")
except Exception:
    pass

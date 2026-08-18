"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


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

    # Database (MySQL - localhost)
    database_url: str = "mysql+asyncmy://appuser:StrongPassword%40123@localhost:3306/myapp"

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

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

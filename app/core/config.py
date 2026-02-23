# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # -----------------
    # Database
    # -----------------
    postgres_user: str
    postgres_password: str
    postgres_db: str
    database_url: str

    # -----------------
    # MinIO
    # -----------------
    minio_endpoint: str
    minio_root_user: str
    minio_root_password: str
    minio_bucket: str
    storage_backend: str = "minio"

    # -----------------
    # Redis / Celery
    # -----------------
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str

    # -----------------
    # JWT
    # -----------------
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 60

    # -----------------
    # LLM
    # -----------------
    llm_provider: str = "mock"
    mock_llm_url: str
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3"
    aggregate_prompt: str = (
        "You are an assistant. Aggregate the following reviews into a concise summary "
        "covering overall sentiment, common praise, and common criticisms.\n\nReviews:\n{reviews}"
    )

    # -----------------
    # API
    # -----------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 👈 prevents “extra_forbidden” validation errors
    )


settings = Settings()

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
from enum import Enum


class LLMProviderType(str, Enum):
    """LLM Provider types for configuration."""
    BEDROCK = "bedrock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    # Application
    app_name: str = "RAG Agent Infrastructure API"
    app_env: str = "development"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Authentication
    secret_key: str = "your-secret-key-change-in-production"
    api_key: str = "your-api-key-change-in-production"
    access_token_expire_minutes: int = 30

    # LLM Provider Configuration
    llm_provider: LLMProviderType = LLMProviderType.BEDROCK
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # AWS Bedrock / General AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"

    # AWS Live Fetch
    aws_live_fetch_enabled: bool = True
    aws_live_fetch_cache_ttl: int = 300  # 5 minutes
    aws_default_regions: List[str] = ["us-east-1", "us-west-2"]

    # ChromaDB
    chroma_persist_directory: str = "./chroma_data"
    chroma_collection_name: str = "documents"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_session_db: int = 0
    session_default_ttl: int = 3600  # 1 hour

    # File Storage
    terraform_storage_path: str = "./terraform_data"
    max_terraform_upload_size_mb: int = 100

    # Document Processing
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_upload_size_mb: int = 50

    # Index-specific Chunking
    terraform_chunk_size: int = 1500
    terraform_chunk_overlap: int = 200
    memory_chunk_size: int = 500
    memory_chunk_overlap: int = 100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

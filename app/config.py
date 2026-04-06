# This project was developed with assistance from AI tools.

"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Service configuration loaded from environment variables."""

    cosmos_endpoint: str = "http://cosmos-reason2:8000/v1"
    cosmos_model: str = "nvidia/Cosmos-Reason2-8B"
    nemotron_endpoint: str = "http://nemotron-nano:8000/v1"
    nemotron_model: str = "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16"
    log_level: str = "info"
    request_timeout: float = 30.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

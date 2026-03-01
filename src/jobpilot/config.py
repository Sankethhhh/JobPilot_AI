from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    litellm_model: str = os.getenv(
        "LITELLM_MODEL",
        "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    )
    litellm_api_base: str | None = os.getenv("LITELLM_API_BASE")
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    scraper_timeout_seconds: int = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", "15"))
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "outputs"))
    db_path: Path = Path(os.getenv("DB_PATH", "data/jobpilot.db"))
    resume_path: Path = Path(os.getenv("RESUME_PATH", "data/resume.json"))
    log_path: Path = Path(os.getenv("LOG_PATH", "data/jobpilot.log"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    supported_countries: tuple[str, ...] = ("Germany", "Netherlands")


settings = Settings()

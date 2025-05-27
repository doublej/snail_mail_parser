from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    scan_dir: Path             # Directory to monitor for new files
    output_dir: Path           # Directory to write YAML/Markdown outputs
    max_inflight: int = 1
    llm_api_key: str
    llm_model: str = "openai/gpt-4o"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    scan_interval_s: int = 1  # Interval in seconds for the main loop's idle time
    session_timeout_s: int = 15  # default timeout (seconds) for idle sessions/documents

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )

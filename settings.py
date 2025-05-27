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

    # Facsimile Specific Settings
    facsimile_recipient_name: str = "CENTRAL RECORDS"
    facsimile_recipient_address: str = "123 ARCHIVE LANE"
    facsimile_recipient_city: str = "DATAVILLE, ST 01010"
    
    facsimile_sender_name: str = "MARGOT - AI DOCUMENT SORTER"
    facsimile_sender_title: str = "CHIEF ARCHIVIST"
    facsimile_sender_fax: str = "N/A (DIGITAL)"
    facsimile_sender_phone: str = "N/A (SYSTEM)"

    facsimile_subject_prefix: str = "DOCUMENT DIGEST"
    facsimile_closing_line: str = "END OF TRANSMISSION."
    facsimile_margot_flair: str = "PROCESSED WITH PRECISION AND PANACHE."
    facsimile_item_notes_placeholder: str = "No specific action notes." # Placeholder for item.notes
    facsimile_item_margot_comment_placeholder: str = "Content summarized by AI. Review original for full details." # Placeholder for item.margot_comment


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore'
    )

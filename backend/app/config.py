import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


def get_api_keys() -> List[str]:
    raw_keys = os.getenv("LLM_API_KEYS", "")
    if not raw_keys.strip():
        # Provide placeholder mock keys if none provided for local test
        return ["mock-key-1", "mock-key-2"]
    return [k.strip() for k in raw_keys.split(",") if k.strip()]


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///app.db")
    ALLOWED_ORIGINS: List[str] = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")
        if o.strip()
    ]
    ENABLE_FAILURE_SIMULATION: bool = (
        os.getenv("ENABLE_FAILURE_SIMULATION", "true").lower() in ("true", "1", "yes")
    )
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini/gemini-3.5-flash-lite")
    FALLBACK_MODELS: List[str] = [
        m.strip()
        for m in os.getenv("FALLBACK_MODELS", "gemini/gemini-3-flash-preview").split(",")
        if m.strip()
    ]
    DEFAULT_SYSTEM_PROMPT: str = os.getenv(
        "DEFAULT_SYSTEM_PROMPT", "You are a helpful and concise AI assistant."
    )

    @property
    def api_keys(self) -> List[str]:
        return get_api_keys()


settings = Settings()

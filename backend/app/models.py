from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("message cannot be empty after trimming whitespace")
        if len(trimmed) > 4000:
            raise ValueError("message length cannot exceed 4000 characters")
        return trimmed

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("session_id cannot be empty")
        if len(trimmed) > 128:
            raise ValueError("session_id length cannot exceed 128 characters")
        return trimmed


class ChatMetadata(BaseModel):
    resolution_source: str  # LIVE_INFERENCE or LLM_CACHE
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str] = None
    fallback_attempts: int = 0


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ChatMetadata


class HealthResponse(BaseModel):
    status: str
    keys_configured: int
    cache_enabled: bool


class SessionMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[SessionMessage]

from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    request_validation_exception_handler,
    http_exception_handler,
)

from app.config import settings
from app.database import (
    init_db,
    check_db_health,
    get_messages_for_llm,
    get_session_history,
    save_message,
)
from app.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SessionHistoryResponse,
)
from app.llm_gateway import execute_llm_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema on startup
    init_db()
    yield


app = FastAPI(
    title="Lyftr AI Gateway",
    description="LLM Chatbot with Key Failover and Response Caching",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS
    if settings.ALLOWED_ORIGINS != ["*"]
    else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # Uses FastAPI's default 422 JSON response with 'detail'
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(HTTPException)
async def custom_http_handler(request: Request, exc: HTTPException):
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Never return an HTML error page or stack trace
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"},
    )


@app.get("/health", response_model=HealthResponse)
async def get_health():
    """
    Returns 200 once app is running, DB is reachable, and key pool is loaded.
    """
    db_ok = check_db_health()
    keys_count = len(settings.api_keys)

    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unreachable",
        )

    return HealthResponse(
        status="ok",
        keys_configured=keys_count,
        cache_enabled=True,
    )


@app.post("/chat", response_model=ChatResponse)
async def post_chat(
    payload: ChatRequest,
    x_simulate_failure: Optional[str] = Header(None, alias="X-Simulate-Failure"),
):
    """
    Multi-turn chat endpoint with auto-fallback and response caching.
    Supports X-Simulate-Failure header for testing key resilience.
    """
    session_id = payload.session_id
    user_message = payload.message

    # 1. Build messages list for LiteLLM
    messages = []

    # System prompt: request-level override or default
    active_system_prompt = payload.system_prompt or settings.DEFAULT_SYSTEM_PROMPT
    if active_system_prompt and active_system_prompt.strip():
        messages.append({"role": "system", "content": active_system_prompt.strip()})

    # Retrieve prior conversation turns from SQLite (multi-turn context)
    past_messages = get_messages_for_llm(session_id)
    messages.extend(past_messages)

    # Append current user message
    messages.append({"role": "user", "content": user_message})

    # 2. Execute via LiteLLM gateway (handles failover and cache)
    reply, metadata = execute_llm_request(
        messages=messages,
        simulate_header=x_simulate_failure,
    )

    # 3. Only on success, persist user message and assistant reply to SQLite
    save_message(session_id=session_id, role="user", content=user_message)
    save_message(
        session_id=session_id,
        role="assistant",
        content=reply,
        metadata={
            "resolution_source": metadata.resolution_source,
            "model": metadata.model,
            "latency_ms": metadata.latency_ms,
            "input_tokens": metadata.input_tokens,
            "output_tokens": metadata.output_tokens,
        },
    )

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        metadata=metadata,
    )


@app.get(
    "/sessions/{session_id}/messages",
    response_model=SessionHistoryResponse,
    response_model_exclude_none=True,
)
async def get_session_messages(session_id: str):
    """
    Returns stored history of one session from SQLite, oldest first, without system prompt.
    Returns 404 if session does not exist.
    """
    history = get_session_history(session_id)
    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found",
        )

    return SessionHistoryResponse(
        session_id=session_id,
        messages=history,
    )

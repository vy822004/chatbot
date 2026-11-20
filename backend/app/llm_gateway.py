import os
import time
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException
import litellm
from litellm.caching.caching import Cache
from app.config import settings
from app.models import ChatMetadata

# Initialize LiteLLM in-memory cache
litellm.cache = Cache(type="local")
litellm.drop_params = True  # Ignore unsupported vendor parameters gracefully


def parse_simulation_header(
    header_val: Optional[str],
) -> Dict[str, int]:
    """
    Parses X-Simulate-Failure header.
    Format: comma-separated <key_id>=<status> pairs; * means every key.
    Example: 'key_1=429,key_2=500' -> {'key_1': 429, 'key_2': 500}
             '*=429' -> {'*': 429}
    Valid statuses: 429, 500, 502, 503
    """
    if not header_val or not settings.ENABLE_FAILURE_SIMULATION:
        return {}

    allowed_statuses = {429, 500, 502, 503}
    simulations: Dict[str, int] = {}

    parts = [p.strip() for p in header_val.split(",") if p.strip()]
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            try:
                status = int(v.strip())
                if status in allowed_statuses:
                    simulations[k] = status
            except ValueError:
                pass
    return simulations


def execute_llm_request(
    messages: List[Dict[str, str]],
    simulate_header: Optional[str] = None,
) -> Tuple[str, ChatMetadata]:
    """
    Executes completion across key pool with auto-fallback and caching.
    Returns (reply_text, ChatMetadata).
    Raises HTTPException(503, detail='all providers unavailable') if all fail.
    """
    start_time = time.perf_counter()
    sim_rules = parse_simulation_header(simulate_header)

    keys = settings.api_keys
    if not keys:
        keys = ["default-key"]

    fallback_attempts = 0
    is_simulation_active = bool(sim_rules)

    # If simulation is active and targets every key (*):
    if "*" in sim_rules:
        # All keys fail immediately
        raise HTTPException(
            status_code=503,
            detail="all providers unavailable",
        )

    for idx, key_value in enumerate(keys):
        key_id = f"key_{idx + 1}"

        # 1. Check if this key has a simulated failure
        if key_id in sim_rules:
            # Simulate failure on this key
            fallback_attempts += 1
            continue

        # 2. Attempt completion
        try:
            # Use mock_response if MOCK_LLM is enabled or in test mode
            kwargs: Dict[str, Any] = {
                "model": settings.LLM_MODEL,
                "messages": messages,
                "api_key": key_value,
            }

            if os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes"):
                kwargs["mock_response"] = (
                    f"Mock reply to: {messages[-1]['content']}"
                )

            # If simulation is active for SOME keys, bypass reading from cache
            # so we verify the actual fallback key (e.g. key_2) answering
            if is_simulation_active:
                kwargs["caching"] = False

            response = litellm.completion(**kwargs)

            # Check if this was a cache hit
            is_cache_hit = (
                getattr(response, "_hidden_params", {}).get("cache_hit") is True
            )

            latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))

            # Extract reply text
            reply = ""
            if response.choices and len(response.choices) > 0:
                reply = response.choices[0].message.content or ""

            # Extract tokens
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage") and response.usage:
                prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                completion_tokens = (
                    getattr(response.usage, "completion_tokens", 0) or 0
                )

            if is_cache_hit:
                # Cache hit: key_id is null, fallback_attempts is 0
                metadata = ChatMetadata(
                    resolution_source="LLM_CACHE",
                    model=settings.LLM_MODEL,
                    latency_ms=latency_ms,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    key_id=None,
                    fallback_attempts=0,
                )
            else:
                metadata = ChatMetadata(
                    resolution_source="LIVE_INFERENCE",
                    model=settings.LLM_MODEL,
                    latency_ms=latency_ms,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    key_id=key_id,
                    fallback_attempts=fallback_attempts,
                )

            return reply, metadata

        except Exception as e:
            # Key failed (rate limit 429, quota, 5xx, or network error)
            fallback_attempts += 1
            # Continue to next key in pool
            continue

    # If loop completed without returning, all keys failed
    raise HTTPException(
        status_code=503,
        detail="all providers unavailable",
    )

"""Admin endpoints — LLM config."""

from fastapi import APIRouter, Depends

from app.api.deps import require_instructor
from app.core.runtime_config import get_snapshot, update_config

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_instructor)])


@router.get("/llm-config")
def get_llm_config() -> dict:
    """Return current LLM configuration (API key masked)."""
    return get_snapshot()


@router.patch("/llm-config")
def patch_llm_config(payload: dict) -> dict:
    """Update LLM config.  Writes to .env and hot-reloads.

    Example body:
      {"mode": "live", "api_key": "sk-...", "model": "gpt-4o"}
    """
    allowed = {"mode", "api_key", "base_url", "model"}
    data = {k: v for k, v in payload.items() if k in allowed and v is not None}
    return update_config(data)

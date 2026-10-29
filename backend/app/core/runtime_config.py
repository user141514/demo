"""
Hot-reloadable LLM config — writes directly to .env, reloads settings in-process.

An explicit LLM_CONFIG_FILE may supply existing credentials without copying them.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"

LLM_KEYS = {
    "mode": "LLM_MODE",
    "api_key": "OPENAI_API_KEY",
    "base_url": "OPENAI_BASE_URL",
    "model": "OPENAI_MODEL",
}


def get_snapshot() -> dict:
    from app.core.config import settings

    key = settings.openai_api_key
    masked = ""
    if key:
        masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
    return {
        "mode": settings.llm_mode,
        "api_key": masked,
        "base_url": settings.openai_base_url,
        "model": settings.openai_model,
        "is_live": settings.llm_mode == "live" and bool(key) and bool(settings.openai_model),
        "llm_report_enabled": settings.llm_report_enabled,
    }


def update_config(data: dict) -> dict:
    """Write LLM keys to .env, hot-reload settings, return snapshot."""
    _write_env(data)
    _hot_reload(data)
    return get_snapshot()


def _write_env(data: dict) -> None:
    updates: dict[str, str] = {}
    for field, env_key in LLM_KEYS.items():
        if field in data and data[field] is not None:
            val = str(data[field]).strip()
            if val:
                updates[env_key] = val

    if not updates:
        return

    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    updated: set[str] = set()
    out: list[str] = []
    for line in lines:
        m = re.match(r"^([A-Z_]+)\s*=", line.strip())
        if m and m.group(1) in updates:
            out.append(f"{m.group(1)}={updates[m.group(1)]}")
            updated.add(m.group(1))
        else:
            out.append(line)

    for env_key, val in updates.items():
        if env_key not in updated:
            out.append(f"{env_key}={val}")

    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def _hot_reload(data: dict) -> None:
    from app.core.config import reload_settings
    for field, env_key in LLM_KEYS.items():
        if field in data and data[field] is not None and str(data[field]).strip():
            os.environ[env_key] = str(data[field]).strip()
    reload_settings()

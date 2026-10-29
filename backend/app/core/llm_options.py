from urllib.parse import urlsplit

from app.core.config import settings


def completion_options() -> dict:
    """Provider-specific options must not be sent to other compatible APIs."""
    if urlsplit(settings.openai_base_url).hostname != "api.deepseek.com":
        return {}
    enabled = getattr(settings, "deepseek_thinking_enabled", True)
    return {"extra_body": {"thinking": {"type": "enabled" if enabled else "disabled"}}}

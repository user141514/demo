"""Ordinary pytest runs must never inherit a developer's live API configuration."""
import os

os.environ.update({
    "RAG_ENABLED": "false",
    "LIGHTRAG_ENABLED": "false",
    "PAYMENT_PROVIDER_MODE": "mock",
    "SMTP_ENABLED": "false",
    "DATABASE_URL": "sqlite:///:memory:",
})

if os.getenv("RUN_LIVE_LLM_TESTS", "").strip().lower() != "true":
    os.environ.update({
        "LLM_MODE": "mock",
        "LLM_REPORT_ENABLED": "false",
        "LLM_CONFIG_FILE": "",
        "OPENAI_API_KEY": "offline-test-placeholder",
        "OPENAI_BASE_URL": "https://example.invalid/v1",
        "OPENAI_MODEL": "offline-test-model",
    })

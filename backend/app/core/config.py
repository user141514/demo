import os
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.security import resolve_jwt_secret

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"
DEFAULT_DATABASE_PATH = ROOT_DIR / "backend" / "data" / "meitai_demo.db"


def load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        cleaned_key = key.strip()
        cleaned_value = value.strip().strip('"').strip("'")
        # Explicit process settings own runtime isolation; .env supplies defaults.
        os.environ.setdefault(cleaned_key, cleaned_value)


def _load_mykey() -> dict:
    """Load LLM credentials from <project_root>/mykey.py (optional, .gitignored).

    Falls back gracefully if the file doesn't exist or can't be imported.
    """
    import importlib.util

    mykey_path = ROOT_DIR / "mykey.py"
    if not mykey_path.exists():
        return {}

    try:
        spec = importlib.util.spec_from_file_location("mykey", str(mykey_path))
        if spec is None or spec.loader is None:
            return {}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, "llm_config", {})
    except Exception:
        return {}


load_env_file(ENV_FILE)
_mykey = _load_mykey()


def _load_llm_config() -> dict:
    """Read credentials only from an explicitly selected existing JSON file."""
    configured_path = os.getenv("LLM_CONFIG_FILE", "").strip()
    if not configured_path:
        return {}
    path = Path(configured_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise ValueError("LLM_CONFIG_FILE is missing or is not valid JSON.") from None
    if not isinstance(data, dict):
        raise ValueError("LLM_CONFIG_FILE must contain a JSON object.")
    aliases = {"openai_api_key": "api_key", "openai_base_url": "base_url", "openai_model": "model"}
    return {key: str(data.get(key) or data.get(alias)).strip()
            for key, alias in aliases.items() if data.get(key) or data.get(alias)}


_llm_file = _load_llm_config()


def _resolve(key: str, env_key: str, default) -> str:
    """Process environment > .env > mykey.py > explicitly selected credential file > default."""
    env_val = os.getenv(env_key)
    if env_val is not None and env_val != "":
        return env_val.strip()
    val = _mykey.get(key)
    if val is not None and val != "":
        return str(val).strip()
    val = _llm_file.get(key)
    if val is not None and val != "":
        return str(val).strip()
    return default.strip() if isinstance(default, str) else default


def _resolve_bool(key: str, env_key: str, default: bool) -> bool:
    env_val = os.getenv(env_key)
    if env_val is not None and env_val != "":
        return env_val.strip().lower() == "true"
    val = _mykey.get(key)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() == "true"


def _resolve_int(key: str, env_key: str, default: int) -> int:
    env_val = os.getenv(env_key)
    if env_val is not None and env_val != "":
        return int(env_val)
    val = _mykey.get(key)
    return int(val) if val is not None else default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Meitai AI Business Innovation Agent API")
    app_env: str = os.getenv("APP_ENV", "development")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3001")
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}",
    )
    # Process environment > .env > mykey.py > default
    llm_mode: str = field(default_factory=lambda: _resolve("llm_mode", "LLM_MODE", "mock").strip().lower())
    openai_api_key: str = field(default_factory=lambda: _resolve("openai_api_key", "OPENAI_API_KEY", "").strip(), repr=False)
    openai_base_url: str = field(default_factory=lambda: _resolve("openai_base_url", "OPENAI_BASE_URL", "https://api.openai.com/v1").strip())
    openai_model: str = field(default_factory=lambda: _resolve("openai_model", "OPENAI_MODEL", "").strip())
    deepseek_thinking_enabled: bool = field(default_factory=lambda: _resolve_bool("deepseek_thinking_enabled", "DEEPSEEK_THINKING_ENABLED", True))
    # RAG settings
    rag_enabled: bool = os.getenv("RAG_ENABLED", "false").strip().lower() == "true"
    chroma_persist_dir: str = os.getenv(
        "CHROMA_PERSIST_DIR",
        str(ROOT_DIR / "backend" / "data" / "chroma"),
    )
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "5"))
    # LightRAG graph-enhanced retrieval (optional, replaces ChromaDB when enabled)
    lightrag_enabled: bool = (
        os.getenv("LIGHTRAG_ENABLED", "false").strip().lower() == "true"
    )
    lightrag_working_dir: str = os.getenv(
        "LIGHTRAG_WORKING_DIR",
        str(ROOT_DIR / "backend" / "data" / "lightrag"),
    )
    lightrag_top_k: int = int(os.getenv("LIGHTRAG_TOP_K", "5"))
    # LLM Report settings
    llm_report_enabled: bool = field(default_factory=lambda: _resolve_bool("llm_report_enabled", "LLM_REPORT_ENABLED", False))
    llm_report_timeout_seconds: int = field(default_factory=lambda: _resolve_int("llm_report_timeout_seconds", "LLM_REPORT_TIMEOUT_SECONDS", 60))
    # Intake import settings
    intake_max_upload_size_mb: int = int(os.getenv("INTAKE_MAX_UPLOAD_SIZE_MB", "10"))
    intake_pdf_ocr_enabled: bool = (
        os.getenv("INTAKE_PDF_OCR_ENABLED", "true").strip().lower() == "true"
    )
    intake_pdf_ocr_min_text_chars: int = int(
        os.getenv("INTAKE_PDF_OCR_MIN_TEXT_CHARS", "20")
    )
    intake_pdf_ocr_max_pages: int = int(os.getenv("INTAKE_PDF_OCR_MAX_PAGES", "12"))
    # JWT Auth settings
    jwt_secret_key: str = field(default=resolve_jwt_secret(
        _resolve("jwt_secret_key", "JWT_SECRET_KEY", ""),
        os.getenv("APP_ENV", "development"),
        Path(os.getenv("JWT_SECRET_FILE", str(ROOT_DIR / "backend" / "data" / ".jwt-secret"))),
    ), repr=False)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = _resolve_int("jwt_expire_minutes", "JWT_EXPIRE_MINUTES", 1440)
    # SMTP / password reset mail
    smtp_enabled: bool = _resolve_bool("smtp_enabled", "SMTP_ENABLED", False)
    smtp_host: str = _resolve("smtp_host", "SMTP_HOST", "").strip()
    smtp_port: int = _resolve_int("smtp_port", "SMTP_PORT", 587)
    smtp_username: str = _resolve("smtp_username", "SMTP_USERNAME", "").strip()
    smtp_password: str = _resolve("smtp_password", "SMTP_PASSWORD", "").strip()
    smtp_from_email: str = _resolve("smtp_from_email", "SMTP_FROM_EMAIL", "").strip()
    smtp_from_name: str = _resolve("smtp_from_name", "SMTP_FROM_NAME", "Meitai AI").strip()
    smtp_use_tls: bool = _resolve_bool("smtp_use_tls", "SMTP_USE_TLS", True)
    smtp_use_ssl: bool = _resolve_bool("smtp_use_ssl", "SMTP_USE_SSL", False)
    password_reset_url: str = _resolve("password_reset_url", "PASSWORD_RESET_URL", "").strip()
    # Payment / entitlement settings
    payment_provider_mode: str = _resolve("payment_provider_mode", "PAYMENT_PROVIDER_MODE", "mock").strip().lower()
    payment_amount_cents: int = _resolve_int("payment_amount_cents", "PAYMENT_AMOUNT_CENTS", 9900)
    payment_currency: str = _resolve("payment_currency", "PAYMENT_CURRENCY", "CNY").strip().upper()
    payment_order_expire_minutes: int = _resolve_int("payment_order_expire_minutes", "PAYMENT_ORDER_EXPIRE_MINUTES", 30)
    payment_notify_base_url: str = _resolve("payment_notify_base_url", "PAYMENT_NOTIFY_BASE_URL", "").strip()
    wechat_pay_app_id: str = _resolve("wechat_pay_app_id", "WECHAT_PAY_APP_ID", "").strip()
    wechat_pay_mch_id: str = _resolve("wechat_pay_mch_id", "WECHAT_PAY_MCH_ID", "").strip()
    wechat_pay_merchant_serial_no: str = _resolve("wechat_pay_merchant_serial_no", "WECHAT_PAY_MERCHANT_SERIAL_NO", "").strip()
    wechat_pay_merchant_private_key: str = _resolve("wechat_pay_merchant_private_key", "WECHAT_PAY_MERCHANT_PRIVATE_KEY", "").strip()
    wechat_pay_api_v3_key: str = _resolve("wechat_pay_api_v3_key", "WECHAT_PAY_API_V3_KEY", "").strip()
    wechat_pay_platform_public_key: str = _resolve("wechat_pay_platform_public_key", "WECHAT_PAY_PLATFORM_PUBLIC_KEY", "").strip()
    wechat_pay_api_base_url: str = _resolve("wechat_pay_api_base_url", "WECHAT_PAY_API_BASE_URL", "https://api.mch.weixin.qq.com").strip()
    alipay_app_id: str = _resolve("alipay_app_id", "ALIPAY_APP_ID", "").strip()
    alipay_private_key: str = _resolve("alipay_private_key", "ALIPAY_PRIVATE_KEY", "").strip()
    alipay_public_key: str = _resolve("alipay_public_key", "ALIPAY_PUBLIC_KEY", "").strip()
    alipay_gateway_url: str = _resolve("alipay_gateway_url", "ALIPAY_GATEWAY_URL", "https://openapi.alipay.com/gateway.do").strip()


settings = Settings()


def reload_settings() -> None:
    """Refresh LLM fields in place so consumers retain a current settings reference."""
    global _mykey, _llm_file
    load_env_file(ENV_FILE)
    _mykey = _load_mykey()
    _llm_file = _load_llm_config()
    refreshed = Settings()
    for name in ("llm_mode", "openai_api_key", "openai_base_url", "openai_model", "llm_report_enabled", "llm_report_timeout_seconds", "deepseek_thinking_enabled"):
        object.__setattr__(settings, name, getattr(refreshed, name))

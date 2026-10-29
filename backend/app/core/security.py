import os
from pathlib import Path
import secrets
from tempfile import NamedTemporaryFile


RETIRED_JWT_SECRET = "meitai-demo-dev-secret-change-in-prod"


def resolve_jwt_secret(value: str, app_env: str, secret_file: Path) -> str:
    if value:
        if value == RETIRED_JWT_SECRET or len(value) < 32:
            raise RuntimeError("JWT_SECRET_KEY must be a new random secret of at least 32 characters.")
        return value
    if app_env.lower() not in {"development", "dev", "test", "testing", "local"}:
        raise RuntimeError("Set JWT_SECRET_KEY before starting outside local development.")
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if not secret_file.exists():
        # Publish a complete file atomically; concurrent workers share the winner.
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=secret_file.parent, delete=False) as stream:
            staging = Path(stream.name)
            stream.write(secrets.token_urlsafe(48))
        try:
            os.link(staging, secret_file)
        except FileExistsError:
            pass
        finally:
            staging.unlink()
    secret = secret_file.read_text(encoding="utf-8").strip()
    if len(secret) < 32 or secret == RETIRED_JWT_SECRET:
        raise RuntimeError("The local JWT secret is invalid; configure JWT_SECRET_KEY explicitly.")
    return secret

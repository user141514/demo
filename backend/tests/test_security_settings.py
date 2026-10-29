from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.security import resolve_jwt_secret, RETIRED_JWT_SECRET


def test_development_secret_is_random_persisted_and_reused(tmp_path):
    path = tmp_path / 'local-secret'
    first = resolve_jwt_secret('', 'development', path)
    assert len(first) >= 32 and first != RETIRED_JWT_SECRET
    assert resolve_jwt_secret('', 'development', path) == first
    assert resolve_jwt_secret('', 'development', tmp_path / 'other-secret') != first


@pytest.mark.parametrize('value', ['', 'short', RETIRED_JWT_SECRET])
def test_production_rejects_missing_or_weak_secret(tmp_path, value):
    with pytest.raises(RuntimeError):
        resolve_jwt_secret(value, 'production', tmp_path / 'secret')
    assert not (tmp_path / 'secret').exists()


def test_explicit_secret_does_not_write_a_file(tmp_path):
    assert resolve_jwt_secret('a-new-secret-value-longer-than-32-characters', 'production', tmp_path / 'secret')
    assert not (tmp_path / 'secret').exists()

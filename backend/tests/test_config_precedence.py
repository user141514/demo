from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core import config

def test_selected_credential_file_is_read_without_enabling_live_mode(tmp_path, monkeypatch):
    import json
    path = tmp_path / "provider.json"
    path.write_text(json.dumps({"api_key": "fake-test-key", "base_url": "https://example.com/v1", "model": "test-model", "mode": "live"}), encoding="utf-8")
    monkeypatch.setenv("LLM_CONFIG_FILE", str(path))
    values = config._load_llm_config()
    assert values == {"openai_api_key": "fake-test-key", "openai_base_url": "https://example.com/v1", "openai_model": "test-model"}
    assert "llm_mode" not in values


def test_current_environment_is_evaluated_for_each_llm_settings_instance(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "new-test-model")
    monkeypatch.setenv("LLM_REPORT_ENABLED", "true")
    settings = config.Settings()
    assert settings.llm_mode == "live"
    assert settings.openai_model == "new-test-model"
    assert settings.llm_report_enabled is True


def test_selected_file_has_lower_precedence_than_explicit_environment(monkeypatch):
    monkeypatch.setattr(config, "_llm_file", {"openai_api_key": "file-test-key"}, raising=False)
    monkeypatch.setattr(config, "_mykey", {})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert config._resolve("openai_api_key", "OPENAI_API_KEY", "") == "file-test-key"
    monkeypatch.setenv("OPENAI_API_KEY", "process-test-key")
    assert config._resolve("openai_api_key", "OPENAI_API_KEY", "") == "process-test-key"


def test_runtime_update_refreshes_existing_settings_references(tmp_path, monkeypatch):
    from app.core import runtime_config
    path = tmp_path / "isolated.env"
    monkeypatch.setattr(runtime_config, "ENV_FILE", path)
    monkeypatch.setattr(config, "ENV_FILE", path)
    monkeypatch.setattr(config, "_mykey", {})
    monkeypatch.setattr(config, "_llm_file", {}, raising=False)
    monkeypatch.delenv("LLM_CONFIG_FILE", raising=False)
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("OPENAI_MODEL", "old-test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    monkeypatch.setattr(config, "settings", config.Settings())
    consumer_reference = config.settings
    snapshot = runtime_config.update_config({"mode": "live", "model": "new-test-model"})
    assert config.settings is consumer_reference
    assert consumer_reference.llm_mode == "live"
    assert consumer_reference.openai_model == "new-test-model"
    assert snapshot["is_live"] is True

def test_explicit_process_settings_win_over_env_file(tmp_path, monkeypatch):
    path = tmp_path / "isolated.env"
    path.write_text("DATABASE_URL=sqlite:///wrong.db\nLLM_MODE=live\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///isolated.db")
    monkeypatch.setenv("LLM_MODE", "mock")
    config.load_env_file(path)
    assert config.os.environ["DATABASE_URL"] == "sqlite:///isolated.db"
    assert config.os.environ["LLM_MODE"] == "mock"

def test_env_file_then_mykey_then_default(tmp_path, monkeypatch):
    path = tmp_path / "isolated.env"
    path.write_text("TEST_CONFIG_PRECEDENCE=file\n", encoding="utf-8")
    monkeypatch.delenv("TEST_CONFIG_PRECEDENCE", raising=False)
    monkeypatch.setattr(config, "_mykey", {"probe": "local"})
    config.load_env_file(path)
    assert config._resolve("probe", "TEST_CONFIG_PRECEDENCE", "default") == "file"
    monkeypatch.delenv("TEST_CONFIG_PRECEDENCE")
    assert config._resolve("probe", "TEST_CONFIG_PRECEDENCE", "default") == "local"
    monkeypatch.setattr(config, "_mykey", {})
    assert config._resolve("probe", "TEST_CONFIG_PRECEDENCE", "default") == "default"

def test_actual_imported_settings_and_engine_honor_isolated_process_environment(tmp_path):
    import os
    import subprocess
    target = tmp_path / "process-owned.db"
    environment = dict(os.environ, DATABASE_URL="sqlite:///" + target.as_posix(),
                       LLM_MODE="mock", RAG_ENABLED="false", LLM_REPORT_ENABLED="false")
    script = """
from pathlib import Path
import sys
from app.core.config import settings
from app.db.session import engine
assert Path(engine.url.database).resolve() == Path(sys.argv[1]).resolve()
assert settings.llm_mode == 'mock'
assert not settings.rag_enabled and not settings.llm_report_enabled
"""
    result = subprocess.run([sys.executable, "-c", script, str(target)], env=environment,
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr

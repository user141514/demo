from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core import llm_options


def test_deepseek_interactive_mode_can_disable_thinking(monkeypatch):
    monkeypatch.setattr(llm_options, "settings", SimpleNamespace(openai_base_url="https://api.deepseek.com", deepseek_thinking_enabled=False))
    assert llm_options.completion_options() == {"extra_body": {"thinking": {"type": "disabled"}}}


def test_thinking_option_does_not_leak_to_other_providers(monkeypatch):
    monkeypatch.setattr(llm_options, "settings", SimpleNamespace(openai_base_url="https://api.openai.com/v1", deepseek_thinking_enabled=False))
    assert llm_options.completion_options() == {}

from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import llm_report_writer, report_enrichment


def test_mock_mode_cannot_enable_a_live_report_with_the_report_flag(monkeypatch):
    monkeypatch.setattr(llm_report_writer, 'settings', SimpleNamespace(
        llm_mode='mock', llm_report_enabled=True, openai_api_key='fake-test-key', openai_model='fake-model'))
    mode, _ = llm_report_writer.LLMReportWriter()._resolve_mode('llm')
    assert mode == 'template'


def test_explicit_template_enrichment_never_calls_the_model(monkeypatch):
    monkeypatch.setattr(report_enrichment, 'settings', SimpleNamespace(
        llm_mode='live', llm_report_enabled=True, openai_api_key='fake-test-key', openai_model='fake-model'))
    service = report_enrichment.ReportEnrichmentService()
    monkeypatch.setattr(service, '_build_user_prompt', lambda *args: 'test prompt')
    monkeypatch.setattr(service, '_call_llm', lambda *args: (_ for _ in ()).throw(AssertionError('Unexpected paid call')))
    marker = object()
    monkeypatch.setattr(service, '_build_rule_based', lambda *args: marker)
    assert service.enrich(None, None, None, None, [], [], allow_llm=False) is marker

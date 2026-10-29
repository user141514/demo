from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from datetime import date
import re
import sys

import fitz as pymupdf
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas.assessment import ReportData, ReportDocumentResponse, ReportSectionData, ReportCardData, ReportTableData
from app.schemas.score import ScoreReportType, ScoreSubmissionInput
from app.services import report_service
from app.services.report_service import ReportService
from app.services.score_service import ScoreService
from app.exporters.pdf_exporter import render_html_pdf


@pytest.fixture
def chinese_report():
    sections = [ReportSectionData(
        key=f'section_{i}', title=f'第{i}章企业创新规划',
        content=f'正文验收标记{i}：客户需求与设备维护知识需要完整保留。',
        bullets=['明确责任人与验收标准'],
    ) for i in range(1, 15)]
    sections[0].cards = [ReportCardData(title='重点行动卡片', content='卡片正文也必须完整导出')]
    sections[1].table = ReportTableData(columns=['场景', '实施建议'], rows=[['智能客服', '沉淀设备知识库']])
    data = ReportData(title='华东制造 AI 商业创新报告', subtitle='中文正文导出验证',
                      company_name='华东制造有限公司', industry='装备制造', company_size='50-200人',
                      region='上海', annual_revenue_range='3000万-1亿', ai_readiness_score=70,
                      ai_readiness_summary='系统与数据基础待完善', generated_with='template', sections=sections)
    return ReportDocumentResponse(report_id='pdf-report', assessment_id='pdf-assessment', title=data.title,
                                  generation_mode='template', used_llm=False, used_rag=False,
                                  content_markdown='', content_html='', content_json=data, sections=sections)


def pdf_text(data):
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        # Exclude the page-number footer when joining a paragraph across pages.
        text = ''.join(page.get_text(clip=pymupdf.Rect(0, 0, page.rect.width, page.rect.height - 40)) for page in doc)
        return re.sub(r'\s+', '', text), len(doc)


def test_fallback_pdf_preserves_chinese_body_cards_and_tables(chinese_report):
    data = ReportService()._build_fallback_pdf_bytes(chinese_report)
    text, _ = pdf_text(data)
    assert '华东制造AI商业创新报告' in text
    for i in range(1, 15):
        assert f'正文验收标记{i}' in text
    assert '卡片正文也必须完整导出' in text
    assert '沉淀设备知识库' in text
    assert '????' not in text


def test_fallback_pdf_paginates_without_truncating_the_last_section(chinese_report):
    chinese_report.sections[0].content = '长篇正文必须跨页保留。' * 1500
    text, count = pdf_text(ReportService()._build_fallback_pdf_bytes(chinese_report))
    assert count > 1
    assert text.count('长篇正文必须跨页保留。') == 1500
    assert '正文验收标记14' in text


def test_old_cached_pdf_is_rebuilt_without_deleting_the_original(tmp_path, monkeypatch, chinese_report):
    import pdfkit
    old_path = tmp_path / 'old.pdf'
    old_data = ReportService()._build_fallback_pdf_bytes(chinese_report)
    old_path.write_bytes(old_data)
    record = SimpleNamespace(export_pdf_path=str(old_path))
    service = ReportService()
    monkeypatch.setattr(service, 'to_document_response', lambda _: chinese_report)
    monkeypatch.setattr(report_service, 'REPORT_EXPORT_DIR', tmp_path / 'new')
    render = Mock(side_effect=OSError('wkhtmltopdf unavailable'))
    monkeypatch.setattr(pdfkit, 'from_string', render)
    new_path = service.ensure_pdf_export(Mock(), record)
    assert new_path != old_path
    assert old_path.read_bytes() == old_data
    assert '正文验收标记14' in pdf_text(new_path.read_bytes())[0]
    assert service.ensure_pdf_export(Mock(), record) == new_path
    assert render.call_count == 1


def test_score_pdf_fallback_preserves_full_chinese_feedback():
    service = ScoreService()
    submission = ScoreSubmissionInput(name='张三', org='创新事业部', report_type=ScoreReportType.WEN_GU_ZHI_XIN,
                                      date=date(2026, 10, 27), note='本机PDF回归测试', transcript='目标、行动、结果与复盘。')
    llm = service._build_mock_llm_result(submission, '目标明确，行动具体，结果可验收。')
    result = service._build_result_payload(submission, llm)
    detail = SimpleNamespace(input=submission, result=result)
    text, _ = pdf_text(service._build_fallback_pdf_bytes(detail))
    assert '汇报评分报告' in text and '创新事业部' in text
    assert '各维度评分明细' in text and '本报告由AI智能体自动生成' in text


def test_pdf_keeps_light_web_text_readable_on_paper():
    data = render_html_pdf('<p style="color:#FFFFFF">中文可读性验证</p>')
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        spans = [span for block in doc[0].get_text('dict')['blocks'] if 'lines' in block
                 for line in block['lines'] for span in line['spans'] if '中文' in span['text']]
        assert spans and all(span['color'] != 0xFFFFFF for span in spans)


def test_pdf_does_not_skip_chapters_after_multi_page_cards(chinese_report):
    chinese_report.content_json.sections = [ReportSectionData(
        key=f's{i}', title=f'第{i}章完整性验收', content='正文需要完整导出。' * 10,
        bullets=['明确责任人与验收标准'] * 3,
        cards=[ReportCardData(
            title=f'第{j}个行动卡片', subtitle='方向说明', highlight='优先实施的创新机会',
            content='创新方向与落地行动。' * 60, bullets=['持续推进与复盘验证'] * 2,
        ) for j in range(3)],
    ) for i in range(1, 7)]
    text, pages = pdf_text(ReportService()._build_fallback_pdf_bytes(chinese_report))
    assert pages > 1
    for section in chinese_report.content_json.sections:
        assert section.title in text
    assert text.count('创新方向与落地行动。') == 6 * 3 * 60

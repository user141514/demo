import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR
from app.exporters.docx_exporter import DocxExporter
from app.exporters.html_exporter import HtmlExporter
from app.exporters.markdown_exporter import MarkdownExporter
from app.exporters.pdf_exporter import PDF_CACHE_VERSION, is_valid_pdf, render_html_pdf
from app.models.generated_report import GeneratedReport
from app.schemas.assessment import (
    ReportData,
    ReportDocumentResponse,
    ReportSummaryResponse,
)
from app.schemas.quality_guard import OverallQualityReport
from app.services.quality_checker import QualityChecker

REPORT_EXPORT_DIR = ROOT_DIR / "backend" / "exports" / "reports"

class ReportService:
    def __init__(self) -> None:
        self.markdown_exporter = MarkdownExporter()
        self.html_exporter = HtmlExporter()
        self.docx_exporter = DocxExporter()

    def save_report(
        self,
        db: Session,
        assessment_id: str,
        report_data: ReportData,
        generation_mode: str = "template",
        metadata: dict[str, Any] | None = None,
    ) -> ReportDocumentResponse:
        record = (
            db.query(GeneratedReport)
            .filter(GeneratedReport.assessment_id == assessment_id)
            .one_or_none()
        )
        if record is None:
            record = GeneratedReport(
                assessment_id=assessment_id,
                generation_mode=generation_mode,
                content_json="{}",
            )

        content_markdown = self.markdown_exporter.render(report_data)
        content_html = self.html_exporter.render_fragment(report_data)
        content_json = json.dumps(report_data.model_dump(mode="json"), ensure_ascii=False)
        normalized_metadata = self._normalize_metadata(metadata, generation_mode)

        record.title = report_data.title
        record.generation_mode = normalized_metadata["generation_mode"]
        record.used_llm = normalized_metadata["used_llm"]
        record.used_rag = normalized_metadata["used_rag"]
        record.warnings = json.dumps(normalized_metadata["warnings"], ensure_ascii=False)
        record.content_markdown = content_markdown
        record.content_html = content_html
        record.content_json = content_json
        record.export_markdown_path = None
        record.export_docx_path = None
        record.export_pdf_path = None

        quality = QualityChecker().audit(report_data)
        record.quality_json = json.dumps(quality.model_dump(), ensure_ascii=False)

        db.add(record)
        db.commit()
        db.refresh(record)
        return self.to_document_response(record)

    def get_report_or_404(self, db: Session, report_id: str) -> GeneratedReport:
        record = db.get(GeneratedReport, report_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )
        return record

    def get_report_summary_by_assessment(
        self,
        db: Session,
        assessment_id: str,
    ) -> ReportSummaryResponse | None:
        record = (
            db.query(GeneratedReport)
            .filter(GeneratedReport.assessment_id == assessment_id)
            .one_or_none()
        )
        if record is None:
            return None

        return ReportSummaryResponse(
            report_id=record.id,
            assessment_id=record.assessment_id,
            title=record.title or "未命名报告",
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def to_document_response(self, record: GeneratedReport) -> ReportDocumentResponse:
        report_data = self._load_report_data(record)
        metadata = self._record_metadata(record)
        content_markdown = record.content_markdown or self.markdown_exporter.render(report_data)
        content_html = record.content_html or self.html_exporter.render_fragment(report_data)

        return ReportDocumentResponse(
            report_id=record.id,
            assessment_id=record.assessment_id,
            title=record.title or report_data.title,
            generation_mode=metadata["generation_mode"],
            used_llm=metadata["used_llm"],
            used_rag=metadata["used_rag"],
            warnings=metadata["warnings"],
            content_markdown=content_markdown,
            content_html=content_html,
            content_json=report_data,
            sections=report_data.sections,
            export_markdown_path=record.export_markdown_path,
            export_docx_path=record.export_docx_path,
            export_pdf_path=record.export_pdf_path,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def ensure_markdown_export(self, db: Session, record: GeneratedReport) -> Path:
        if record.export_markdown_path:
            path = Path(record.export_markdown_path)
            if path.exists():
                return path

        response = self.to_document_response(record)
        filename = self._build_export_filename(
            response.content_json.company_name,
            response.assessment_id,
            response.report_id,
            "md",
        )
        path = REPORT_EXPORT_DIR / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self._render_markdown_with_metadata(response),
            encoding="utf-8",
        )

        record.export_markdown_path = str(path)
        db.add(record)
        db.commit()
        return path

    def ensure_docx_export(self, db: Session, record: GeneratedReport) -> Path:
        if record.export_docx_path:
            path = Path(record.export_docx_path)
            if path.exists():
                return path

        response = self.to_document_response(record)
        filename = self._build_export_filename(
            response.content_json.company_name,
            response.assessment_id,
            response.report_id,
            "docx",
        )
        path = REPORT_EXPORT_DIR / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        self.docx_exporter.export(
            response.content_json,
            path,
            metadata=self._export_metadata(response),
        )

        record.export_docx_path = str(path)
        db.add(record)
        db.commit()
        return path

    def build_print_html(self, record: GeneratedReport) -> str:
        report_data = self._load_report_data(record)
        metadata = self._record_metadata(record)
        return self.html_exporter.render_print_document(
            report_data,
            metadata=metadata,
        )

    def _load_report_data(self, record: GeneratedReport) -> ReportData:
        try:
            raw_payload = json.loads(record.content_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to parse stored report content.",
            ) from exc

        try:
            return ReportData.model_validate(raw_payload)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stored report content is invalid.",
            ) from exc

    def _normalize_metadata(
        self,
        metadata: dict[str, Any] | None,
        generation_mode: str,
    ) -> dict[str, Any]:
        base = {
            "generation_mode": generation_mode,
            "used_llm": False,
            "used_rag": False,
            "warnings": [],
        }
        if not metadata:
            return base

        warnings = metadata.get("warnings") or []
        if not isinstance(warnings, list):
            warnings = [str(warnings)]

        return {
            "generation_mode": str(metadata.get("generation_mode", generation_mode)),
            "used_llm": bool(metadata.get("used_llm", False)),
            "used_rag": bool(metadata.get("used_rag", False)),
            "warnings": [str(item) for item in warnings if str(item).strip()],
        }

    def _record_metadata(self, record: GeneratedReport) -> dict[str, Any]:
        return {
            "generation_mode": record.generation_mode or "template",
            "used_llm": bool(record.used_llm),
            "used_rag": bool(record.used_rag),
            "warnings": self._parse_warning_list(record.warnings),
        }

    def _parse_warning_list(self, raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return [raw_value]

        if not isinstance(parsed, list):
            return [str(parsed)]
        return [str(item) for item in parsed if str(item).strip()]

    def _render_markdown_with_metadata(self, response: ReportDocumentResponse) -> str:
        lines = [
            f"- generation_mode: {response.generation_mode}",
            f"- used_llm: {str(response.used_llm).lower()}",
            f"- used_rag: {str(response.used_rag).lower()}",
        ]
        if response.warnings:
            lines.append("- warnings:")
            lines.extend(f"  - {item}" for item in response.warnings)
        else:
            lines.append("- warnings: none")

        return "\n".join(lines) + "\n\n" + response.content_markdown

    def _export_metadata(self, response: ReportDocumentResponse) -> dict[str, Any]:
        return {
            "generation_mode": response.generation_mode,
            "used_llm": response.used_llm,
            "used_rag": response.used_rag,
            "warnings": response.warnings,
        }

    def _build_export_filename(
        self,
        company_name: str,
        assessment_id: str,
        report_id: str,
        extension: str,
    ) -> str:
        safe_company = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", company_name).strip("_")
        safe_company = safe_company or "report"
        return f"{safe_company}__{assessment_id}__{report_id}.{extension}"

    @staticmethod
    def _is_valid_pdf(path: Path) -> bool:
        return is_valid_pdf(path)

    def _build_fallback_pdf_bytes(self, response: ReportDocumentResponse) -> bytes:
        html = self.html_exporter.render_print_document(
            response.content_json, metadata=self._export_metadata(response),
        )
        return render_html_pdf(html, response.title)

    def ensure_pdf_export(self, db: Session, record: GeneratedReport) -> Path:
        # Old ASCII/heading-only exports must be rebuilt from the stored report.
        if record.export_pdf_path:
            cached = Path(record.export_pdf_path)
            if cached.name.endswith(f".{PDF_CACHE_VERSION}.pdf") and self._is_valid_pdf(cached):
                return cached

        response = self.to_document_response(record)
        html_content = self.html_exporter.render_print_document(
            response.content_json,
            metadata=self._export_metadata(response),
        )
        filename = self._build_export_filename(
            response.content_json.company_name,
            response.assessment_id,
            response.report_id,
            f"{PDF_CACHE_VERSION}.pdf",
        )
        path = REPORT_EXPORT_DIR / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import pdfkit
            options = {
                "encoding": "UTF-8",
                "page-size": "A4",
                "margin-top": "12mm",
                "margin-right": "12mm",
                "margin-bottom": "12mm",
                "margin-left": "12mm",
                "quiet": "",
            }
            pdfkit.from_string(html_content, str(path), options=options)
        except ImportError:
            path.write_bytes(self._build_fallback_pdf_bytes(response))
        except Exception as exc:
            # 生成失败时回退到内置 PDF 生成器，避免环境依赖导致导出不可用。
            if path.exists() and not self._is_valid_pdf(path):
                path.unlink(missing_ok=True)
            try:
                path.write_bytes(self._build_fallback_pdf_bytes(response))
            except Exception as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"PDF 导出生成失败：{fallback_exc}",
                ) from exc

        # 生成后校验 PDF 结构。
        if not self._is_valid_pdf(path):
            path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PDF 导出生成失败（文件无效）。",
            )

        record.export_pdf_path = str(path)
        db.add(record)
        db.commit()
        return path

    def generate_share_token(self, db: Session, record: GeneratedReport) -> str:
        import secrets
        if not record.share_token:
            record.share_token = secrets.token_urlsafe(16)
            db.add(record)
            db.commit()
        return record.share_token

    def get_enrichment(self, record: GeneratedReport) -> dict:
        if record.enrichment_json:
            try:
                return json.loads(record.enrichment_json)
            except json.JSONDecodeError:
                pass

        report_data = self._load_report_data(record)
        enrichment = _build_minimal_enrichment(report_data)
        return enrichment.model_dump(mode="json")

    def get_quality_report(self, record: GeneratedReport) -> dict:
        if record.quality_json:
            try:
                return json.loads(record.quality_json)
            except json.JSONDecodeError:
                pass

        report_data = self._load_report_data(record)
        quality = QualityChecker().audit(report_data)
        return quality.model_dump(mode="json")

    def save_enrichment(
        self,
        db: Session,
        record: GeneratedReport,
        enrichment,
    ) -> None:
        record.enrichment_json = json.dumps(enrichment.model_dump(mode="json"), ensure_ascii=False)
        db.add(record)
        db.commit()


def _build_minimal_enrichment(report_data):
    from app.schemas.report_enrichment import (
        ExecutiveSummary,
        IndustryBenchmark,
        InstructorComment,
        ReportEnrichmentResult,
        RoiFramework,
    )
    sections = {s.key: s for s in report_data.sections}
    comp = sections.get("competitiveness")

    exec_summary = ExecutiveSummary(
        headline=report_data.title[:40],
        key_findings=["报告已生成", "各项分析已完成"],
        top_3_recommendations=["请查看报告正文"],
        readiness_verdict="待评议",
    )
    benchmark = IndustryBenchmark(
        industry=report_data.industry,
        industry_avg_score=50,
        peer_company_size=report_data.company_size,
        peer_avg_score=50,
        percentile_rank=50,
        key_gap="待补充",
        advantage="待补充",
    )
    roi = RoiFramework(
        confidence_level="预估",
        low_investment_scenarios=[],
        medium_investment_scenarios=[],
        high_investment_scenarios=[],
        roi_time_horizon="3-12个月",
    )
    instructor = InstructorComment(
        comment_mode="rule_based",
        overall_assessment=comp.content[:200] if comp else "待讲师补充点评。",
        strength_points=[],
        risk_warnings=[],
        next_steps_advice="建议与讲师沟通后补充下一步行动建议。",
        recommended_reading=[],
    )

    return ReportEnrichmentResult(
        executive_summary=exec_summary,
        industry_benchmark=benchmark,
        roi_framework=roi,
        instructor_comment=instructor,
    )

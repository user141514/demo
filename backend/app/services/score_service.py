from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR, settings
from app.exporters.pdf_exporter import PDF_CACHE_VERSION, is_valid_pdf, render_html_pdf
from app.core.llm_options import completion_options
from app.models.score_record import ScoreRecord
from app.models.user import User
from app.prompts.score_writer_prompt import ScoreWriterPrompt
from app.schemas.intake import IntakeSourceFile
from app.schemas.score import (
    ScoreCreateResponse,
    ScoreDetailResponse,
    ScoreDimensionResult,
    ScoreExportFormat,
    ScoreExportMetadata,
    ScoreLLMDimensionResult,
    ScoreLLMResult,
    ScoreLevelLabel,
    ScoreRecordResponse,
    ScoreReportType,
    ScoreResultPayload,
    ScoreRubricSnapshot,
    ScoreSubmissionInput,
    build_score_disclaimer,
    ensure_llm_dimensions_match_rubric,
    get_score_rubric,
    infer_level_label,
)
from app.services.intake_service import IntakeService

SCORE_EXPORT_DIR = ROOT_DIR / "backend" / "exports" / "score"


class ScoreService:
    async def create_score(
        self,
        db: Session,
        current_user: User,
        submission: ScoreSubmissionInput,
        pdf_file: UploadFile,
    ) -> ScoreCreateResponse:
        source_file, document_text = await self._extract_pdf_text(pdf_file)
        llm_result = self._score_submission(submission, document_text)
        result = self._build_result_payload(submission, llm_result)
        markdown = self.render_markdown(submission, result)

        record = ScoreRecord(
            user_id=current_user.id,
            name=submission.name,
            org=submission.org,
            report_type=self._report_type_text(submission.report_type),
            scoring_date=submission.date,
            note=submission.note,
            source_pdf_name=source_file.name,
            source_pdf_size_bytes=source_file.size_bytes,
            document_text=document_text,
            transcript_text=submission.transcript,
            rubric_json=json.dumps(
                ScoreRubricSnapshot.from_report_type(submission.report_type).model_dump(
                    mode="json"
                ),
                ensure_ascii=False,
            ),
            llm_raw_json=json.dumps(llm_result.model_dump(mode="json"), ensure_ascii=False),
            result_json=json.dumps(result.model_dump(mode="json"), ensure_ascii=False),
            content_markdown=markdown,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return ScoreCreateResponse(
            score_id=record.id,
            total_score=result.total_score,
            dimensions=result.dimensions,
            overall_comment=result.overall_comment,
            created_at=record.created_at,
        )

    async def _extract_pdf_text(
        self,
        pdf_file: UploadFile,
    ) -> tuple[IntakeSourceFile, str]:
        source_file, document_text, _warnings = await IntakeService().extract_upload_file(pdf_file)
        if source_file.kind != "pdf":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="pdf_file must be a PDF document.",
            )
        return source_file, document_text

    def _score_submission(
        self,
        submission: ScoreSubmissionInput,
        document_text: str,
    ) -> ScoreLLMResult:
        if settings.llm_mode == "live" and settings.openai_api_key and settings.openai_model:
            return self._score_with_live_llm(submission, document_text)
        return self._build_mock_llm_result(submission, document_text)

    def _score_with_live_llm(
        self,
        submission: ScoreSubmissionInput,
        document_text: str,
    ) -> ScoreLLMResult:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        timeout = getattr(settings, "llm_report_timeout_seconds", 60)
        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                **completion_options(),
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": ScoreWriterPrompt.build_system_prompt(
                            submission.report_type
                        ),
                    },
                    {
                        "role": "user",
                        "content": ScoreWriterPrompt.build_user_prompt(
                            document_text=document_text,
                            transcript_text=submission.transcript,
                        ),
                    },
                ],
                timeout=timeout,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Live scoring request failed: {exc}",
            ) from exc

        raw_content = response.choices[0].message.content or ""
        try:
            payload = json.loads(self._extract_json_object(raw_content))
            llm_result = ScoreLLMResult.model_validate(payload)
            llm_result.dimensions = ensure_llm_dimensions_match_rubric(
                submission.report_type,
                llm_result.dimensions,
            )
            return llm_result
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Live scoring response is invalid: {exc}",
            ) from exc

    def _build_mock_llm_result(
        self,
        submission: ScoreSubmissionInput,
        document_text: str,
    ) -> ScoreLLMResult:
        rubric = get_score_rubric(submission.report_type)
        dimensions: list[ScoreLLMDimensionResult] = []
        for definition in rubric.dimensions:
            if (
                definition.material_source == "录音转写"
                and not submission.transcript.strip()
            ):
                dimensions.append(
                    ScoreLLMDimensionResult(
                        id=definition.id,
                        name=definition.name,
                        level=definition.level_name,
                        material_source=definition.material_source,
                        score=None,
                        level_label=ScoreLevelLabel.NOT_SCORED,
                        evidence="录音材料未提供",
                        comment="缺少录音转写文本，暂无法完成该维度评分。",
                    )
                )
                continue

            source_text = (
                submission.transcript
                if definition.material_source == "录音转写"
                else document_text
            )
            score = self._heuristic_score(source_text, definition.id)
            dimensions.append(
                ScoreLLMDimensionResult(
                    id=definition.id,
                    name=definition.name,
                    level=definition.level_name,
                    material_source=definition.material_source,
                    score=score,
                    level_label=infer_level_label(score),
                    evidence=self._build_mock_evidence(source_text),
                    comment=self._build_mock_comment(definition.name, score),
                )
            )

        llm_result = ScoreLLMResult(
            report_type=submission.report_type,
            dimensions=dimensions,
            overall_comment=self._build_mock_overall_comment(
                submission.report_type,
                dimensions,
            ),
        )
        llm_result.dimensions = ensure_llm_dimensions_match_rubric(
            submission.report_type,
            llm_result.dimensions,
        )
        return llm_result

    def _build_result_payload(
        self,
        submission: ScoreSubmissionInput,
        llm_result: ScoreLLMResult,
    ) -> ScoreResultPayload:
        rubric = get_score_rubric(submission.report_type)
        weight_by_id = {item.id: item for item in rubric.dimensions}
        dimensions: list[ScoreDimensionResult] = []
        for item in llm_result.dimensions:
            definition = weight_by_id[item.id]
            weighted_score = (
                0.0
                if item.score is None
                else round(item.score * definition.weight_pct / 10.0, 1)
            )
            dimensions.append(
                ScoreDimensionResult(
                    id=item.id,
                    name=item.name,
                    level_name=definition.level_name,
                    material_source=definition.material_source,
                    weight_pct=definition.weight_pct,
                    score=item.score,
                    weighted_score=weighted_score,
                    level_label=item.level_label,
                    evidence=item.evidence,
                    comment=item.comment,
                )
            )

        total_score = round(sum(item.weighted_score for item in dimensions), 1)
        strengths, improvements = self._derive_strengths_and_improvements(dimensions)
        return ScoreResultPayload(
            report_type=submission.report_type,
            total_score=total_score,
            dimensions=dimensions,
            overall_comment=llm_result.overall_comment,
            strengths=strengths,
            improvements=improvements,
            disclaimer=build_score_disclaimer(),
            transcript_provided=bool(submission.transcript.strip()),
        )

    def get_score_or_404(
        self,
        db: Session,
        score_id: str,
        current_user: User,
    ) -> ScoreRecord:
        record = db.get(ScoreRecord, score_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Score record not found.",
            )
        if current_user.role != "instructor" and record.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this score record.",
            )
        return record

    def to_detail_response(self, record: ScoreRecord) -> ScoreDetailResponse:
        submission = ScoreSubmissionInput(
            name=record.name,
            org=record.org,
            report_type=ScoreReportType(record.report_type),
            date=record.scoring_date,
            note=record.note,
            transcript=record.transcript_text,
        )
        result_payload = ScoreResultPayload.model_validate(json.loads(record.result_json))
        return ScoreDetailResponse(
            score_id=record.id,
            input=submission,
            result=result_payload,
            created_at=record.created_at,
            updated_at=record.updated_at,
            export_markdown_path=record.export_markdown_path,
            export_pdf_path=record.export_pdf_path,
        )

    def to_record_response(self, record: ScoreRecord) -> ScoreRecordResponse:
        detail = self.to_detail_response(record)
        return ScoreRecordResponse(
            score_id=record.id,
            name=detail.input.name,
            org=detail.input.org,
            report_type=detail.input.report_type,
            date=detail.input.date,
            note=detail.input.note,
            total_score=detail.result.total_score,
            dimensions=detail.result.dimensions,
            overall_comment=detail.result.overall_comment,
            strengths=detail.result.strengths,
            improvements=detail.result.improvements,
            created_at=detail.created_at,
        )

    def render_markdown(
        self,
        submission: ScoreSubmissionInput,
        result: ScoreResultPayload,
    ) -> str:
        grouped: dict[str, list[ScoreDimensionResult]] = {}
        level_weights: dict[str, float] = {}
        for dimension in result.dimensions:
            grouped.setdefault(dimension.level_name, []).append(dimension)
            level_weights[dimension.level_name] = level_weights.get(
                dimension.level_name, 0.0
            ) + dimension.weight_pct

        lines = [
            "# 汇报评分报告",
            "",
            "## 被评价人信息",
            "| 字段 | 内容 |",
            "|------|------|",
            f"| 姓名 | {submission.name} |",
            f"| 所属组织/部门 | {submission.org} |",
            f"| 汇报类型 | {self._report_type_text(submission.report_type)} |",
            f"| 评分日期 | {submission.date.isoformat()} |",
        ]
        if submission.note:
            lines.append(f"| 备注 | {submission.note} |")
        lines.extend(
            [
                "",
                "---",
                "",
                "## 总分",
                f"**{result.total_score:.1f} 分**（满分100分）",
                "",
                "## 总评",
                result.overall_comment,
                "",
                "---",
                "",
                "## 各维度评分明细",
            ]
        )

        for level_name, items in grouped.items():
            lines.extend(
                [
                    f"### 一级维度：{level_name}（权重{level_weights[level_name]:.1f}%）",
                    "",
                ]
            )
            for item in items:
                score_text = "未评分" if item.score is None else f"{item.score:.1f} 分"
                lines.extend(
                    [
                        f"#### {item.name}　{score_text} · {self._level_label_text(item.level_label)}",
                        f"**评分依据：** {item.evidence}",
                        f"**维度评价：** {item.comment}",
                        "",
                    ]
                )

        lines.extend(
            [
                "---",
                "",
                "## 结论与建议",
                "",
                "### 优势亮点",
            ]
        )
        lines.extend([f"- {item}" for item in result.strengths] or ["- 暂无"])
        lines.extend(["", "### 改进方向"])
        lines.extend([f"- {item}" for item in result.improvements] or ["- 暂无"])
        lines.extend(
            [
                "",
                "---",
                f"*{result.disclaimer}*",
                f"*生成时间：{recorded_now_iso()}*",
            ]
        )
        return "\n".join(lines)

    def ensure_export(
        self,
        db: Session,
        record: ScoreRecord,
        export_format: ScoreExportFormat,
    ) -> tuple[Path, ScoreExportMetadata]:
        detail = self.to_detail_response(record)
        filename_base = self._build_export_filename(
            detail.input.name,
            detail.input.report_type,
            detail.input.date.isoformat(),
        )
        SCORE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        if export_format == ScoreExportFormat.MARKDOWN:
            path = (
                Path(record.export_markdown_path)
                if record.export_markdown_path
                else SCORE_EXPORT_DIR / f"{filename_base}.md"
            )
            path.write_text(record.content_markdown, encoding="utf-8")
            record.export_markdown_path = str(path)
            db.add(record)
            db.commit()
            return path, ScoreExportMetadata(
                file_name=path.name,
                media_type="text/markdown; charset=utf-8",
                extension="md",
            )

        path = SCORE_EXPORT_DIR / f"{filename_base}_{record.id}.{PDF_CACHE_VERSION}.pdf"
        html = self._build_score_html(detail)
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
            pdfkit.from_string(html, str(path), options=options)
        except ImportError:
            path.write_bytes(self._build_fallback_pdf_bytes(detail))
        except Exception as exc:
            if path.exists():
                path.unlink(missing_ok=True)
            try:
                path.write_bytes(self._build_fallback_pdf_bytes(detail))
            except Exception as fallback_exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"PDF export failed: {fallback_exc}",
                ) from exc

        if not self._is_valid_pdf(path):
            path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PDF export failed because the generated file is invalid.",
            )

        record.export_pdf_path = str(path)
        db.add(record)
        db.commit()
        return path, ScoreExportMetadata(
            file_name=path.name,
            media_type="application/pdf",
            extension="pdf",
        )

    def _build_export_filename(
        self,
        name: str,
        report_type: ScoreReportType,
        date_text: str,
    ) -> str:
        safe_name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", name).strip("_") or "score"
        safe_type = re.sub(
            r"[^0-9A-Za-z\u4e00-\u9fff_-]+",
            "_",
            self._report_type_text(report_type),
        ).strip("_")
        safe_date = re.sub(r"[^0-9-]+", "_", date_text).strip("_")
        return f"{safe_name}_{safe_type}_{safe_date}"

    @staticmethod
    def _report_type_text(report_type: ScoreReportType | str) -> str:
        return report_type.value if hasattr(report_type, "value") else str(report_type)

    @staticmethod
    def _level_label_text(level_label: ScoreLevelLabel | str) -> str:
        return level_label.value if hasattr(level_label, "value") else str(level_label)

    def _derive_strengths_and_improvements(
        self,
        dimensions: list[ScoreDimensionResult],
    ) -> tuple[list[str], list[str]]:
        scored = [item for item in dimensions if item.score is not None]
        if not scored:
            return ["暂无足够材料提炼优势亮点。"], ["请补充完整材料后重新评分。"]
        strengths = [
            f"{item.name}：{item.comment}"
            for item in sorted(
                scored,
                key=lambda value: (value.score or 0.0),
                reverse=True,
            )[:3]
        ]
        improvements = [
            f"{item.name}：{item.comment}"
            for item in sorted(scored, key=lambda value: (value.score or 0.0))[:3]
        ]
        return strengths, improvements

    def _heuristic_score(self, source_text: str, seed: int) -> float:
        cleaned = source_text.strip()
        if not cleaned:
            return 5.0
        char_count = len(re.sub(r"\s+", "", cleaned))
        sentence_count = max(1, len(re.findall(r"[。！？.!?；;]", cleaned)))
        keyword_bonus = sum(
            0.2
            for keyword in ("目标", "问题", "行动", "结果", "复盘", "改进", "创新", "规划")
            if keyword in cleaned
        )
        base = 5.6 + min(char_count / 600.0, 2.0) + min(sentence_count / 12.0, 1.0)
        modulation = ((seed % 5) - 2) * 0.25
        score = max(4.0, min(9.6, base + keyword_bonus + modulation))
        return round(score, 1)

    def _build_mock_evidence(self, source_text: str) -> str:
        snippets = re.split(r"[。！？.!?；;\n]+", source_text.strip())
        cleaned = [item.strip() for item in snippets if item.strip()]
        if not cleaned:
            return "材料内容较少，证据提取有限。"
        return truncate(cleaned[0], 80)

    def _build_mock_comment(self, dimension_name: str, score: float) -> str:
        if score >= 8.5:
            prefix = "该维度表现较强"
        elif score >= 7.0:
            prefix = "该维度整体较稳"
        elif score >= 6.0:
            prefix = "该维度基本达标"
        else:
            prefix = "该维度仍有明显提升空间"
        return truncate(
            f"{prefix}，在“{dimension_name}”上已有一定支撑，但还可继续补充更具体的证据与行动闭环。",
            120,
        )

    def _build_mock_overall_comment(
        self,
        report_type: ScoreReportType,
        dimensions: list[ScoreLLMDimensionResult],
    ) -> str:
        report_type_text = self._report_type_text(report_type)
        scored = [item for item in dimensions if item.score is not None]
        if not scored:
            return (
                f"{report_type_text}材料尚不完整，当前仅完成基础结构校验，"
                "建议补齐材料后重新评分。"
            )
        highest = max(scored, key=lambda item: item.score or 0.0)
        lowest = min(scored, key=lambda item: item.score or 0.0)
        return (
            f"本次{report_type_text}整体完成度较为稳定，优势主要体现在“{highest.name}”，"
            f"说明提交材料在相关论述上已有一定支撑；主要改进方向集中在“{lowest.name}”，"
            "建议补充更具体的证据、行动路径与结果闭环，以提升整体说服力。"
        )

    def _build_score_html(self, detail: ScoreDetailResponse) -> str:
        markdown = self.render_markdown(detail.input, detail.result)
        escaped = (
            markdown.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            "<html><head><meta charset='utf-8' />"
            "<style>body{font-family:Arial,'Microsoft YaHei',sans-serif;padding:24px;line-height:1.7;white-space:pre-wrap;}</style>"
            "</head><body>"
            f"{escaped}"
            "</body></html>"
        )

    @staticmethod
    def _is_valid_pdf(path: Path) -> bool:
        return is_valid_pdf(path)

    def _build_fallback_pdf_bytes(self, detail: ScoreDetailResponse) -> bytes:
        return render_html_pdf(self._build_score_html(detail), "汇报评分报告")

    @staticmethod
    def _extract_json_object(content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        fenced_match = re.search(r"```json\s*(\{.*\})\s*```", stripped, re.DOTALL)
        if fenced_match:
            return fenced_match.group(1)
        generic_match = re.search(r"(\{.*\})", stripped, re.DOTALL)
        if generic_match:
            return generic_match.group(1)
        raise ValueError("LLM response did not contain a valid JSON object.")


def truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


def recorded_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

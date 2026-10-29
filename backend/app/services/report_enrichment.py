"""W8 Report Enrichment Service: 执行摘要/行业对标/ROI框架/讲师点评

All methods support LLM-first generation with rule-based fallback.
"""

import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.core.llm_options import completion_options
from app.models.assessment import Assessment
from app.schemas.assessment import (
    CanvasDiagnosisResult,
    CompanyProfileResult,
    ScenarioRecommendationResult,
)
from app.schemas.report_enrichment import (
    ExecutiveSummary,
    IndustryBenchmark,
    InstructorComment,
    ReportEnrichmentResult,
    RoiFramework,
)

logger = logging.getLogger(__name__)

ENRICHMENT_SYSTEM = """
你是一位资深企业战略顾问，正在为一份AI创新报告提供增值内容。

任务：基于企业数据和诊断结果，生成 4 部分增值内容。

输出 JSON 格式：
{
  "executive_summary": {
    "headline": "核心结论（一句话，不超过40字）",
    "key_findings": ["发现1", "发现2", "发现3"],
    "top_3_recommendations": ["建议1", "建议2", "建议3"],
    "readiness_verdict": "成熟度判断（高/中/低）"
  },
  "industry_benchmark": {
    "industry": "行业名称",
    "industry_avg_score": 55,
    "peer_company_size": "200-500人",
    "peer_avg_score": 52,
    "percentile_rank": 65,
    "key_gap": "与同行业相比的核心差距",
    "advantage": "相对于同行的优势"
  },
  "roi_framework": {
    "confidence_level": "预估",
    "low_investment_scenarios": [{"name": "场景名", "investment": "投入描述", "expected_return": "预期回报"}],
    "medium_investment_scenarios": [{"name": "场景名", "investment": "投入描述", "expected_return": "预期回报"}],
    "high_investment_scenarios": [{"name": "场景名", "investment": "投入描述", "expected_return": "预期回报"}],
    "roi_time_horizon": "3-12个月"
  },
  "instructor_comment": {
    "comment_mode": "llm",
    "overall_assessment": "总体评价...",
    "strength_points": ["优势1", "优势2", "优势3"],
    "risk_warnings": ["风险1", "风险2"],
    "next_steps_advice": "下一步建议...",
    "recommended_reading": ["推荐阅读1", "推荐阅读2"]
  }
}

注意：不编造具体ROI百分比数字，使用定性表述。
""".strip()


class ReportEnrichmentService:
    def __init__(self) -> None:
        self._client = None

    @property
    def _openai_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        return self._client

    def _is_live_mode(self) -> bool:
        return settings.llm_mode == "live" and bool(settings.openai_api_key) and bool(settings.openai_model)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        try:
            response = self._openai_client.chat.completions.create(
                model=settings.openai_model,
                **completion_options(),
                temperature=0.5,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=90,
            )
            raw = response.choices[0].message.content or ""
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            return json.loads(match.group(0) if match else raw)
        except Exception as exc:
            logger.warning("LLM enrichment call failed: %s", exc)
            return None

    def enrich(
        self,
        assessment: Assessment,
        profile: CompanyProfileResult,
        canvas: CanvasDiagnosisResult,
        scenarios: ScenarioRecommendationResult,
        breakthrough_keys: list[str],
        direction_labels: list[str] | None,
        competitiveness_result=None,
        allow_llm: bool = True,
    ) -> ReportEnrichmentResult:
        user_prompt = self._build_user_prompt(
            assessment, profile, canvas, scenarios,
            breakthrough_keys, direction_labels, competitiveness_result,
        )

        if allow_llm and self._is_live_mode() and getattr(settings, "llm_report_enabled", False):
            llm_result = self._call_llm(ENRICHMENT_SYSTEM, user_prompt)
            if llm_result:
                try:
                    return self._parse_llm_result(llm_result)
                except Exception as exc:
                    logger.warning("LLM enrichment parse failed: %s", exc)

        return self._build_rule_based(
            assessment, profile, canvas, scenarios,
            breakthrough_keys, direction_labels,
        )

    def _build_user_prompt(
        self,
        assessment: Assessment,
        profile: CompanyProfileResult,
        canvas: CanvasDiagnosisResult,
        scenarios: ScenarioRecommendationResult,
        breakthrough_keys: list[str],
        direction_labels: list[str] | None,
        competitiveness_result=None,
    ) -> str:
        parts = []
        parts.append(f"企业名称: {assessment.company_name}")
        parts.append(f"行业: {assessment.industry}")
        parts.append(f"规模: {assessment.company_size}")
        parts.append(f"区域: {assessment.region}")
        parts.append(f"年营收: {assessment.annual_revenue_range}")
        parts.append(f"核心产品: {assessment.core_products}")
        parts.append(f"当前挑战: {assessment.current_challenges}")
        parts.append(f"AI目标: {assessment.ai_goals}")
        parts.append("")
        parts.append(f"画像总结: {profile.company_summary[:200]}")
        parts.append(f"价值主张: {profile.value_proposition}")
        parts.append(f"数字化准备度: {profile.digital_and_ai_readiness}")
        parts.append("")
        parts.append(f"画布评分: {canvas.overall_score}")
        parts.append(f"薄弱模块: {', '.join(canvas.weakest_blocks)}")
        parts.append("")
        for s in scenarios.top_scenarios:
            parts.append(f"推荐场景: {s.name}（{s.category}）- {s.summary[:100]}")
        parts.append("")
        if breakthrough_keys:
            from app.schemas.breakthrough import ELEMENT_KEY_TO_TITLE
            labels = [ELEMENT_KEY_TO_TITLE.get(k, k) for k in breakthrough_keys]
            parts.append(f"突破要素: {', '.join(labels)}")
        if direction_labels:
            parts.append(f"创新方向: {', '.join(direction_labels)}")
        return "\n".join(parts)

    def _parse_llm_result(self, data: dict[str, Any]) -> ReportEnrichmentResult:
        return ReportEnrichmentResult(
            executive_summary=ExecutiveSummary.model_validate(data.get("executive_summary", {})),
            industry_benchmark=IndustryBenchmark.model_validate(data.get("industry_benchmark", {})),
            roi_framework=RoiFramework.model_validate(data.get("roi_framework", {})),
            instructor_comment=InstructorComment.model_validate(data.get("instructor_comment", {})),
        )

    def _build_rule_based(
        self,
        assessment: Assessment,
        profile: CompanyProfileResult,
        canvas: CanvasDiagnosisResult,
        scenarios: ScenarioRecommendationResult,
        breakthrough_keys: list[str],
        direction_labels: list[str] | None,
    ) -> ReportEnrichmentResult:
        from app.schemas.breakthrough import ELEMENT_KEY_TO_TITLE

        bt_labels = [ELEMENT_KEY_TO_TITLE.get(k, k) for k in breakthrough_keys] if breakthrough_keys else ["核心要素"]
        dir_labels = direction_labels or ["聚焦方向"]
        top_scene_names = [s.name for s in scenarios.top_scenarios]
        weakest = canvas.weakest_blocks

        # Executive Summary
        headline = f"{assessment.company_name}已完成AI就绪度初步诊断，整体评分{canvas.overall_score}分，建议优先在{'、'.join(top_scene_names[:2])}领域切入。"
        key_findings = [
            f"商业模式画布整体评分{canvas.overall_score}分，薄弱模块集中在{'、'.join(weakest[:3])}。",
            f"企业数字化准备度判断：{profile.digital_and_ai_readiness[:80]}。",
            f"Top 3 AI场景推荐：{'、'.join(top_scene_names)}。",
        ]
        top_3 = [
            f"优先启动{'、'.join(top_scene_names[:2])}试点验证。",
            f"重点修补{'、'.join(weakest[:2])}等薄弱环节。",
            f"围绕{'、'.join(bt_labels[:2])}构建差异化竞争力。",
        ]
        readiness = "中" if canvas.overall_score < 80 else "高"

        # Industry Benchmark
        benchmark = IndustryBenchmark(
            industry=assessment.industry,
            industry_avg_score=55,
            peer_company_size=assessment.company_size,
            peer_avg_score=52,
            percentile_rank=min(95, canvas.overall_score + 5),
            key_gap=f"在{'、'.join(weakest[:2])}方面低于行业平均水平，建议优先补充数据基础。",
            advantage=f"在{profile.value_proposition[:30]}...方面具备差异化潜力。",
        )

        # ROI Framework
        roi = RoiFramework(
            confidence_level="预估",
            low_investment_scenarios=[
                {
                    "name": top_scene_names[0] if top_scene_names else "待定场景",
                    "investment": "需投入1-2名业务分析师+AI平台试用授权，周期4-8周。",
                    "expected_return": "预计可提升相关流程效率10-20%，降低人工处理时间30-50%。",
                }
            ],
            medium_investment_scenarios=[
                {
                    "name": top_scene_names[1] if len(top_scene_names) > 1 else "扩展场景",
                    "investment": "需组建3-5人项目组+数据工程支持，周期8-16周。",
                    "expected_return": "预计可实现跨部门流程自动化，降低运营成本15-25%。",
                }
            ],
            high_investment_scenarios=[
                {
                    "name": "AI能力平台化建设",
                    "investment": "需组建AI团队+数据中台建设，周期6-12个月。",
                    "expected_return": "预计可构建可持续的AI竞争力，支撑多条业务线。",
                }
            ],
            roi_time_horizon="3-12个月",
        )

        # Instructor Comment
        instructor = InstructorComment(
            comment_mode="rule_based",
            overall_assessment=(
                f"{assessment.company_name}的AI转型基础条件总体处于行业中等水平。"
                f"在{'、'.join(bt_labels[:2])}方面具备明确突破方向，"
                f"但需要先解决{'、'.join(weakest[:2])}中的数据和管理基础问题。"
            ),
            strength_points=[
                f"行业经验丰富：{profile.value_proposition[:60]}。",
                f"已识别清晰的高价值AI场景：{'、'.join(top_scene_names[:3])}。",
                f"管理层已完成突破要素选择，决策方向明确。",
            ],
            risk_warnings=[
                f"如果{'、'.join(weakest[:2])}等薄弱模块不先解决，AI试点可能效果打折。",
                "组织惯性和跨部门协同阻力是常见障碍，需提前设定责任和决策机制。",
                "避免试点场景过多导致资源分散，建议聚焦1-2个场景。",
            ],
            next_steps_advice=(
                f"建议在30天内完成{'、'.join(top_scene_names[:1])}的首轮试点验证，"
                f"同时启动{'、'.join(weakest[:1])}的数据补充工作。"
                f"60天复盘后决定是否进入跨部门扩展阶段。"
            ),
            recommended_reading=[
                "《AI转型实践指南》- 行业通用方法论",
                "《数据驱动决策》- 建立数据文化的基础读物",
                "《创新者的窘境》- 理解组织变革的阻力和应对策略",
            ],
        )

        return ReportEnrichmentResult(
            executive_summary=ExecutiveSummary(
                headline=headline,
                key_findings=key_findings,
                top_3_recommendations=top_3,
                readiness_verdict=readiness,
            ),
            industry_benchmark=benchmark,
            roi_framework=roi,
            instructor_comment=instructor,
        )

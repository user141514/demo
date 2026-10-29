"""LLM-enhanced versions of rule-based analysis services.

Each service tries LLM generation first, falls back to rule-based on failure.
Configuration: set LLM_MODE=live and provide OPENAI_API_KEY/OPENAI_MODEL.
"""

import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.core.llm_options import completion_options
from app.models.assessment import Assessment
from app.prompts.scenario_writer_prompt import ScenarioWriterPrompt

from app.schemas.assessment import (
    CanvasDiagnosisResult,
    CompanyProfileResult,
    ScenarioRecommendationItem,
)
from app.schemas.breakthrough import (
    BreakthroughElement,
    BreakthroughRecommendationResult,
)
from app.schemas.competitiveness import (
    CompetitivenessResult,
    CoreAdvantage,
    DeliveryStrategy,
    PointToLineConnection,
    VPReconstruction,
)
from app.schemas.direction import DirectionSuggestion

logger = logging.getLogger(__name__)

BREAKTHROUGH_SYSTEM = """
你是一位企业战略顾问，正在分析商业模式画布的薄弱环节。

任务：基于画布诊断数据，深度分析每个要素的薄弱程度和突破建议。

输出要求：
1. 为每个要素给出 0-100 的评分（越低越薄弱）
2. 推荐 3 个最需要优先突破的要素
3. 给出综合性的突破建议

输出 JSON 格式：
{
  "elements": [
    {"key": "key_partnerships", "title": "关键合作伙伴", "score": 35, "reason": "...", "ai_opportunity": "..."},
    ...9个要素
  ],
  "recommended_keys": ["key_partnerships", "channels", "cost_structure"],
  "overall_suggestion": "..."
}
""".strip()

DIRECTION_SYSTEM = """
你是一位企业创新顾问，需要为突破要素生成具体的创新方向。

任务：针对每个突破要素，给出 2-3 个具体的、可落地的创新方向。

输出 JSON 格式：
{
  "elements": [
    {
      "element_key": "key_partnerships",
      "element_title": "关键合作伙伴",
      "suggestions": [
        {
          "direction_id": "unique_id_1",
          "element_key": "key_partnerships",
          "title": "方向标题",
          "description": "一句话描述",
          "expected_impact": "预期影响",
          "data_needed": ["数据1", "数据2"],
          "related_scenario_categories": ["销售增长", "交付运营"]
        }
      ]
    }
  ],
  "total_suggestions": 6
}
""".strip()

COMPETITIVENESS_SYSTEM = """
<role>
你是一位融合麦肯锡战略框架与硅谷商业思维的顶尖 AI 商业战略顾问。你精通《商业模式画布》，擅长将 AI 技术创新点转化为可落地的差异化竞争策略，并以严格的结构化 JSON 格式输出。
</role>

<task>
基于提供的企业商业画布现状、突破要素和 AI 创新方向，生成一份逻辑严密的差异化竞争力分析。
【强制要求】：直接输出符合 <output_schema> 的 JSON，不得有任何前言、注释、Markdown 包裹或额外说明文字。
</task>

<input_data>
- 企业名称与核心业务：{{company_name_and_business}}
- 商业画布现状（AS-IS）：{{canvas_as_is}}
  （含：客户细分、价值主张、渠道、客户关系、收入流、核心资源、关键业务、重要合作、成本结构）
- 突破商业画布要素：{{breakthrough_elements}}
  （例：AI 重构了"关键业务"和"成本结构"）
- Top 3 AI 创新方向：
  - 方向1（id: p1）：{{direction_1}}
  - 方向2（id: p2）：{{direction_2}}
  - 方向3（id: p3）：{{direction_3}}
</input_data>

<reasoning_chain>
在生成 JSON 前，请在内部完成以下推演（结果直接反映在输出中，无需输出推演过程）：

Step 1 - VP 质变分析：
  对比画布现状 vs 突破要素，识别价值交付逻辑的根本性变化。
  判断标准：是否从"卖投入（人力/时间/产品）"转变为"卖产出（结果/效果/数据）"？

Step 2 - 创新方向串联：
  提取 3 个方向的共性，将其命名为一个体系化方案（system_solution_name）。
  明确数据如何在 3 个方向间流动，形成增强回路而非独立功能。

Step 3 - 护城河识别：
  护城河必须建立在企业原有核心资源（行业私有数据、线下履约网络、老客户信任等）与 AI 能力的结合上，而非单纯的技术能力。
  barrier_level 评判：高 = 竞争对手至少需 2 年以上才能复制；中 = 1 年内有被复制风险；低 = 可快速被替代。

Step 4 - 竞争路径时序：
  短期（0-6 个月）= 单点降本增效或跑通 MVP 闭环
  中期（6-18 个月）= 画布核心要素重构 + 跨部门协同
  长期（18 个月+）= 数据飞轮 / 生态壁垒 / 行业标准制定
</reasoning_chain>

<output_schema>
{
  "vp_reconstruction": {
    "current_vp": "string // 基于画布现状的当前价值主张，20字以内",
    "enhanced_vp": "string // 突破后的增强型价值主张，聚焦质变而非量变，25字以内",
    "differentiation_points": ["string // 具体差异点，3-4条，每条15字以内"],
    "customer_value_shift": "string // 客户获得的价值如何从输入侧转移到结果侧，40字以内"
  },
  "connections": [
    {
      "line_name": "string // 竞争力线名称，体现战略主题",
      "point_ids": ["string // 对应方向id，如 p1/p2/p3"],
      "point_titles": ["string // 对应方向名称"],
      "strategic_narrative": "string // 3个方向如何协同形成增强回路，说明数据流向，50字以内",
      "competitive_impact": "string // 对竞争格局的具体影响，30字以内",
      "key_metrics": ["string // 可量化的验证指标，2-3个"]
    }
  ],
  "advantages": [
    {
      "advantage_name": "string // 优势名称",
      "source_elements": ["string // 来源于哪些画布要素或企业原有资源"],
      "description": "string // 该优势如何难以被AI原生竞争者（套壳初创）复制，40字以内",
      "barrier_level": "高 | 中 | 低"
    }
  ],
  "delivery_strategy": {
    "phase_1_quick_win": "string // 0-6个月：具体可验证的单点突破，包含成功标准",
    "phase_2_scale": "string // 6-18个月：哪些画布要素被重构，跨部门如何协同",
    "phase_3_moat": "string // 18个月+：数据飞轮或生态壁垒的具体形成机制",
    "key_risks": ["string // 执行风险，2-3个，每个附带缓解思路"]
  },
  "overall_narrative": "string // 一句话战略判断：该企业在AI竞争中的差异化生存逻辑，50字以内"
}
</output_schema>

<quality_gates>
输出前自检以下条件，全部满足才可输出：
enhanced_vp 体现的是交付逻辑的质变，而非旧VP的修饰版本
connections 中的 strategic_narrative 包含明确的数据流向描述
advantages 中至少一条 barrier_level 为"高"，且 source_elements 指向企业原有资源（非AI技术本身）
delivery_strategy 三个阶段符合"单点→重构→飞轮"的商业演进规律
输出为合法 JSON，无任何额外文字
</quality_gates>
""".strip()


class LLMEnhancer:
    _cache: dict[str, Any] = {}

    @classmethod
    def invalidate_cache_for(cls, assessment_id: str) -> None:
        for prefix in ("breakthrough", "directions", "competitiveness"):
            cls._cache.pop(f"{prefix}:{assessment_id}", None)

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
                temperature=0.4,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=60,
            )
            raw = response.choices[0].message.content or ""
            json_str = self._extract_json(raw)
            return json.loads(json_str)
        except Exception as exc:
            logger.warning("LLM call failed for enhancer: %s", exc)
            return None

    @staticmethod
    def _extract_json(raw: str) -> str:
        raw = raw.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        return match.group(0) if match else raw

    def enhance_breakthrough(
        self,
        canvas_diagnosis: CanvasDiagnosisResult,
        assessment_id: str = "",
    ) -> BreakthroughRecommendationResult | None:
        if not self._is_live_mode():
            return None

        if assessment_id:
            cache_key = f"breakthrough:{assessment_id}"
            if cache_key in self._cache:
                return self._cache[cache_key]

        blocks_summary = "\n".join(
            f"- {b.title}({b.key}): 诊断={b.diagnosis[:60]}, 机会={b.ai_opportunity[:60]}"
            for b in canvas_diagnosis.canvas.blocks
        )
        user_prompt = f"""画布诊断数据：
整体评分: {canvas_diagnosis.overall_score}
薄弱模块: {', '.join(canvas_diagnosis.weakest_blocks)}

各模块详情：
{blocks_summary}

请基于以上数据生成突破要素推荐。"""

        result = self._call_llm(BREAKTHROUGH_SYSTEM, user_prompt)
        if not result:
            return None

        try:
            elements = [BreakthroughElement.model_validate(e) for e in result.get("elements", [])]
            if len(elements) != 9:
                return None
            parsed = BreakthroughRecommendationResult(
                generation_mode="llm",
                elements=elements,
                recommended_keys=result.get("recommended_keys", [])[:3],
                overall_suggestion=result.get("overall_suggestion", ""),
            )
            if assessment_id:
                self._cache[f"breakthrough:{assessment_id}"] = parsed
            return parsed
        except Exception as exc:
            logger.warning("Failed to parse LLM breakthrough response: %s", exc)
            return None

    def enhance_directions(
        self,
        canvas_diagnosis: CanvasDiagnosisResult,
        breakthrough_keys: list[str],
    ) -> list[DirectionSuggestion] | None:
        if not self._is_live_mode():
            return None

        from app.schemas.breakthrough import ELEMENT_KEY_TO_TITLE

        block_details = "\n".join(
            f"- {b.title}({b.key}): {b.diagnosis[:80]}, AI机会={b.ai_opportunity[:80]}"
            for b in canvas_diagnosis.canvas.blocks
            if b.key in breakthrough_keys
        )
        keys_display = "、".join(ELEMENT_KEY_TO_TITLE.get(k, k) for k in breakthrough_keys)

        user_prompt = f"""选定突破要素: {keys_display}

相关模块详情：
{block_details}

请为每个选定的突破要素生成 2-3 个具体的创新方向。direction_id 用英文下划线命名。"""

        result = self._call_llm(DIRECTION_SYSTEM, user_prompt)
        if not result:
            return None

        try:
            directions: list[DirectionSuggestion] = []
            for elem in result.get("elements", []):
                for s in elem.get("suggestions", []):
                    directions.append(DirectionSuggestion.model_validate(s))
            return directions if directions else None
        except Exception as exc:
            logger.warning("Failed to parse LLM direction response: %s", exc)
            return None

    def enhance_competitiveness(
        self,
        canvas_diagnosis: CanvasDiagnosisResult,
        breakthrough_keys: list[str],
        selected_directions: list[DirectionSuggestion],
    ) -> CompetitivenessResult | None:
        if not self._is_live_mode():
            return None

        from app.schemas.breakthrough import ELEMENT_KEY_TO_TITLE

        dir_summary = "\n".join(
            f"- [{d.element_key}] {d.title}: {d.description[:80]}"
            for d in selected_directions
        )
        keys_display = "、".join(ELEMENT_KEY_TO_TITLE.get(k, k) for k in breakthrough_keys)

        user_prompt = f"""突破要素: {keys_display}
画布评分: {canvas_diagnosis.overall_score}
薄弱模块: {', '.join(canvas_diagnosis.weakest_blocks)}

选定创新方向：
{dir_summary}

请生成完整的差异化竞争力分析，barrier_level 用 高/中/低 三个级别。"""

        result = self._call_llm(COMPETITIVENESS_SYSTEM, user_prompt)
        if not result:
            return None

        try:
            vp_raw = result.get("vp_reconstruction", {})
            vp = VPReconstruction.model_validate(vp_raw)

            connections = [
                PointToLineConnection.model_validate(c)
                for c in result.get("connections", [])
            ]
            advantages = [
                CoreAdvantage.model_validate(a)
                for a in result.get("advantages", [])
            ]
            strategy = DeliveryStrategy.model_validate(
                result.get("delivery_strategy", {})
            )
            return CompetitivenessResult(
                generation_mode="llm",
                vp_reconstruction=vp,
                connections=connections,
                advantages=advantages,
                delivery_strategy=strategy,
                overall_narrative=result.get("overall_narrative", ""),
            )
        except Exception as exc:
            logger.warning("Failed to parse LLM competitiveness response: %s", exc)
            return None

    def enhance_scenario_descriptions(
        self,
        assessment: Assessment,
        profile: CompanyProfileResult | None,
        canvas_diagnosis: CanvasDiagnosisResult,
        breakthrough_labels: list[str],
        selected_directions: list[DirectionSuggestion],
        scenarios: list[ScenarioRecommendationItem],
    ) -> list[ScenarioRecommendationItem] | None:
        if not self._is_live_mode():
            return None
        if not scenarios:
            return []

        system_prompt = ScenarioWriterPrompt.build_system_prompt()
        user_prompt = ScenarioWriterPrompt.build_user_prompt(
            assessment=assessment,
            profile=profile,
            canvas=canvas_diagnosis,
            breakthrough_labels=breakthrough_labels,
            selected_directions=selected_directions,
            scenarios=scenarios,
        )
        result = self._call_llm(system_prompt, user_prompt)
        if not result:
            return None

        raw_items = result.get("scenarios", [])
        if not isinstance(raw_items, list) or not raw_items:
            return None

        rewrite_by_id: dict[str, dict[str, object]] = {}
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            scenario_id = str(raw.get("scenario_id", "")).strip()
            if not scenario_id:
                continue
            # 解析 benefits 列表
            raw_benefits = raw.get("benefits", [])
            benefits_list: list[dict[str, str]] = []
            if isinstance(raw_benefits, list):
                for b in raw_benefits:
                    if isinstance(b, dict):
                        benefits_list.append({
                            "text": str(b.get("text", "")).strip(),
                            "canvas": str(b.get("canvas", "")).strip(),
                        })
            # 解析 resources 列表
            raw_resources = raw.get("resources", [])
            resources_list: list[dict[str, str]] = []
            if isinstance(raw_resources, list):
                for r in raw_resources:
                    if isinstance(r, dict):
                        resources_list.append({
                            "type": str(r.get("type", "")).strip(),
                            "label": str(r.get("label", "")).strip(),
                            "text": str(r.get("text", "")).strip(),
                        })
            # 解析 value_dimensions
            raw_dims = raw.get("value_dimensions", [])
            dims_list: list[str] = []
            if isinstance(raw_dims, list):
                for d in raw_dims:
                    if isinstance(d, str):
                        dims_list.append(d.strip())

            rewrite_by_id[scenario_id] = {
                "summary": str(raw.get("summary", "")).strip(),
                "canvas_elements": str(raw.get("canvas_elements", "")).strip(),
                "expected_effects": str(raw.get("expected_effects", "")).strip(),
                "core_data_requirements": str(
                    raw.get("core_data_requirements", "")
                ).strip(),
                "canvas_element": str(raw.get("canvas_element", "")).strip(),
                "canvas_key": str(raw.get("canvas_key", "")).strip(),
                "positioning": str(raw.get("positioning", "")).strip(),
                "value_dimensions": dims_list,
                "value_text": str(raw.get("value_text", "")).strip(),
                "benefits": benefits_list,
                "resources": resources_list,
            }

        if not rewrite_by_id:
            return None

        enhanced_items: list[ScenarioRecommendationItem] = []
        matched_count = 0
        for item in scenarios:
            rewrite = rewrite_by_id.get(item.scenario_id)
            if not rewrite:
                enhanced_items.append(item.model_copy(deep=True))
                continue
            matched_count += 1
            benefits_models = [
                {"text": b["text"], "canvas": b["canvas"]}
                for b in rewrite.get("benefits", []) if isinstance(b, dict)
            ]
            resources_models = [
                {"type": r.get("type", ""), "label": r.get("label", ""), "text": r.get("text", "")}
                for r in rewrite.get("resources", []) if isinstance(r, dict)
            ]
            enhanced_items.append(
                item.model_copy(
                    update={
                        "summary": rewrite.get("summary") or item.summary,
                        "canvas_elements": rewrite.get("canvas_elements")
                        or item.canvas_elements,
                        "expected_effects": rewrite.get("expected_effects")
                        or item.expected_effects,
                        "core_data_requirements": rewrite.get("core_data_requirements")
                        or item.core_data_requirements,
                        "canvas_element": rewrite.get("canvas_element") or item.canvas_element,
                        "canvas_key": rewrite.get("canvas_key") or item.canvas_key,
                        "positioning": rewrite.get("positioning") or item.positioning,
                        "value_dimensions": rewrite.get("value_dimensions") or item.value_dimensions,
                        "value_text": rewrite.get("value_text") or item.value_text,
                        "benefits": benefits_models or item.benefits,
                        "resources": resources_models or item.resources,
                    }
                )
            )

        return enhanced_items if matched_count else None

"""
LLM-powered field extraction for intake documents.

Uses the configured LLM (OpenAI-compatible) to extract structured
assessment fields from raw text. Falls back to regex-based extraction
when LLM is unavailable or in mock mode.
"""

from __future__ import annotations

import json
import logging

from app.core.config import settings
from app.core.llm_options import completion_options


logger = logging.getLogger(__name__)

ASSESSMENT_FIELD_NAMES: dict[str, str] = {
    "company_name": "企业名称",
    "industry": "所属行业",
    "company_size": "企业规模",
    "region": "所在区域",
    "annual_revenue_range": "年营收范围",
    "core_products": "核心产品/服务",
    "target_customers": "目标客户",
    "current_challenges": "当前经营/管理挑战",
    "ai_goals": "希望通过 AI 达成的目标",
    "available_data": "当前可用数据/系统基础",
    "notes": "其他补充说明",
}

EXTRACTOR_SYSTEM_PROMPT = """\
你是一个企业信息提取助手。从用户提供的文档中提取关键企业信息。

# 输出格式
返回一个 JSON 对象，key 固定为以下 11 个字段，value 为提取到的文本。
**找不到信息的字段必须设为空字符串 ""，绝不编造。**

# 字段说明
- company_name: 企业名称（公司全称）
- industry: 所属行业（如：装备制造、医疗器械、连锁零售、软件服务等）
- company_size: 企业规模，标准化为以下之一：10人以下 / 10-50人 / 50-200人 / 200-500人 / 500人以上
- region: 所在区域（城市或地区，如：上海、苏州、深圳、华东等）
- annual_revenue_range: 年营收范围，标准化为以下之一：500万以下 / 500万-3000万 / 3000万-1亿 / 1亿-10亿 / 10亿以上
- core_products: 核心产品/服务（主要业务描述）
- target_customers: 目标客户（主要客户群体描述）
- current_challenges: 当前经营/管理挑战（企业面临的主要问题和困难）
- ai_goals: 希望通过 AI 达成的目标（企业对 AI 的期望和需求）
- available_data: 当前可用数据/系统基础（已有的信息化系统、数据源等）
- notes: 其他补充说明（其他值得注意的信息）

# 规则
1. 只提取文档中明确提到的信息
2. 不要推断或编造任何信息
3. 找不到信息的字段直接返回空字符串 ""
4. 如果提到员工人数但未给出标准化范围，尽量推断合适的标准化值
5. 如果提到营收但未给出标准化范围，尽量推断合适的标准化值
"""


class IntakeLLMExtractor:
    """Extract assessment fields from raw text using LLM."""

    def extract(self, raw_text: str) -> dict[str, str]:
        """
        Extract 11 assessment fields from raw text.

        Returns dict with all 11 field keys.
        Fields that can't be determined are set to "".
        """
        if not raw_text or not raw_text.strip():
            return {k: "" for k in ASSESSMENT_FIELD_NAMES}

        if self._use_mock_mode():
            logger.info("IntakeLLMExtractor: mock mode — returning empty dict")
            return {k: "" for k in ASSESSMENT_FIELD_NAMES}

        try:
            result = self._call_llm(raw_text)
            logger.info(
                "IntakeLLMExtractor: LLM extraction complete — %d fields filled",
                sum(1 for v in result.values() if v),
            )
            return result
        except Exception as exc:
            logger.warning("IntakeLLMExtractor: LLM call failed — %s", exc)
            return {k: "" for k in ASSESSMENT_FIELD_NAMES}

    def _use_mock_mode(self) -> bool:
        return settings.llm_mode != "live" or not settings.openai_api_key or not settings.openai_model

    def _call_llm(self, raw_text: str) -> dict[str, str]:
        from openai import OpenAI

        # Truncate very long texts to avoid token limits
        max_chars = 8000
        text = raw_text[:max_chars]
        if len(raw_text) > max_chars:
            text += "\n\n[文档过长，已截断...]"

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

        response = client.chat.completions.create(
            model=settings.openai_model,
            **completion_options(),
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"请从以下文档中提取企业信息：\n\n{text}",
                },
            ],
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)

        # Normalize: ensure all 11 fields present, non-empty strings
        result: dict[str, str] = {}
        for key in ASSESSMENT_FIELD_NAMES:
            value = parsed.get(key, "")
            result[key] = str(value).strip() if value else ""

        return result

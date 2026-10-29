"""BMC 三维突破要素评分 — Pydantic Schema"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ── 模块定义（与 breakthrough.BREAKTHROUGH_ELEMENTS 使用相同的 key） ──

BMC_MODULE_DEFINITIONS = [
    {"key": "customer_segments", "title": "客户细分", "abbr": "CS", "category": "market", "display_order": 1},
    {"key": "value_propositions", "title": "价值主张", "abbr": "VP", "category": "market", "display_order": 2},
    {"key": "channels", "title": "渠道通路", "abbr": "CH", "category": "market", "display_order": 3},
    {"key": "customer_relationships", "title": "客户关系", "abbr": "CR", "category": "market", "display_order": 4},
    {"key": "revenue_streams", "title": "收入来源", "abbr": "R$", "category": "market", "display_order": 5},
    {"key": "key_resources", "title": "核心资源", "abbr": "KR", "category": "efficiency", "display_order": 6},
    {"key": "key_activities", "title": "关键业务", "abbr": "KA", "category": "efficiency", "display_order": 7},
    {"key": "key_partnerships", "title": "重要合作", "abbr": "KP", "category": "efficiency", "display_order": 8},
    {"key": "cost_structure", "title": "成本结构", "abbr": "C$", "category": "efficiency", "display_order": 9},
]

MODULE_KEY_TO_TITLE = {m["key"]: m["title"] for m in BMC_MODULE_DEFINITIONS}
MODULE_KEY_TO_CATEGORY = {m["key"]: m["category"] for m in BMC_MODULE_DEFINITIONS}

# 内部效率类要素（用于互补性检验）
INTERNAL_EFFICIENCY_KEYS = {"key_activities", "key_resources", "cost_structure"}
MARKET_SIDE_KEYS = {"customer_segments", "value_propositions", "channels", "customer_relationships"}

# ── 评分算法常量 ──

WEIGHT_PAIN = 0.40
WEIGHT_DATA = 0.35
WEIGHT_FEASIBILITY = 0.25
INTERACTION_ALPHA = 0.05
SCORE_MIN = 1.05
SCORE_MAX = 6.25
SCORE_RANGE = SCORE_MAX - SCORE_MIN  # 5.20


# ── 输入模型 ──

class ModuleScoreInput(BaseModel):
    """单个模块的三维评分输入"""
    key: str
    pain: float = Field(ge=1, le=5, description="痛点迫切度 1-5")
    data: float = Field(ge=1, le=5, description="数据基础度 1-5")
    feasibility: float = Field(ge=1, le=5, description="实施可行度 1-5")

    @field_validator("key")
    @classmethod
    def validate_module_key(cls, value: str) -> str:
        if value not in MODULE_KEY_TO_TITLE:
            raise ValueError("请选择九大商业画布模块中的有效模块")
        return value


class BMCScoringRequest(BaseModel):
    """批量评分请求"""
    assessment_id: str
    modules: list[ModuleScoreInput] = Field(min_length=1, max_length=9)


class BMCScoringSaveRequest(BaseModel):
    """保存评分和选择"""
    selected_keys: list[str] = Field(min_length=1, max_length=3)
    all_module_scores: list[ModuleScoreInput] = Field(min_length=1, max_length=9)
    selection_mode: Literal["bmc_scoring", "manual"] = "bmc_scoring"

    @field_validator("all_module_scores")
    @classmethod
    def validate_unique_modules(cls, values: list[ModuleScoreInput]) -> list[ModuleScoreInput]:
        if len({item.key for item in values}) != len(values):
            raise ValueError("模块评分不能重复")
        return values


# ── 输出模型 ──

class ModuleScoringResult(BaseModel):
    """单个模块的完整评分结果"""
    key: str
    title: str
    abbr: str
    category: str
    pain: float
    data: float
    feasibility: float
    raw_score: float
    normalized_score: float = Field(ge=0, le=100)
    zone: str  # quickwin / strategic / longterm / hold / blocked
    veto_status: str  # none / blocked_feasibility / blocked_data_pain / not_recommended
    veto_reason: str | None = None
    recommendation_level: str  # top / strategic / cultivate / none / veto
    recommendation_label: str  # 前端标签文案
    recommendation_stars: str  # ⭐⭐⭐ / ⭐⭐ / ⭐ / — / 🚫


class BMCScoringResult(BaseModel):
    """完整评分结果"""
    assessment_id: str
    module_results: list[ModuleScoringResult]
    top_3_keys: list[str] = Field(default_factory=list, max_length=3)
    top_3_results: list[ModuleScoringResult] = Field(default_factory=list)
    complementarity_warning: str | None = None


class BMCScoringResponse(BaseModel):
    """评分保存后的完整响应"""
    assessment_id: str
    scoring_result: BMCScoringResult | None = None
    selected_keys: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AutoDeriveResponse(BaseModel):
    """自动推导响应"""
    modules: list[ModuleScoreInput]
    derived_from_canvas: bool = True

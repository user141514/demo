from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


BREAKTHROUGH_ELEMENTS = [
    {"key": "key_partnerships", "title": "关键合作伙伴", "display_order": 1},
    {"key": "key_activities", "title": "关键业务活动", "display_order": 2},
    {"key": "key_resources", "title": "关键资源", "display_order": 3},
    {"key": "value_propositions", "title": "价值主张", "display_order": 4},
    {"key": "customer_relationships", "title": "客户关系", "display_order": 5},
    {"key": "channels", "title": "渠道通路", "display_order": 6},
    {"key": "customer_segments", "title": "客户细分", "display_order": 7},
    {"key": "cost_structure", "title": "成本结构", "display_order": 8},
    {"key": "revenue_streams", "title": "收入来源", "display_order": 9},
]

ELEMENT_KEY_TO_TITLE = {item["key"]: item["title"] for item in BREAKTHROUGH_ELEMENTS}


class BreakthroughElement(BaseModel):
    key: str
    title: str
    score: int = Field(ge=0, le=100)
    reason: str
    ai_opportunity: str


class BreakthroughRecommendationResult(BaseModel):
    generation_mode: Literal["rule_based", "mock"]
    elements: list[BreakthroughElement] = Field(default_factory=list)
    recommended_keys: list[str] = Field(default_factory=list, max_length=3)
    overall_suggestion: str


class BreakthroughSelectionRequest(BaseModel):
    selected_keys: list[str] = Field(min_length=1, max_length=3)
    selection_mode: Literal["system_recommended", "manual"]


class BreakthroughSelectionResponse(BaseModel):
    assessment_id: str
    selection_mode: str
    recommended_elements: list[BreakthroughElement] = Field(default_factory=list)
    selected_elements: list[BreakthroughElement] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssessmentBreakthroughResponse(BaseModel):
    assessment_id: str
    breakthrough_recommendation: BreakthroughRecommendationResult
    breakthrough_selection: BreakthroughSelectionResponse | None = None

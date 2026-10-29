"""W8 Report Intelligence: 执行摘要 / 行业对标 / ROI 框架 / 管理员点评"""
from datetime import datetime

from pydantic import BaseModel, Field


class ExecutiveSummary(BaseModel):
    headline: str
    key_findings: list[str] = Field(default_factory=list)
    top_3_recommendations: list[str] = Field(default_factory=list)
    readiness_verdict: str


class IndustryBenchmark(BaseModel):
    industry: str
    industry_avg_score: int = Field(default=50, ge=0, le=100)
    peer_company_size: str
    peer_avg_score: int = Field(default=50, ge=0, le=100)
    percentile_rank: int = Field(default=50, ge=0, le=100)
    key_gap: str
    advantage: str


class RoiFramework(BaseModel):
    confidence_level: str = "预估"
    low_investment_scenarios: list[dict[str, str]] = Field(default_factory=list)
    medium_investment_scenarios: list[dict[str, str]] = Field(default_factory=list)
    high_investment_scenarios: list[dict[str, str]] = Field(default_factory=list)
    roi_time_horizon: str


class InstructorComment(BaseModel):
    comment_mode: str = "rule_based"
    overall_assessment: str
    strength_points: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    next_steps_advice: str
    recommended_reading: list[str] = Field(default_factory=list)


class ReportEnrichmentResult(BaseModel):
    executive_summary: ExecutiveSummary
    industry_benchmark: IndustryBenchmark
    roi_framework: RoiFramework
    instructor_comment: InstructorComment
    generated_at: datetime | None = None

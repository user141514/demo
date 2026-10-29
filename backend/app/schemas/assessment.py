from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.direction import DirectionExpansionResult, DirectionSelectionResponse
from app.schemas.competitiveness import CompetitivenessResponse
from app.schemas.endgame import EndgameResponse
from app.schemas.payment import EntitlementResponse


class AssessmentCardItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_name: str
    industry: str
    company_size: str
    has_profile: bool
    has_report: bool = False
    created_at: datetime
    updated_at: datetime


class AssessmentListResponse(BaseModel):
    items: list[AssessmentCardItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class AssessmentCreateRequest(BaseModel):
    company_name: str = Field(default="", max_length=255)
    industry: str = Field(default="", max_length=255)
    company_size: str = Field(default="", max_length=100)
    region: str = Field(default="", max_length=255)
    annual_revenue_range: str = Field(default="", max_length=100)
    core_products: str = Field(default="")
    target_customers: str = Field(default="")
    current_challenges: str = Field(default="")
    ai_goals: str = Field(default="")
    available_data: str = Field(default="")
    notes: str | None = None
    class_group: str | None = None


class AssessmentInputSnapshot(BaseModel):
    company_name: str
    industry: str
    company_size: str
    region: str
    annual_revenue_range: str
    core_products: str
    target_customers: str
    current_challenges: str
    ai_goals: str
    available_data: str
    notes: str | None


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_name: str
    industry: str
    company_size: str
    region: str
    annual_revenue_range: str
    core_products: str
    target_customers: str
    current_challenges: str
    ai_goals: str
    available_data: str
    notes: str | None
    class_group: str | None = None
    instructor_comment: str | None = None
    has_profile: bool
    profile_generation_mode: str | None
    profile_generated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CompanyProfileResult(BaseModel):
    company_name: str
    company_summary: str
    value_proposition: str
    customer_and_market: str
    operations_and_resources: str
    digital_and_ai_readiness: str
    key_challenges: list[str] = Field(default_factory=list)
    priority_ai_directions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_llm_types(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        # LLM sometimes returns customer_and_market as a list — join to str
        cam = data.get("customer_and_market")
        if isinstance(cam, list):
            data["customer_and_market"] = "、".join(str(x) for x in cam)
        # LLM sometimes returns missing_information as a plain str — wrap in list
        mi = data.get("missing_information")
        if isinstance(mi, str):
            data["missing_information"] = [mi] if mi.strip() else []
        return data


class AssessmentProfileResponse(BaseModel):
    assessment: AssessmentResponse
    generation_mode: Literal["mock", "live"]
    profile: CompanyProfileResult


class CanvasBlockResult(BaseModel):
    key: str
    title: str
    current_state: str
    diagnosis: str
    ai_opportunity: str
    missing_information: str


class BusinessModelCanvasResult(BaseModel):
    overall_summary: str
    blocks: list[CanvasBlockResult] = Field(default_factory=list)


class CanvasDiagnosisResult(BaseModel):
    generation_mode: Literal["mock", "live", "manual_edit"]
    overall_score: int
    weakest_blocks: list[str] = Field(default_factory=list)
    recommended_focus: list[str] = Field(default_factory=list)
    canvas: BusinessModelCanvasResult
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssessmentCanvasResponse(BaseModel):
    assessment: AssessmentResponse
    canvas_diagnosis: CanvasDiagnosisResult


class ScenarioBenefit(BaseModel):
    text: str = ""
    canvas: str = ""


class ScenarioResource(BaseModel):
    type: str = ""
    label: str = ""
    text: str = ""


class ScenarioRecommendationItem(BaseModel):
    scenario_id: str
    name: str
    category: str
    summary: str
    canvas_elements: str = ""
    expected_effects: str = ""
    core_data_requirements: str = ""
    # 新版结构化字段（优先使用，旧字段保留兼容）
    canvas_element: str = ""
    canvas_key: str = ""
    positioning: str = ""
    value_dimensions: list[str] = Field(default_factory=list)
    value_text: str = ""
    benefits: list[ScenarioBenefit] = Field(default_factory=list)
    resources: list[ScenarioResource] = Field(default_factory=list)
    # 四象限优先级评分字段（可选，由 ScenePriorityScorer 填充）
    priority_structuredness_x: float | None = None
    priority_complexity_y: float | None = None
    priority_qs: float | None = None
    priority_lps: float | None = None
    priority_lps_display: float | None = None
    priority_quadrant: str | None = None
    priority_tier: int | None = None
    priority_recommendation: str | None = None
    industry_coefficient: float | None = None
    recommendation_level: str | None = None


class ScenarioRecommendationResult(BaseModel):
    scoring_method: Literal["rule_based_v1", "four_quadrant_v1"]
    evaluated_count: int
    top_scenarios: list[ScenarioRecommendationItem] = Field(default_factory=list)
    fallback_triggered: bool = False
    fallback_reason: str = ""
    all_scores: list[ScenarioRecommendationItem] | None = None
    active_count: int | None = None
    excluded_scores: list[ScenarioRecommendationItem] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScenarioCalibrationItem(BaseModel):
    scenario_id: str
    priority_structuredness_x: float = Field(ge=1, le=5)
    priority_complexity_y: float = Field(ge=1, le=5)


class ScenarioCalibrationRequest(BaseModel):
    calibrations: list[ScenarioCalibrationItem] = Field(min_length=1, max_length=50)


class ScenarioPoolUpdateRequest(BaseModel):
    active_scenario_ids: list[str] = Field(min_length=3, max_length=50)


class ScenarioTop3SelectionRequest(BaseModel):
    selected_scenario_ids: list[str] = Field(min_length=3, max_length=3)


class AssessmentScenarioRecommendationResponse(BaseModel):
    assessment: AssessmentResponse
    scenario_recommendation: ScenarioRecommendationResult


class CaseMatchItem(BaseModel):
    case_id: str
    title: str
    industry: str
    summary: str
    fit_score: int = Field(ge=0, le=100)
    matched_pain_points: list[str] = Field(default_factory=list)
    matched_canvas_blocks: list[str] = Field(default_factory=list)
    matched_scenarios: list[str] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    reference_points: list[str] = Field(default_factory=list)
    data_foundation: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    retrieval_source: str = "rule_based"
    source_summary: str = ""


class CaseRecommendationResult(BaseModel):
    scoring_method: Literal["rule_based_case_v1", "layered_v1"]
    evaluated_count: int
    top_cases: list[CaseMatchItem] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssessmentCaseResponse(BaseModel):
    assessment: AssessmentResponse
    case_recommendation: CaseRecommendationResult


class ReportRoadmapStage(BaseModel):
    stage_name: str
    time_horizon: str
    strategic_focus: str
    priority_actions: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)


class ReportActionItem(BaseModel):
    period: str
    action: str
    owner_suggestion: str
    deliverable: str


class ReportTableData(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ReportCardData(BaseModel):
    title: str
    subtitle: str | None = None
    content: str
    bullets: list[str] = Field(default_factory=list)
    highlight: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ReportSectionData(BaseModel):
    key: str
    title: str
    content: str
    bullets: list[str] = Field(default_factory=list)
    table: ReportTableData | None = None
    cards: list[ReportCardData] = Field(default_factory=list)
    note: str | None = None


class ReportData(BaseModel):
    title: str
    subtitle: str
    company_name: str
    industry: str
    company_size: str
    region: str
    annual_revenue_range: str
    ai_readiness_score: int = Field(ge=0, le=100)
    ai_readiness_summary: str
    generated_with: Literal["template", "llm"]
    sections: list[ReportSectionData] = Field(default_factory=list)


class ReportSummaryResponse(BaseModel):
    report_id: str
    assessment_id: str
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReportDocumentResponse(BaseModel):
    report_id: str
    assessment_id: str
    title: str
    generation_mode: str
    used_llm: bool
    used_rag: bool
    warnings: list[str] = Field(default_factory=list)
    content_markdown: str
    content_html: str
    content_json: ReportData
    sections: list[ReportSectionData] = Field(default_factory=list)
    export_markdown_path: str | None = None
    export_docx_path: str | None = None
    export_pdf_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssessmentProgress(BaseModel):
    has_profile: bool
    has_canvas: bool
    has_breakthrough: bool
    has_directions: bool
    has_competitiveness: bool
    has_endgame: bool
    has_scenarios: bool
    has_cases: bool
    has_report: bool
    ready_for_report: bool


class AssessmentDetailResponse(BaseModel):
    assessment: AssessmentResponse
    entitlement: EntitlementResponse
    company_profile: CompanyProfileResult | None
    canvas_diagnosis: CanvasDiagnosisResult | None
    breakthrough_selection: list[str] | None = None
    direction_expansion: DirectionExpansionResult | None = None
    direction_selection: DirectionSelectionResponse | None = None
    scenario_recommendation: ScenarioRecommendationResult | None
    competitiveness: CompetitivenessResponse | None = None
    endgame: EndgameResponse | None = None
    case_recommendation: CaseRecommendationResult | None
    generated_report: ReportSummaryResponse | None
    progress: AssessmentProgress


class ReportContextResponse(BaseModel):
    assessment_id: str
    company_input: AssessmentInputSnapshot
    company_profile: CompanyProfileResult
    canvas_diagnosis: CanvasDiagnosisResult
    selected_breakthrough_elements: list[str] = Field(default_factory=list)
    top_scenarios: list[ScenarioRecommendationItem] = Field(default_factory=list)
    report_outline: list[str] = Field(default_factory=list)


class StudentSummary(BaseModel):
    assessment_id: str
    company_name: str
    industry: str
    company_size: str
    class_group: str | None = None
    instructor_comment: str | None = None
    has_profile: bool = False
    has_canvas: bool = False
    has_breakthrough: bool = False
    has_directions: bool = False
    has_competitiveness: bool = False
    has_scenarios: bool = False
    has_cases: bool = False
    has_report: bool = False
    ready_for_report: bool = False
    canvas_score: int | None = None
    report_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class InstructorDashboardResponse(BaseModel):
    total_students: int
    groups: list[str] = Field(default_factory=list)
    students: list[StudentSummary] = Field(default_factory=list)
    summary_by_group: dict[str, int] = Field(default_factory=dict)
    overall_completion_pct: int = 0


class BatchCommentRequest(BaseModel):
    assessment_ids: list[str] = Field(min_length=1, max_length=50)
    comment: str = Field(min_length=1, max_length=1000)


class BatchCommentResponse(BaseModel):
    updated_count: int
    comment: str


class InstructorExportResponse(BaseModel):
    export_format: str
    content: str
    student_count: int

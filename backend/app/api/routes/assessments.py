import json
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, get_db
from app.models.assessment import Assessment
from app.models.bmc_scoring import BMCScoring
from app.models.breakthrough_selection import BreakthroughSelection
from app.models.canvas_diagnosis import CanvasDiagnosis
from app.models.case_recommendation import CaseRecommendation
from app.models.chat import Conversation, Message
from app.models.competitiveness_analysis import CompetitivenessAnalysis
from app.models.direction_expansion import DirectionExpansion
from app.models.direction_selection import DirectionSelection
from app.models.endgame_analysis import EndgameAnalysis
from app.models.follow_up import FollowUpTask
from app.models.generated_report import GeneratedReport
from app.models.intake_session import AssessmentIntakeSession
from app.models.payment import AssessmentEntitlement, PaymentOrder
from app.models.push_record import PushRecord
from app.models.scenario_recommendation import ScenarioRecommendation
from app.schemas.assessment import (
    AssessmentCanvasResponse,
    AssessmentCaseResponse,
    AssessmentCreateRequest,
    AssessmentDetailResponse,
    AssessmentInputSnapshot,
    AssessmentProfileResponse,
    AssessmentProgress,
    AssessmentResponse,
    AssessmentScenarioRecommendationResponse,
    BusinessModelCanvasResult,
    CanvasBlockResult,
    CanvasDiagnosisResult,
    CaseMatchItem,
    CaseRecommendationResult,
    CompanyProfileResult,
    ReportContextResponse,
    ReportDocumentResponse,
    ScenarioCalibrationItem,
    ScenarioCalibrationRequest,
    ScenarioBenefit,
    ScenarioPoolUpdateRequest,
    ScenarioRecommendationItem,
    ScenarioRecommendationResult,
    ScenarioResource,
)
from app.schemas.breakthrough import (
    AssessmentBreakthroughResponse,
    BreakthroughRecommendationResult,
    BreakthroughSelectionRequest,
    BreakthroughSelectionResponse,
    BreakthroughElement,
    ELEMENT_KEY_TO_TITLE,
)
from app.schemas.direction import (
    AssessmentDirectionResponse,
    DirectionExpansionResult,
    DirectionSelectionRequest,
    DirectionSelectionResponse,
    DirectionSuggestion,
)
from app.schemas.competitiveness import (
    build_line_summary,
    CompetitivenessResponse,
    CompetitivenessResult,
    CoreAdvantage,
    DeliveryStrategy,
    PointToLineConnection,
    VPReconstruction,
)
from app.schemas.endgame import (
    EcosystemDesign,
    EndgameResponse,
    EndgameResult,
    OPCDesign,
    PrivateDomainDesign,
    StrategicPath,
    ThreeStageStrategy,
)
from app.services.breakthrough_recommender import BreakthroughRecommender
from app.services.case_matcher import CaseMatcher
from app.services.competitiveness_analyzer import CompetitivenessAnalyzer
from app.services.direction_expansion_service import DirectionExpansionService
from app.services.endgame_analyzer import EndgameAnalyzer
from app.services.llm_client import LLMClient
from app.services.llm_enhancer import LLMEnhancer
from app.services.report_builder import ReportBuilder
from app.services.report_enrichment import ReportEnrichmentService
from app.services.report_service import ReportService
from app.services.payment_service import EntitlementService
from app.services.scenario_recommender import ScenarioRecommender
from app.services.scene_priority_scorer import ScenePriorityScorer
from app.schemas.scene_priority import ScenePriorityInput
from app.api.deps import get_current_user, require_instructor
from app.models.user import User
from app.schemas.assessment import AssessmentCardItem, AssessmentListResponse

router = APIRouter(prefix="/api/assessments", tags=["assessments"])

REPORT_OUTLINE = [
    "当前商业模式画布诊断",
    "突破要素",
    "创新方向延展",
    "高优先级 AI 提效场景",
    "差异化竞争力设计",
    "商业终局设计",
]


def _check_owner_or_instructor(
    assessment: Assessment, current_user: User
) -> None:
    if current_user.role == "instructor":
        return
    if assessment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此评估。",
        )


def _require_paid_workflow_access(
    db: Session,
    assessment: Assessment,
    current_user: User,
) -> None:
    _check_owner_or_instructor(assessment, current_user)
    EntitlementService().require_paid_access(db, assessment, current_user)


def _claim_orphaned_assessment_from_intake(
    db: Session,
    assessment: Assessment,
    current_user: User,
) -> Assessment:
    if current_user.role == "instructor" or assessment.user_id is not None:
        return assessment

    intake_session = (
        db.query(AssessmentIntakeSession)
        .filter(AssessmentIntakeSession.created_assessment_id == assessment.id)
        .order_by(AssessmentIntakeSession.created_at.desc())
        .first()
    )
    if intake_session is None:
        return assessment
    if intake_session.user_id not in (None, current_user.id):
        return assessment

    assessment.user_id = current_user.id
    db.add(assessment)
    if intake_session.user_id is None:
        intake_session.user_id = current_user.id
        db.add(intake_session)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    payload: AssessmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentResponse:
    assessment = Assessment(**payload.model_dump(), user_id=current_user.id)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return AssessmentResponse.model_validate(assessment, from_attributes=True)


@router.get("", response_model=AssessmentListResponse, status_code=status.HTTP_200_OK)
def list_assessments(
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    industry: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentListResponse:
    query = db.query(Assessment)
    if current_user.role != "instructor":
        query = query.filter(Assessment.user_id == current_user.id)
    if search:
        query = query.filter(Assessment.company_name.ilike(f"%{search}%"))
    if date_from:
        query = query.filter(Assessment.created_at >= date_from)
    if date_to:
        query = query.filter(Assessment.created_at <= date_to)
    if industry:
        query = query.filter(Assessment.industry == industry)

    total = query.count()
    items = (
        query.order_by(Assessment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    card_items = []
    for a in items:
        has_report = db.query(GeneratedReport).filter(
            GeneratedReport.assessment_id == a.id
        ).count() > 0
        card_items.append(
            AssessmentCardItem(
                id=a.id,
                company_name=a.company_name,
                industry=a.industry,
                company_size=a.company_size,
                has_profile=a.has_profile,
                has_report=has_report,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
        )

    return AssessmentListResponse(
        items=card_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除当前用户的评估及其所有关联数据。"""
    assessment = _get_assessment_or_404(db, assessment_id)
    if assessment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此评估")

    # 1. 删除会话和消息
    conv = db.scalar(
        select(Conversation).where(Conversation.assessment_id == assessment_id)
    )
    if conv:
        msgs = db.scalars(
            select(Message).where(Message.conversation_id == conv.id)
        ).all()
        for m in msgs:
            db.delete(m)
        db.delete(conv)

    # 2. 级联删除所有 1:1 子记录
    for model in [
        CanvasDiagnosis,
        BreakthroughSelection,
        DirectionExpansion,
        DirectionSelection,
        CompetitivenessAnalysis,
        EndgameAnalysis,
        ScenarioRecommendation,
        CaseRecommendation,
        GeneratedReport,
        BMCScoring,
    ]:
        record = db.scalar(
            select(model).where(model.assessment_id == assessment_id)
        )
        if record is not None:
            db.delete(record)

    # 3. 删除 1:N 子记录
    for record in db.scalars(
        select(FollowUpTask).where(FollowUpTask.assessment_id == assessment_id)
    ).all():
        db.delete(record)
    for record in db.scalars(
        select(PushRecord).where(PushRecord.assessment_id == assessment_id)
    ).all():
        db.delete(record)

    for record in db.scalars(
        select(AssessmentEntitlement).where(AssessmentEntitlement.assessment_id == assessment_id)
    ).all():
        db.delete(record)
    for record in db.scalars(
        select(PaymentOrder).where(PaymentOrder.assessment_id == assessment_id)
    ).all():
        db.delete(record)

    # 4. 清除 intake session 中的关联
    intake = db.scalar(
        select(AssessmentIntakeSession).where(
            AssessmentIntakeSession.created_assessment_id == assessment_id
        )
    )
    if intake is not None:
        intake.created_assessment_id = None

    # 5. 删除评估本身
    db.delete(assessment)
    db.commit()

    return Response(status_code=204)


@router.get(
    "/{assessment_id}",
    response_model=AssessmentDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_assessment_detail(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentDetailResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    assessment = _claim_orphaned_assessment_from_intake(db, assessment, current_user)
    _check_owner_or_instructor(assessment, current_user)
    entitlement = EntitlementService().get_status(db, assessment, current_user)
    report_service = ReportService()
    profile = _load_profile_from_assessment(assessment)
    canvas = _load_canvas_diagnosis(db, assessment_id)
    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id)
    scenarios = _load_scenario_recommendation(db, assessment_id)
    cases = _load_case_recommendation(db, assessment_id)
    report_summary = report_service.get_report_summary_by_assessment(db, assessment_id)
    direction_selection = _load_direction_selection(db, assessment_id)
    direction_expansion = _load_direction_expansion_result(db, assessment_id)
    competitiveness = _load_competitiveness_analysis(db, assessment_id)
    endgame = _load_endgame_analysis(db, assessment_id)

    competitiveness_response = None
    if competitiveness is not None:
        competitiveness_response = CompetitivenessResponse(
            assessment_id=competitiveness.assessment_id,
            result=_build_competitiveness_result_from_record(competitiveness),
            created_at=competitiveness.created_at,
            updated_at=competitiveness.updated_at,
        )

    endgame_response = None
    if endgame is not None:
        endgame_response = EndgameResponse(
            assessment_id=endgame.assessment_id,
            result=_build_endgame_result_from_record(endgame, assessment.industry),
            created_at=endgame.created_at.isoformat() if endgame.created_at else None,
            updated_at=endgame.updated_at.isoformat() if endgame.updated_at else None,
        )

    if not entitlement.can_continue:
        breakthrough_keys = None
        scenarios = None
        cases = None
        report_summary = None
        direction_selection = None
        direction_expansion = None
        competitiveness = None
        endgame = None
        competitiveness_response = None
        endgame_response = None

    return AssessmentDetailResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        entitlement=entitlement,
        company_profile=profile,
        canvas_diagnosis=canvas,
        breakthrough_selection=breakthrough_keys,
        direction_expansion=direction_expansion,
        direction_selection=direction_selection,
        scenario_recommendation=scenarios,
        competitiveness=competitiveness_response,
        endgame=endgame_response,
        case_recommendation=cases,
        generated_report=report_summary,
        progress=_build_progress(
            profile, canvas, breakthrough_keys, scenarios, cases, report_summary,
            direction_selection, competitiveness, endgame,
        ),
    )


@router.get(
    "/{assessment_id}/report-context",
    response_model=ReportContextResponse,
    status_code=status.HTTP_200_OK,
)
def get_report_context(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportContextResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    profile, canvas, scenarios = _require_report_prerequisites(db, assessment)
    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id) or []

    return ReportContextResponse(
        assessment_id=assessment.id,
        company_input=_build_assessment_input_snapshot(assessment),
        company_profile=profile,
        canvas_diagnosis=canvas,
        selected_breakthrough_elements=breakthrough_keys,
        top_scenarios=scenarios.top_scenarios,
        report_outline=REPORT_OUTLINE,
    )


@router.post(
    "/{assessment_id}/profile",
    response_model=AssessmentProfileResponse,
    status_code=status.HTTP_200_OK,
)
def generate_profile(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentProfileResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _check_owner_or_instructor(assessment, current_user)
    profile, generation_mode = _generate_and_store_profile(db, assessment)

    return AssessmentProfileResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        generation_mode=generation_mode,
        profile=profile,
    )


@router.post(
    "/{assessment_id}/canvas",
    response_model=AssessmentCanvasResponse,
    status_code=status.HTTP_200_OK,
)
def generate_canvas(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentCanvasResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _check_owner_or_instructor(assessment, current_user)
    profile, _ = _ensure_profile(db, assessment)
    llm_client = LLMClient()
    canvas_result, generation_mode = llm_client.generate_business_model_canvas(
        assessment,
        profile,
    )
    stored_canvas = _upsert_canvas_diagnosis(
        db=db,
        assessment_id=assessment.id,
        canvas_result=canvas_result,
        generation_mode=generation_mode,
    )

    return AssessmentCanvasResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        canvas_diagnosis=stored_canvas,
    )


class UpdateCanvasBlockRequest(BaseModel):
    key: str
    title: str
    current_state: str
    diagnosis: str
    ai_opportunity: str


class UpdateCanvasRequest(BaseModel):
    overall_summary: str
    blocks: list[UpdateCanvasBlockRequest]


class UpdateCompetitivenessRequest(BaseModel):
    vp_reconstruction: VPReconstruction
    connections: list[PointToLineConnection]
    advantages: list[CoreAdvantage]
    delivery_strategy: DeliveryStrategy
    overall_narrative: str


class UpdateEndgameRequest(BaseModel):
    industry_essence: str = ""
    private_domain: PrivateDomainDesign
    ecosystem: EcosystemDesign
    opc: OPCDesign
    three_stage_strategy: ThreeStageStrategy
    strategic_paths: list[StrategicPath]
    overall_narrative: str


@router.put(
    "/{assessment_id}/canvas",
    response_model=AssessmentCanvasResponse,
    status_code=status.HTTP_200_OK,
)
def update_canvas(
    assessment_id: str,
    payload: UpdateCanvasRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentCanvasResponse:
    """手动更新画布诊断内容，并清除下游数据以便基于新画布重新生成。"""
    assessment = _get_assessment_or_404(db, assessment_id)
    _check_owner_or_instructor(assessment, current_user)

    # Build updated canvas result from payload
    canvas_blocks = [
        CanvasBlockResult(
            key=b.key,
            title=b.title,
            current_state=b.current_state,
            diagnosis=b.diagnosis,
            ai_opportunity=b.ai_opportunity,
            missing_information="",
        )
        for b in payload.blocks
    ]
    canvas_result = BusinessModelCanvasResult(
        overall_summary=payload.overall_summary,
        blocks=canvas_blocks,
    )
    stored_canvas = _upsert_canvas_diagnosis(
        db=db,
        assessment_id=assessment.id,
        canvas_result=canvas_result,
        generation_mode="manual_edit",
    )

    _clear_breakthrough_and_below(db, assessment_id)

    return AssessmentCanvasResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        canvas_diagnosis=stored_canvas,
    )


@router.post(
    "/{assessment_id}/breakthrough/recommend",
    response_model=AssessmentBreakthroughResponse,
    status_code=status.HTTP_200_OK,
)
def recommend_breakthrough(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentBreakthroughResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    canvas = _require_canvas(db, assessment_id)

    recommendation = None
    enhancer = LLMEnhancer()
    llm_result = enhancer.enhance_breakthrough(canvas, assessment_id=assessment_id)
    if llm_result is not None:
        recommendation = llm_result
    else:
        recommender = BreakthroughRecommender()
        recommendation = recommender.recommend(canvas)

    existing = _load_breakthrough_selection(db, assessment_id)
    selection_response = None
    if existing is not None:
        selection_response = _build_breakthrough_selection_response(existing)

    return AssessmentBreakthroughResponse(
        assessment_id=assessment.id,
        breakthrough_recommendation=recommendation,
        breakthrough_selection=selection_response,
    )


@router.post(
    "/{assessment_id}/breakthrough/select",
    response_model=BreakthroughSelectionResponse,
    status_code=status.HTTP_200_OK,
)
def select_breakthrough(
    assessment_id: str,
    payload: BreakthroughSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BreakthroughSelectionResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    canvas = _require_canvas(db, assessment_id)
    recommender = BreakthroughRecommender()
    recommendation = recommender.recommend(canvas)

    selected_elements = _resolve_selected_elements(payload.selected_keys, recommendation)

    record = _upsert_breakthrough_selection(
        db=db,
        assessment_id=assessment_id,
        selection_mode=payload.selection_mode,
        recommended_elements=recommendation.elements,
        selected_elements=selected_elements,
    )

    return _build_breakthrough_selection_response(record)


@router.get(
    "/{assessment_id}/breakthrough",
    response_model=AssessmentBreakthroughResponse,
    status_code=status.HTTP_200_OK,
)
def get_breakthrough(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentBreakthroughResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    canvas = _require_canvas(db, assessment_id)
    recommender = BreakthroughRecommender()
    recommendation = recommender.recommend(canvas)

    existing = _load_breakthrough_selection(db, assessment_id)
    selection_response = None
    if existing is not None:
        selection_response = _build_breakthrough_selection_response(existing)

    return AssessmentBreakthroughResponse(
        assessment_id=assessment_id,
        breakthrough_recommendation=recommendation,
        breakthrough_selection=selection_response,
    )


@router.post(
    "/{assessment_id}/directions/expand",
    response_model=AssessmentDirectionResponse,
    status_code=status.HTTP_200_OK,
)
def expand_directions(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentDirectionResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id)
    if not breakthrough_keys or len(breakthrough_keys) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择突破要素，再展开创新方向。",
        )

    canvas = _require_canvas(db, assessment_id)

    # Phase 1: Instant rule-based expansion
    service = DirectionExpansionService()
    expansion = service.expand(breakthrough_keys)
    _clear_direction_selection_and_below(db, assessment_id)

    # Persist with pending LLM status
    record = _upsert_direction_expansion(
        db=db,
        assessment_id=assessment_id,
        expansion=expansion,
    )
    db.commit()

    # Phase 2: Background LLM enhancement (daemon thread, non-blocking)
    enhancer = LLMEnhancer()
    if enhancer._is_live_mode():
        canvas_json = canvas.model_dump_json()
        thread = threading.Thread(
            target=_background_enhance_directions,
            args=(assessment_id, canvas_json, breakthrough_keys),
            daemon=True,
        )
        thread.start()
    else:
        record.llm_status = "completed"
        db.commit()
        db.refresh(record)

    # Set llm_status on the response expansion
    expansion.llm_status = record.llm_status
    expansion.created_at = record.created_at
    expansion.updated_at = record.updated_at

    return AssessmentDirectionResponse(
        assessment_id=assessment_id,
        direction_expansion=expansion,
        direction_selection=None,
    )


@router.post(
    "/{assessment_id}/directions/select",
    response_model=DirectionSelectionResponse,
    status_code=status.HTTP_200_OK,
)
def select_directions(
    assessment_id: str,
    payload: DirectionSelectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DirectionSelectionResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id)
    if not breakthrough_keys or len(breakthrough_keys) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择突破要素，再确认创新方向。",
        )

    service = DirectionExpansionService()
    selected_directions, _ = _resolve_selected_directions_for_assessment(
        db,
        assessment_id,
        payload.selected_direction_ids,
    )
    if not selected_directions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择当前创新方向列表中的有效方向。",
        )

    record = _upsert_direction_selection(
        db=db,
        assessment_id=assessment_id,
        direction_ids=[direction.direction_id for direction in selected_directions],
        selected_directions=selected_directions,
    )

    return service.build_selection_response(record, selected_directions)


@router.get(
    "/{assessment_id}/directions",
    response_model=AssessmentDirectionResponse,
    status_code=status.HTTP_200_OK,
)
def get_directions(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentDirectionResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    record = _load_direction_expansion(db, assessment_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="请先生成创新方向延展。",
        )

    expansion = _normalize_direction_expansion(
        DirectionExpansionResult.model_validate_json(record.expansion_json)
    )
    expansion.generation_mode = record.generation_mode  # type: ignore[assignment]
    expansion.llm_status = record.llm_status  # type: ignore[assignment]
    expansion.created_at = record.created_at
    expansion.updated_at = record.updated_at

    selection_response = _load_direction_selection(db, assessment_id)

    return AssessmentDirectionResponse(
        assessment_id=assessment_id,
        direction_expansion=expansion,
        direction_selection=selection_response,
    )


@router.post(
    "/{assessment_id}/competitiveness/generate",
    response_model=CompetitivenessResponse,
    status_code=status.HTTP_200_OK,
)
def generate_competitiveness(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompetitivenessResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    canvas = _require_canvas(db, assessment_id)
    _require_scenarios(db, assessment_id)
    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id)
    if not breakthrough_keys or len(breakthrough_keys) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先选择突破要素，再生成竞争力分析。",
        )

    selected_directions = _load_selected_directions(db, assessment_id)
    if not selected_directions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先确认创新方向，再生成竞争力分析。",
        )

    result = None
    enhancer = LLMEnhancer()
    llm_result = enhancer.enhance_competitiveness(canvas, breakthrough_keys, selected_directions)
    if llm_result is not None:
        result = llm_result
    else:
        analyzer = CompetitivenessAnalyzer()
        result = analyzer.analyze(canvas, breakthrough_keys, selected_directions)

    record = _upsert_competitiveness_analysis(
        db=db,
        assessment_id=assessment_id,
        result=result,
    )

    return CompetitivenessResponse(
        assessment_id=record.assessment_id,
        result=result,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/{assessment_id}/competitiveness",
    response_model=CompetitivenessResponse,
    status_code=status.HTTP_200_OK,
)
def get_competitiveness(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompetitivenessResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    existing = _load_competitiveness_analysis(db, assessment_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="请先生成差异化竞争力分析。",
        )

    result = _build_competitiveness_result_from_record(existing)
    return CompetitivenessResponse(
        assessment_id=existing.assessment_id,
        result=result,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
    )


@router.put(
    "/{assessment_id}/competitiveness",
    response_model=CompetitivenessResponse,
    status_code=status.HTTP_200_OK,
)
def update_competitiveness(
    assessment_id: str,
    payload: UpdateCompetitivenessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompetitivenessResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    result = CompetitivenessResult(
        generation_mode="manual_edit",
        vp_reconstruction=payload.vp_reconstruction,
        connections=payload.connections,
        advantages=payload.advantages,
        delivery_strategy=payload.delivery_strategy,
        overall_narrative=payload.overall_narrative,
    )
    record = _upsert_competitiveness_analysis(
        db=db,
        assessment_id=assessment_id,
        result=result,
    )
    return CompetitivenessResponse(
        assessment_id=record.assessment_id,
        result=result,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post(
    "/{assessment_id}/endgame/generate",
    response_model=EndgameResponse,
    status_code=status.HTTP_200_OK,
)
def generate_endgame(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EndgameResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    canvas = _require_canvas(db, assessment_id)
    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id) or []
    selected_directions = _load_selected_directions(db, assessment_id)
    if not selected_directions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先确认创新方向，再生成商业终局设计。",
        )

    comp_record = _load_competitiveness_analysis(db, assessment_id)
    if comp_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先生成差异化竞争力分析，再生成商业终局设计。",
        )
    competitiveness_result = _build_competitiveness_result_from_record(comp_record)

    analyzer = EndgameAnalyzer()
    result = analyzer.analyze(
        industry=assessment.industry,
        canvas_diagnosis=canvas,
        breakthrough_keys=breakthrough_keys,
        selected_directions=selected_directions,
        competitiveness_result=competitiveness_result,
    )

    record = _upsert_endgame_analysis(db, assessment_id, result)

    return EndgameResponse(
        assessment_id=record.assessment_id,
        result=result,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


@router.get(
    "/{assessment_id}/endgame",
    response_model=EndgameResponse,
    status_code=status.HTTP_200_OK,
)
def get_endgame(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EndgameResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    existing = _load_endgame_analysis(db, assessment_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="请先生成商业终局设计。",
        )

    result = _build_endgame_result_from_record(existing, assessment.industry)
    return EndgameResponse(
        assessment_id=existing.assessment_id,
        result=result,
        created_at=existing.created_at.isoformat() if existing.created_at else None,
        updated_at=existing.updated_at.isoformat() if existing.updated_at else None,
    )


@router.put(
    "/{assessment_id}/endgame",
    response_model=EndgameResponse,
    status_code=status.HTTP_200_OK,
)
def update_endgame(
    assessment_id: str,
    payload: UpdateEndgameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EndgameResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    result = EndgameResult(
        generation_mode="manual_edit",
        industry_essence=payload.industry_essence
        or _derive_industry_essence(assessment.industry),
        private_domain=payload.private_domain,
        ecosystem=payload.ecosystem,
        opc=payload.opc,
        three_stage_strategy=payload.three_stage_strategy,
        strategic_paths=payload.strategic_paths,
        overall_narrative=payload.overall_narrative,
    )
    record = _upsert_endgame_analysis(db, assessment_id, result)
    return EndgameResponse(
        assessment_id=record.assessment_id,
        result=result,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


@router.post(
    "/{assessment_id}/scenarios",
    response_model=AssessmentScenarioRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/{assessment_id}/scenario-recommendations",
    response_model=AssessmentScenarioRecommendationResponse,
    status_code=status.HTTP_200_OK,
    deprecated=True,
)
def recommend_scenarios(
    assessment_id: str,
    mode: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentScenarioRecommendationResponse:
    """生成 Top 3 AI 场景推荐。

    默认使用四象限优先级评分算法（four_quadrant_v1）。
    可通过 ?mode=legacy 回退到旧关键词评分算法（rule_based_v1）。
    """
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    canvas = _require_canvas(db, assessment_id)
    profile = _load_profile_from_assessment(assessment)
    selected_directions = _load_selected_directions(db, assessment_id)
    if not selected_directions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先确认创新方向，再生成 AI 场景推荐。",
        )
    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id) or []
    breakthrough_labels = [ELEMENT_KEY_TO_TITLE.get(key, key) for key in breakthrough_keys]
    direction_titles = [direction.title for direction in selected_directions]
    direction_categories = _load_direction_categories(db, assessment_id)
    recommender = ScenarioRecommender()

    if mode == "legacy":
        top_recommendations, evaluated_count = recommender.recommend(
            assessment,
            profile,
            direction_categories,
            breakthrough_labels,
            direction_titles,
        )
        top_recommendations, _ = _enhance_scenario_description_fields(
            assessment=assessment,
            profile=profile,
            canvas=canvas,
            breakthrough_labels=breakthrough_labels,
            selected_directions=selected_directions,
            top_scenarios=top_recommendations,
            all_scores=None,
        )
        stored_scenarios = _upsert_scenario_recommendation(
            db=db,
            assessment_id=assessment.id,
            evaluated_count=evaluated_count,
            top_scenarios=top_recommendations,
            scoring_method="rule_based_v1",
        )
    else:
        priority_result = recommender.recommend_with_priority(
            assessment,
            profile,
            direction_categories,
            breakthrough_labels,
            direction_titles,
        )
        enhanced_top, enhanced_all = _enhance_scenario_description_fields(
            assessment=assessment,
            profile=profile,
            canvas=canvas,
            breakthrough_labels=breakthrough_labels,
            selected_directions=selected_directions,
            top_scenarios=priority_result.top_scenarios,
            all_scores=priority_result.all_scores,
        )
        stored_scenarios = _upsert_scenario_recommendation(
            db=db,
            assessment_id=assessment.id,
            evaluated_count=priority_result.evaluated_count,
            top_scenarios=enhanced_top,
            scoring_method=priority_result.scoring_method,
            all_scores=enhanced_all,
        )

    return AssessmentScenarioRecommendationResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        scenario_recommendation=stored_scenarios,
    )


@router.post(
    "/{assessment_id}/scenarios/priority",
    response_model=AssessmentScenarioRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
def recommend_scenarios_with_priority(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentScenarioRecommendationResponse:
    """使用四象限优先级评分引擎推荐 Top 3 AI 场景。

    先通过关键词评分从 24 个预定义场景中筛选候选，再使用
    ScenePriorityScorer 计算每个场景的 QS/LPS/LPS_display，
    最终按梯队+LPS_final 排序返回 Top 3。

    输出每个场景附带的 priority_* 字段：
    - priority_structuredness_x / priority_complexity_y: X/Y 评分
    - priority_qs: 象限定位得分
    - priority_lps / priority_lps_display: 落地优先级及展示分
    - priority_quadrant: 象限归属
    - priority_tier: 推荐梯队 (1=自动化主战场, 2=AI优先区, 3=人机协作区)
    - priority_recommendation: 推荐话术模板
    """
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    selected_directions = _load_selected_directions(db, assessment_id)
    if not selected_directions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先确认创新方向，再生成 AI 场景推荐。",
        )
    canvas = _require_canvas(db, assessment_id)
    profile = _load_profile_from_assessment(assessment)
    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id) or []
    breakthrough_labels = [ELEMENT_KEY_TO_TITLE.get(key, key) for key in breakthrough_keys]
    direction_titles = [direction.title for direction in selected_directions]
    direction_categories = _load_direction_categories(db, assessment_id)
    recommender = ScenarioRecommender()
    priority_result = recommender.recommend_with_priority(
        assessment,
        profile,
        direction_categories,
        breakthrough_labels,
        direction_titles,
    )
    enhanced_top, enhanced_all = _enhance_scenario_description_fields(
        assessment=assessment,
        profile=profile,
        canvas=canvas,
        breakthrough_labels=breakthrough_labels,
        selected_directions=selected_directions,
        top_scenarios=priority_result.top_scenarios,
        all_scores=priority_result.all_scores,
    )
    stored_scenarios = _upsert_scenario_recommendation(
        db=db,
        assessment_id=assessment.id,
        evaluated_count=priority_result.evaluated_count,
        top_scenarios=enhanced_top,
        scoring_method=priority_result.scoring_method,
        all_scores=enhanced_all,
    )

    return AssessmentScenarioRecommendationResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        scenario_recommendation=stored_scenarios,
    )


@router.post(
    "/{assessment_id}/scenarios/calibrations",
    response_model=AssessmentScenarioRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
def save_scenario_calibrations(
    assessment_id: str,
    body: ScenarioCalibrationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentScenarioRecommendationResponse:
    """保存人工校准后的 X/Y 评分，重算所有 priority_* 字段并更新 Top3。

    请求体包含校准后的场景列表，每个场景提供 scenario_id 和新的 X/Y 值。
    后端按四象限公式重算：QS, LPS, LPS_display, 象限, 梯队, 推荐等级。
    重新排序后更新 top_scenarios 和 all_scores。
    """
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)

    record = db.scalar(
        select(ScenarioRecommendation).where(
            ScenarioRecommendation.assessment_id == assessment_id
        )
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="请先生成场景推荐后再进行校准。",
        )

    raw_all = _parse_json_raw(record.all_scores_json or record.scenario_json, "场景数据解析失败")
    if not isinstance(raw_all, list) or len(raw_all) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前没有可校准的场景数据。",
        )

    all_items = _load_ranked_scenario_items_from_record(record)
    cal_map: dict[str, tuple[float, float]] = {
        c.scenario_id: (c.priority_structuredness_x, c.priority_complexity_y)
        for c in body.calibrations
    }

    # 构建原始 item 查找表，保留 summary/canvas_elements/expected_effects 等字段
    orig_by_id: dict[str, ScenarioRecommendationItem] = {item.scenario_id: item for item in all_items}

    # 构建 ScenePriorityInput 列表，应用校准后的 X/Y 值
    industry = (assessment.industry or "") if assessment else ""
    candidates: list[ScenePriorityInput] = []
    for item in all_items:
        if item.scenario_id in cal_map:
            new_x, new_y = cal_map[item.scenario_id]
        else:
            new_x = item.priority_structuredness_x or 3.0
            new_y = item.priority_complexity_y or 3.0
        candidates.append(ScenePriorityInput(
            scene_id=item.scenario_id,
            scene_name=item.name,
            category=item.category,
            summary=item.summary or "",
            structuredness_x=new_x,
            complexity_y=new_y,
            industry=industry,
            canvas_elements=item.canvas_elements or "",
            expected_effects=item.expected_effects or "",
            core_data_requirements=item.core_data_requirements or "",
            canvas_element=item.canvas_element or "",
            canvas_key=item.canvas_key or "",
            positioning=item.positioning or "",
            value_dimensions=item.value_dimensions or [],
            value_text=item.value_text or "",
            benefits=_scenario_benefit_payloads(item),
            resources=_scenario_resource_payloads(item),
        ))

    # 复用 ScenePriorityScorer 进行评分、排序、Q4 兜底、tie-break
    scorer = ScenePriorityScorer()
    result = scorer.recommend_top3(candidates)

    # 用 scorer 结果更新 all_items，保留原始非评分字段
    score_by_id = {s.scene_id: s for s in result.all_scores}
    updated_items: list[ScenarioRecommendationItem] = []
    for s in result.all_scores:
        orig = orig_by_id.get(s.scene_id)
        if orig is None:
            continue
        orig.priority_structuredness_x = s.structuredness_x
        orig.priority_complexity_y = s.complexity_y
        orig.priority_qs = s.qs
        orig.priority_lps = s.lps
        orig.priority_lps_display = s.lps_display
        orig.priority_quadrant = s.quadrant.value if hasattr(s.quadrant, "value") else str(s.quadrant)
        orig.priority_tier = s.priority_tier
        orig.recommendation_level = s.recommendation_label
        orig.industry_coefficient = s.industry_coefficient
        updated_items.append(orig)

    active_id_set = set(_load_active_scenario_ids_from_record(record, all_items))
    active_ranked_items = [
        item for item in updated_items if item.scenario_id in active_id_set
    ]
    new_top3 = _select_top_scenarios_for_active_items(
        active_ranked_items,
        industry,
    )

    record.all_scores_json = json.dumps(
        [item.model_dump() for item in updated_items], ensure_ascii=False,
    )
    record.scenario_json = json.dumps(
        [item.model_dump() for item in new_top3], ensure_ascii=False,
    )
    record.top_scenarios = json.dumps(
        [item.name for item in new_top3], ensure_ascii=False,
    )
    record.active_scenario_ids_json = json.dumps(
        [item.scenario_id for item in active_ranked_items],
        ensure_ascii=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 清理下游依赖：场景变动后，竞争力、终局和报告都需要重算
    _clear_competitiveness_outputs(db, assessment_id)

    return AssessmentScenarioRecommendationResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        scenario_recommendation=_build_scenario_recommendation_result_from_record(record),
    )


@router.put(
    "/{assessment_id}/scenarios/pool",
    response_model=AssessmentScenarioRecommendationResponse,
    status_code=status.HTTP_200_OK,
)
def update_scenario_pool(
    assessment_id: str,
    payload: ScenarioPoolUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentScenarioRecommendationResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    record = db.scalar(
        select(ScenarioRecommendation).where(
            ScenarioRecommendation.assessment_id == assessment_id
        )
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="请先生成候选场景池后再调整场景池。",
        )

    ranked_items = _load_ranked_scenario_items_from_record(record)
    if len(ranked_items) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前候选场景少于 3 个，暂时不能调整场景池。",
        )

    requested_ids = list(dict.fromkeys(payload.active_scenario_ids))
    ranked_ids = [item.scenario_id for item in ranked_items]
    ranked_id_set = set(ranked_ids)
    unknown_ids = [
        scenario_id for scenario_id in requested_ids if scenario_id not in ranked_id_set
    ]
    if unknown_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="场景池里包含未知场景 ID，请刷新候选场景后重试。",
        )

    requested_id_set = set(requested_ids)
    normalized_active_ids = [
        scenario_id for scenario_id in ranked_ids if scenario_id in requested_id_set
    ]
    if len(normalized_active_ids) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="有效场景池至少需要保留 3 个场景。",
        )

    previous_active_ids = _load_active_scenario_ids_from_record(record, ranked_items)
    if previous_active_ids != normalized_active_ids:
        active_id_set = set(normalized_active_ids)
        active_ranked_items = [
            item for item in ranked_items if item.scenario_id in active_id_set
        ]
        next_top_items = _select_top_scenarios_for_active_items(
            active_ranked_items,
            assessment.industry or "",
        )
        record.active_scenario_ids_json = json.dumps(
            normalized_active_ids,
            ensure_ascii=False,
        )
        record.all_scores_json = json.dumps(
            [item.model_dump() for item in ranked_items],
            ensure_ascii=False,
        )
        record.scenario_json = json.dumps(
            [item.model_dump() for item in next_top_items],
            ensure_ascii=False,
        )
        record.top_scenarios = json.dumps(
            [item.name for item in next_top_items],
            ensure_ascii=False,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        _clear_competitiveness_outputs(db, assessment_id)

    return AssessmentScenarioRecommendationResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        scenario_recommendation=_build_scenario_recommendation_result_from_record(record),
    )


@router.post(
    "/{assessment_id}/cases",
    response_model=AssessmentCaseResponse,
    status_code=status.HTTP_200_OK,
)
def match_cases(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssessmentCaseResponse:
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    profile = _require_profile(assessment)
    canvas = _require_canvas(db, assessment_id)
    scenarios = _require_scenarios(db, assessment_id)
    stored_cases = _match_and_store_cases(db, assessment, profile, canvas, scenarios)

    return AssessmentCaseResponse(
        assessment=AssessmentResponse.model_validate(assessment, from_attributes=True),
        case_recommendation=stored_cases,
    )


@router.post(
    "/{assessment_id}/report",
    response_model=ReportDocumentResponse,
    status_code=status.HTTP_200_OK,
)
def generate_report(
    assessment_id: str,
    mode: str = "template",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportDocumentResponse:
    """Generate report with specified mode.

    Args:
        mode: "template" (default), "llm", or "template_fallback"
            - template: Always use template-based generation
            - llm: Use LLM deep writing, fallback to template if LLM unavailable
            - template_fallback: Prefer template with LLM enhancement when available
    """
    from app.services.llm_report_writer import LLMReportWriter

    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    profile, canvas, scenarios = _require_report_prerequisites(db, assessment)

    cases = _load_case_recommendation(db, assessment_id)
    if cases is None:
        cases = _match_and_store_cases(db, assessment, profile, canvas, scenarios)

    breakthrough_keys = _load_breakthrough_selection_keys(db, assessment_id) or []
    direction_labels = _load_direction_labels(db, assessment_id)
    selected_directions = _load_selected_directions(db, assessment_id)
    competitiveness_record = _load_competitiveness_analysis(db, assessment_id)
    competitiveness_result = _build_competitiveness_result_from_record(competitiveness_record) if competitiveness_record else None

    enrichment_service = ReportEnrichmentService()
    enrichment = enrichment_service.enrich(
        assessment=assessment,
        profile=profile,
        canvas=canvas,
        scenarios=scenarios,
        breakthrough_keys=breakthrough_keys,
        direction_labels=direction_labels,
        competitiveness_result=competitiveness_result,
        allow_llm=mode in ("llm", "template_fallback"),
    )

    endgame_record = _load_endgame_analysis(db, assessment_id)
    endgame_result = (
        _build_endgame_result_from_record(endgame_record, assessment.industry)
        if endgame_record
        else None
    )

    # Validate mode
    valid_modes = ("template", "llm", "template_fallback")
    if mode not in valid_modes:
        mode = "template"

    # Use LLMReportWriter which handles fallback logic
    llm_writer = LLMReportWriter()
    report_data, metadata = llm_writer.build(
        assessment=assessment,
        profile=profile,
        canvas_diagnosis=canvas,
        scenario_recommendation=scenarios,
        case_recommendation=cases,
        breakthrough_keys=breakthrough_keys,
        direction_labels=direction_labels,
        selected_directions=selected_directions,
        competitiveness_result=competitiveness_result,
        enrichment_result=enrichment,
        endgame_result=endgame_result,
        mode=mode,
    )

    report_service = ReportService()
    response = report_service.save_report(
        db=db,
        assessment_id=assessment.id,
        report_data=report_data,
        generation_mode=metadata.get("generation_mode", "template"),
        metadata=metadata,
    )

    record = report_service.get_report_or_404(db, response.report_id)
    report_service.save_enrichment(db, record, enrichment)

    return response


def _get_assessment_or_404(db: Session, assessment_id: str) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found.",
        )
    return assessment


def _build_assessment_input_snapshot(
    assessment: Assessment,
) -> AssessmentInputSnapshot:
    return AssessmentInputSnapshot(
        company_name=assessment.company_name,
        industry=assessment.industry,
        company_size=assessment.company_size,
        region=assessment.region,
        annual_revenue_range=assessment.annual_revenue_range,
        core_products=assessment.core_products,
        target_customers=assessment.target_customers,
        current_challenges=assessment.current_challenges,
        ai_goals=assessment.ai_goals,
        available_data=assessment.available_data,
        notes=assessment.notes,
    )


def _parse_json_payload(payload: str, model_class, detail_message: str):
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_message,
        ) from exc

    try:
        return model_class.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_message,
        ) from exc


def _parse_json_raw(payload: str, detail_message: str):
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_message,
        ) from exc


def _parse_json_string_list(payload: str, detail_message: str) -> list[str]:
    raw = _parse_json_raw(payload, detail_message)
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail_message,
        )
    return raw


def _load_ranked_scenario_items_from_record(
    record: ScenarioRecommendation,
) -> list[ScenarioRecommendationItem]:
    raw_items = _parse_json_raw(
        record.all_scores_json or record.scenario_json,
        "Failed to parse stored scenario recommendation for this assessment.",
    )
    if not isinstance(raw_items, list) or len(raw_items) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current scenario data is empty for this assessment.",
        )

    try:
        items = [ScenarioRecommendationItem.model_validate(item) for item in raw_items]
        return [_ensure_structured_scenario_fields_compat(item) for item in items]
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse stored scenario recommendation for this assessment.",
        ) from exc


def _load_top_scenario_items_from_record(
    record: ScenarioRecommendation,
) -> list[ScenarioRecommendationItem]:
    raw_items = _parse_json_raw(
        record.scenario_json,
        "Failed to parse stored top scenario recommendation for this assessment.",
    )
    if not isinstance(raw_items, list) or len(raw_items) == 0:
        return []

    try:
        items = [ScenarioRecommendationItem.model_validate(item) for item in raw_items]
        return [_ensure_structured_scenario_fields_compat(item) for item in items]
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse stored top scenario recommendation for this assessment.",
        ) from exc


_LEGACY_SECTION_MARKERS = (
    "对应突破要素",
    "战略定位",
    "战略价值",
    "预期收益",
    "资源准备",
)


def _sanitize_legacy_text(value: str) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    # Collapse excessive blank lines.
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def _compact_one_liner(value: str, max_len: int = 28) -> str:
    text = _sanitize_legacy_text(value)
    if not text:
        return ""
    # Prefer the first non-empty line.
    line = next((ln.strip() for ln in text.split("\n") if ln.strip()), "")
    if not line:
        return ""
    # Strip common legacy section prefixes.
    for prefix in ("战略定位", "对应突破要素", "战略价值", "预期收益", "资源准备"):
        if prefix in line[:8]:
            line = line.split(prefix, 1)[-1].lstrip("：: -—\t")
            break
    if len(line) <= max_len:
        return line
    return line[:max_len].rstrip("，。；;、,") + "…"


def _extract_between_markers(
    text: str,
    start_markers: tuple[str, ...],
    end_markers: tuple[str, ...],
) -> str:
    raw = _sanitize_legacy_text(text)
    if not raw:
        return ""

    start_pos = None
    start_marker_len = 0
    for marker in start_markers:
        idx = raw.find(marker)
        if idx == -1:
            continue
        if start_pos is None or idx < start_pos:
            start_pos = idx
            start_marker_len = len(marker)
    if start_pos is None:
        return ""

    content_start = start_pos + start_marker_len
    # Skip delimiters after the marker.
    while content_start < len(raw) and raw[content_start] in "：: \t\n】-—":
        content_start += 1

    content_end = len(raw)
    for marker in end_markers:
        idx = raw.find(marker, content_start)
        if idx != -1:
            content_end = min(content_end, idx)
    return raw[content_start:content_end].strip()


def _split_bullets(value: str, max_items: int = 4) -> list[str]:
    import re

    text = _sanitize_legacy_text(value)
    if not text:
        return []
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # Remove typical bullet prefixes.
        line = re.sub(r"^(?:[\\-\\*•]+|\\d+[\\.\\)\\]]|[①②③④⑤⑥⑦⑧⑨⑩]+)\\s*", "", line).strip()
        if not line:
            continue
        lines.append(line)
    # De-dup while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        uniq.append(line)
        if len(uniq) >= max_items:
            break
    return uniq


def _ensure_structured_scenario_fields(
    item: ScenarioRecommendationItem,
) -> ScenarioRecommendationItem:
    summary = _sanitize_legacy_text(item.summary or "")
    canvas_elements = _sanitize_legacy_text(item.canvas_elements or "")
    expected_effects = _sanitize_legacy_text(item.expected_effects or "")
    core_data = _sanitize_legacy_text(item.core_data_requirements or "")

    # 1) canvas_element: must be short, otherwise frontend uses canvas_elements as a tag.
    if not item.canvas_element:
        item.canvas_element = (item.category or "").strip()

    # 2) positioning: short one-liner derived from summary; fallback to scenario name.
    if not item.positioning:
        item.positioning = _compact_one_liner(summary) or _compact_one_liner(item.name, max_len=18)

    # 3) value_text: try to extract "战略价值" section from legacy canvas_elements; fallback to the whole canvas_elements.
    if not item.value_text:
        value_text = _extract_between_markers(
            canvas_elements,
            start_markers=("战略价值", "① 战略价值", "1. 战略价值", "1) 战略价值"),
            end_markers=("预期收益", "② 预期收益", "2. 预期收益", "资源准备", "③ 资源准备", "3. 资源准备"),
        )
        if not value_text and canvas_elements:
            # If canvas_elements is already short, keep it; otherwise pick the first paragraph.
            paras = [p.strip() for p in canvas_elements.split("\n\n") if p.strip()]
            value_text = paras[0] if paras else canvas_elements
        item.value_text = value_text

    # 4) benefits/resources: best-effort parsing from legacy expected_effects/core_data_requirements.
    if not item.benefits:
        benefit_text = _extract_between_markers(
            expected_effects,
            start_markers=("预期收益", "② 预期收益", "2. 预期收益"),
            end_markers=("资源准备", "③ 资源准备", "3. 资源准备"),
        ) or expected_effects
        benefit_lines = _split_bullets(benefit_text)
        if benefit_lines:
            item.benefits = [ScenarioBenefit(text=line, canvas="") for line in benefit_lines]

    if not item.resources:
        resource_text = _extract_between_markers(
            core_data,
            start_markers=("资源准备", "③ 资源准备", "3. 资源准备"),
            end_markers=(),
        ) or core_data
        resource_lines = _split_bullets(resource_text)
        if resource_lines:
            resources: list[ScenarioResource] = []
            for line in resource_lines:
                label = "准备"
                text = line
                if "：" in line:
                    left, right = line.split("：", 1)
                    if left.strip() and right.strip():
                        label = left.strip()
                        text = right.strip()
                elif ":" in line:
                    left, right = line.split(":", 1)
                    if left.strip() and right.strip():
                        label = left.strip()
                        text = right.strip()
                resources.append(ScenarioResource(type="resource", label=label, text=text))
            item.resources = resources

    # Keep dimensions empty; it's safe and doesn't change scoring.
    return item


_LEGACY_BREAKTHROUGH_MARKER_ASCII = "\u5bf9\u5e94\u7a81\u7834\u8981\u7d20"
_LEGACY_DIRECTION_MARKER_ASCII = "\u5bf9\u5e94\u521b\u65b0\u65b9\u5411"
_LEGACY_POSITIONING_MARKER_ASCII = "\u6218\u7565\u5b9a\u4f4d"
_LEGACY_VALUE_MARKER_ASCII = "\u6218\u7565\u4ef7\u503c"
_LEGACY_BENEFIT_MARKER_ASCII = "\u9884\u671f\u6536\u76ca"
_LEGACY_RESOURCE_MARKER_ASCII = "\u8d44\u6e90\u51c6\u5907"
_LEGACY_MARKERS_ASCII = (
    _LEGACY_BREAKTHROUGH_MARKER_ASCII,
    _LEGACY_DIRECTION_MARKER_ASCII,
    _LEGACY_POSITIONING_MARKER_ASCII,
    _LEGACY_VALUE_MARKER_ASCII,
    _LEGACY_BENEFIT_MARKER_ASCII,
    _LEGACY_RESOURCE_MARKER_ASCII,
)
_CANVAS_COMPAT_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("\u5ba2\u6237\u7ec6\u5206", "customer_segments", "CS"),
    ("\u4ef7\u503c\u4e3b\u5f20", "value_propositions", "VP"),
    ("\u6e20\u9053\u901a\u8def", "channels", "CH"),
    ("\u5ba2\u6237\u5173\u7cfb", "customer_relationships", "CR"),
    ("\u6536\u5165\u6765\u6e90", "revenue_streams", "R$"),
    ("\u6838\u5fc3\u8d44\u6e90", "key_resources", "KR"),
    ("\u5173\u952e\u8d44\u6e90", "key_resources", "KR"),
    ("\u6838\u5fc3\u4e1a\u52a1", "key_activities", "KA"),
    ("\u5173\u952e\u4e1a\u52a1", "key_activities", "KA"),
    ("\u5173\u952e\u4e1a\u52a1\u6d3b\u52a8", "key_activities", "KA"),
    ("\u91cd\u8981\u5408\u4f5c", "key_partnerships", "KP"),
    ("\u5173\u952e\u5408\u4f5c\u4f19\u4f34", "key_partnerships", "KP"),
    ("\u6210\u672c\u7ed3\u6784", "cost_structure", "C$"),
)


def _compat_strip_marker_prefix(value: str) -> str:
    text = _sanitize_legacy_text(value)
    if not text:
        return ""
    marker_pattern = "|".join(re.escape(marker) for marker in _LEGACY_MARKERS_ASCII)
    text = re.sub(
        rf"^(?:{marker_pattern})(?:\s*[\uff1a:]\s*|\s+)",
        "",
        text,
        count=1,
    )
    return text.strip(" \t\n\uff0c\u3002\uff1b;-.")


def _compat_compact_line(value: str, max_len: int = 18) -> str:
    text = _compat_strip_marker_prefix(value)
    if not text:
        return ""
    line = next((ln.strip() for ln in text.split("\n") if ln.strip()), "")
    line = re.sub(r"\s+", " ", line).strip()
    if not line:
        return ""
    if len(line) <= max_len:
        return line
    return line[:max_len].rstrip(" \t\n\uff0c\u3002\uff1b;") + "..."


def _compat_extract_section(
    text: str,
    start_markers: tuple[str, ...],
    end_markers: tuple[str, ...],
) -> str:
    raw = _sanitize_legacy_text(text)
    if not raw:
        return ""
    start_pos = None
    start_len = 0
    for marker in start_markers:
        idx = raw.find(marker)
        if idx == -1:
            continue
        if start_pos is None or idx < start_pos:
            start_pos = idx
            start_len = len(marker)
    if start_pos is None:
        return ""
    content_start = start_pos + start_len
    while content_start < len(raw) and raw[content_start] in " \t\n\uff1a:;,\uff0c\u3002-":
        content_start += 1
    content_end = len(raw)
    for marker in end_markers:
        idx = raw.find(marker, content_start)
        if idx != -1:
            content_end = min(content_end, idx)
    return raw[content_start:content_end].strip()


def _compat_split_points(value: str, max_items: int = 4) -> list[str]:
    text = _sanitize_legacy_text(value)
    if not text:
        return []
    pieces = re.split(r"\n+|[；;](?!\d)", text)
    points: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        line = piece.strip()
        if not line:
            continue
        line = re.sub(
            r"^(?:[-*+•·]|\d+[.)\]]|[①②③④⑤⑥⑦⑧⑨⑩])\s*",
            "",
            line,
        ).strip()
        line = _compat_strip_marker_prefix(line)
        if not line or line in seen:
            continue
        seen.add(line)
        points.append(line)
        if len(points) >= max_items:
            break
    return points


def _compat_resolve_canvas_metadata(value: str) -> tuple[str, str, str]:
    text = _sanitize_legacy_text(value)
    if not text:
        return "", "", ""
    breakthrough_text = _compat_extract_section(
        text,
        start_markers=(_LEGACY_BREAKTHROUGH_MARKER_ASCII,),
        end_markers=(
            _LEGACY_DIRECTION_MARKER_ASCII,
            _LEGACY_POSITIONING_MARKER_ASCII,
            _LEGACY_VALUE_MARKER_ASCII,
        ),
    )
    for haystack in (breakthrough_text, text):
        for title, key, abbr in _CANVAS_COMPAT_ALIASES:
            if title in haystack:
                return title, key, abbr
    return "", "", ""


def _compat_render_canvas_label(title: str, abbr: str) -> str:
    if not title:
        return ""
    return f"{title}\uff08{abbr}\uff09" if abbr else title


def _compat_extract_positioning(summary: str, fallback_name: str) -> str:
    text = _sanitize_legacy_text(summary)
    if text:
        match = re.search(
            rf"{re.escape(_LEGACY_POSITIONING_MARKER_ASCII)}(?:\s*[\uff1a:]\s*|\s*[是为]\s*)([^。\n；;]{2,40})",
            text,
        )
        if match:
            return _compat_compact_line(match.group(1), max_len=18)
    return _compat_compact_line(text, max_len=18) or _compat_compact_line(fallback_name, max_len=18)


def _compat_needs_value_backfill(value_text: str) -> bool:
    text = _sanitize_legacy_text(value_text)
    if not text:
        return True
    noisy_markers = (
        _LEGACY_BREAKTHROUGH_MARKER_ASCII,
        _LEGACY_DIRECTION_MARKER_ASCII,
        _LEGACY_POSITIONING_MARKER_ASCII,
        _LEGACY_BENEFIT_MARKER_ASCII,
        _LEGACY_RESOURCE_MARKER_ASCII,
    )
    return any(marker in text for marker in noisy_markers)


def _compat_infer_resource_meta(value: str) -> tuple[str, str]:
    text = _sanitize_legacy_text(value)
    if re.search(r"\u98ce\u9669|\u504f\u5dee|\u5931\u8d25|\u5ef6\u8bef|\u8bef\u5224", text):
        return "risk", "\u5173\u952e\u98ce\u9669"
    if re.search(r"\u56e2\u961f|\u6d41\u7a0b|\u534f\u540c|\u7ec4\u7ec7|\u57f9\u8bad|\u8fd0\u8425", text):
        return "org", "\u7ec4\u7ec7\u51c6\u5907"
    if re.search(r"\u9884\u7b97|\u91c7\u8d2d|\u6295\u5165|\u6295\u8d44|\u5f00\u53d1|\u5efa\u8bbe", text):
        return "invest", "\u6295\u5165\u95e8\u69db"
    return "data", "\u6570\u636e\u57fa\u7840"


def _ensure_structured_scenario_fields_compat(
    item: ScenarioRecommendationItem,
) -> ScenarioRecommendationItem:
    summary = _sanitize_legacy_text(item.summary or "")
    canvas_elements = _sanitize_legacy_text(item.canvas_elements or "")
    expected_effects = _sanitize_legacy_text(item.expected_effects or "")
    core_data = _sanitize_legacy_text(item.core_data_requirements or "")

    canvas_title, canvas_key, canvas_abbr = _compat_resolve_canvas_metadata(
        "\n".join(part for part in (item.canvas_element, canvas_elements) if part)
    )
    canvas_label = _compat_render_canvas_label(canvas_title, canvas_abbr)
    benefit_canvas = (
        f"{canvas_title} {canvas_abbr}".strip()
        if canvas_title
        else (canvas_abbr or (item.category or "").strip() or "\u4e1a\u52a1\u76ee\u6807")
    )

    if not item.canvas_element:
        item.canvas_element = canvas_label or (item.category or "").strip()
    if not item.canvas_key and canvas_key:
        item.canvas_key = canvas_key

    if not item.positioning or len(_sanitize_legacy_text(item.positioning)) > 40:
        item.positioning = _compat_extract_positioning(summary, item.name)

    if _compat_needs_value_backfill(item.value_text):
        value_text = _compat_extract_section(
            canvas_elements,
            start_markers=(_LEGACY_VALUE_MARKER_ASCII,),
            end_markers=(_LEGACY_BENEFIT_MARKER_ASCII, _LEGACY_RESOURCE_MARKER_ASCII),
        )
        if not value_text:
            value_text = _sanitize_legacy_text(canvas_elements)
        item.value_text = _compat_strip_marker_prefix(value_text)

    if not item.benefits:
        benefit_text = _compat_extract_section(
            expected_effects,
            start_markers=(_LEGACY_BENEFIT_MARKER_ASCII,),
            end_markers=(_LEGACY_RESOURCE_MARKER_ASCII,),
        ) or expected_effects
        benefit_lines = _compat_split_points(benefit_text, max_items=4)
        if benefit_lines:
            item.benefits = [
                ScenarioBenefit(text=line, canvas=benefit_canvas)
                for line in benefit_lines
            ]
    else:
        item.benefits = [
            ScenarioBenefit(
                text=benefit.text,
                canvas=benefit.canvas or benefit_canvas,
            )
            for benefit in item.benefits
        ]

    if not item.resources:
        resource_text = _compat_extract_section(
            core_data,
            start_markers=(_LEGACY_RESOURCE_MARKER_ASCII,),
            end_markers=(),
        ) or core_data
        resource_lines = _compat_split_points(resource_text, max_items=4)
        if resource_lines:
            item.resources = []
            for line in resource_lines:
                normalized_line = _sanitize_legacy_text(line)
                label = ""
                text = normalized_line
                match = re.match(r"^(.{1,8})[\uff1a:]\s*(.+)$", normalized_line)
                if match:
                    label = match.group(1).strip()
                    text = match.group(2).strip()
                resource_type, fallback_label = _compat_infer_resource_meta(
                    label or text
                )
                item.resources.append(
                    ScenarioResource(
                        type=resource_type,
                        label=label or fallback_label,
                        text=text,
                    )
                )
    else:
        item.resources = [
            ScenarioResource(
                type=resource.type or _compat_infer_resource_meta(
                    f"{resource.label} {resource.text}".strip()
                )[0],
                label=resource.label or _compat_infer_resource_meta(resource.text)[1],
                text=resource.text,
            )
            for resource in item.resources
        ]

    return item


def _load_active_scenario_ids_from_record(
    record: ScenarioRecommendation,
    ranked_items: list[ScenarioRecommendationItem],
) -> list[str]:
    ranked_ids = [item.scenario_id for item in ranked_items]
    if not ranked_ids:
        return []

    if not record.active_scenario_ids_json:
        return ranked_ids

    try:
        parsed_active_ids = _parse_json_string_list(
            record.active_scenario_ids_json,
            "Failed to parse stored active scenario ids for this assessment.",
        )
    except HTTPException:
        return ranked_ids

    parsed_active_set = set(parsed_active_ids)
    normalized_active_ids = [
        scenario_id for scenario_id in ranked_ids if scenario_id in parsed_active_set
    ]
    if len(normalized_active_ids) >= min(3, len(ranked_ids)):
        return normalized_active_ids
    return ranked_ids


def _scenario_benefit_payloads(item: ScenarioRecommendationItem) -> list[dict]:
    if not item.benefits:
        return []
    return [
        benefit.model_dump() if hasattr(benefit, "model_dump") else dict(benefit)
        for benefit in item.benefits
    ]


def _scenario_resource_payloads(item: ScenarioRecommendationItem) -> list[dict]:
    if not item.resources:
        return []
    return [
        resource.model_dump() if hasattr(resource, "model_dump") else dict(resource)
        for resource in item.resources
    ]


def _build_priority_inputs_from_items(
    items: list[ScenarioRecommendationItem],
    industry: str,
) -> list[ScenePriorityInput]:
    return [
        ScenePriorityInput(
            scene_id=item.scenario_id,
            scene_name=item.name,
            category=item.category,
            summary=item.summary or "",
            structuredness_x=float(item.priority_structuredness_x or 3.0),
            complexity_y=float(item.priority_complexity_y or 3.0),
            industry=industry,
            canvas_elements=item.canvas_elements or "",
            expected_effects=item.expected_effects or "",
            core_data_requirements=item.core_data_requirements or "",
            canvas_element=item.canvas_element or "",
            canvas_key=item.canvas_key or "",
            positioning=item.positioning or "",
            value_dimensions=item.value_dimensions or [],
            value_text=item.value_text or "",
            benefits=_scenario_benefit_payloads(item),
            resources=_scenario_resource_payloads(item),
        )
        for item in items
    ]


def _select_top_scenarios_for_active_items(
    active_items: list[ScenarioRecommendationItem],
    industry: str,
) -> list[ScenarioRecommendationItem]:
    if not active_items:
        return []

    scorer = ScenePriorityScorer()
    priority_result = scorer.recommend_top3(
        _build_priority_inputs_from_items(active_items, industry),
    )
    by_id = {item.scenario_id: item for item in active_items}
    selected: list[ScenarioRecommendationItem] = []
    for score in priority_result.top_3:
        item = by_id.get(score.scene_id)
        if item is not None:
            selected.append(item)
    return selected


def _build_scenario_recommendation_result_from_record(
    record: ScenarioRecommendation,
) -> ScenarioRecommendationResult:
    ranked_items = _load_ranked_scenario_items_from_record(record)
    stored_top_items = _load_top_scenario_items_from_record(record)
    active_ids = _load_active_scenario_ids_from_record(record, ranked_items)
    active_id_set = set(active_ids)
    active_items = [
        item for item in ranked_items if item.scenario_id in active_id_set
    ]
    excluded_items = [
        item for item in ranked_items if item.scenario_id not in active_id_set
    ]
    active_by_id = {item.scenario_id: item for item in active_items}
    top_scenarios = [
        active_by_id.get(item.scenario_id, item)
        for item in stored_top_items
        if item.scenario_id in active_id_set
    ]
    if len(top_scenarios) < min(3, len(active_items)):
        seen_ids = {item.scenario_id for item in top_scenarios}
        for item in active_items:
            if item.scenario_id in seen_ids:
                continue
            top_scenarios.append(item)
            seen_ids.add(item.scenario_id)
            if len(top_scenarios) >= min(3, len(active_items)):
                break

    return ScenarioRecommendationResult(
        scoring_method=record.scoring_method,
        evaluated_count=record.evaluated_count,
        top_scenarios=top_scenarios,
        all_scores=active_items if record.all_scores_json else None,
        active_count=len(active_items),
        excluded_scores=excluded_items,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _enhance_scenario_description_fields(
    assessment: Assessment,
    profile: CompanyProfileResult | None,
    canvas: CanvasDiagnosisResult,
    breakthrough_labels: list[str],
    selected_directions: list,
    top_scenarios: list[ScenarioRecommendationItem],
    all_scores: list[ScenarioRecommendationItem] | None,
) -> tuple[list[ScenarioRecommendationItem], list[ScenarioRecommendationItem] | None]:
    if not top_scenarios:
        return top_scenarios, all_scores

    enhancer = LLMEnhancer()
    enhanced_top = enhancer.enhance_scenario_descriptions(
        assessment=assessment,
        profile=profile,
        canvas_diagnosis=canvas,
        breakthrough_labels=breakthrough_labels,
        selected_directions=selected_directions,
        scenarios=top_scenarios,
    )
    if enhanced_top is None:
        return top_scenarios, all_scores

    enhanced_by_id = {item.scenario_id: item for item in enhanced_top}
    merged_top = [
        enhanced_by_id.get(item.scenario_id, item) for item in top_scenarios
    ]
    if all_scores is None:
        return merged_top, None

    merged_all = [
        enhanced_by_id.get(item.scenario_id, item) for item in all_scores
    ]
    return merged_top, merged_all


def _load_profile_from_assessment(
    assessment: Assessment,
) -> CompanyProfileResult | None:
    if not assessment.profile_payload:
        return None
    return _parse_json_payload(
        assessment.profile_payload,
        CompanyProfileResult,
        "Failed to parse stored company profile for this assessment.",
    )


def _load_canvas_diagnosis(
    db: Session,
    assessment_id: str,
) -> CanvasDiagnosisResult | None:
    record = db.scalar(
        select(CanvasDiagnosis).where(CanvasDiagnosis.assessment_id == assessment_id)
    )
    if record is None:
        return None

    return CanvasDiagnosisResult(
        generation_mode=record.generation_mode,
        overall_score=record.overall_score,
        weakest_blocks=_parse_json_string_list(
            record.weakest_blocks,
            "Failed to parse stored weakest canvas blocks for this assessment.",
        ),
        recommended_focus=_parse_json_string_list(
            record.recommended_focus,
            "Failed to parse stored recommended focus for this assessment.",
        ),
        canvas=_parse_json_payload(
            record.canvas_json,
            BusinessModelCanvasResult,
            "Failed to parse stored canvas diagnosis for this assessment.",
        ),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _load_scenario_recommendation(
    db: Session,
    assessment_id: str,
) -> ScenarioRecommendationResult | None:
    record = db.scalar(
        select(ScenarioRecommendation).where(
            ScenarioRecommendation.assessment_id == assessment_id
        )
    )
    if record is None:
        return None
    return _build_scenario_recommendation_result_from_record(record)


def _load_case_recommendation(
    db: Session,
    assessment_id: str,
) -> CaseRecommendationResult | None:
    record = db.scalar(
        select(CaseRecommendation).where(
            CaseRecommendation.assessment_id == assessment_id
        )
    )
    if record is None:
        return None

    raw_top_cases = _parse_json_raw(
        record.case_json,
        "Failed to parse stored case recommendation for this assessment.",
    )
    _parse_json_string_list(
        record.top_cases,
        "Failed to parse stored top case titles for this assessment.",
    )
    if not isinstance(raw_top_cases, list):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse stored case recommendation for this assessment.",
        )

    try:
        validated_cases = [CaseMatchItem.model_validate(item) for item in raw_top_cases]
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse stored case recommendation for this assessment.",
        ) from exc

    return CaseRecommendationResult(
        scoring_method=record.scoring_method,
        evaluated_count=record.evaluated_count,
        top_cases=validated_cases,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _require_profile(assessment: Assessment) -> CompanyProfileResult:
    profile = _load_profile_from_assessment(assessment)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company profile has not been generated for this assessment.",
        )
    return profile


def _require_canvas(db: Session, assessment_id: str) -> CanvasDiagnosisResult:
    canvas = _load_canvas_diagnosis(db, assessment_id)
    if canvas is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Canvas diagnosis has not been generated for this assessment.",
        )
    return canvas


def _load_breakthrough_selection(
    db: Session,
    assessment_id: str,
) -> BreakthroughSelection | None:
    return db.scalar(
        select(BreakthroughSelection).where(
            BreakthroughSelection.assessment_id == assessment_id
        )
    )


def _load_breakthrough_selection_keys(
    db: Session,
    assessment_id: str,
) -> list[str] | None:
    record = _load_breakthrough_selection(db, assessment_id)
    if record is None:
        return None
    return _parse_json_string_list(
        record.selected_elements_json,
        "Failed to parse stored breakthrough selection.",
    )


def _resolve_selected_elements(
    selected_keys: list[str],
    recommendation: BreakthroughRecommendationResult,
) -> list[BreakthroughElement]:
    element_map = {e.key: e for e in recommendation.elements}
    resolved: list[BreakthroughElement] = []
    for key in selected_keys:
        if key in element_map:
            resolved.append(element_map[key])
        else:
            resolved.append(
                BreakthroughElement(
                    key=key,
                    title=ELEMENT_KEY_TO_TITLE.get(key, key),
                    score=0,
                    reason="",
                    ai_opportunity="",
                )
            )
    return resolved


def _upsert_breakthrough_selection(
    db: Session,
    assessment_id: str,
    selection_mode: str,
    recommended_elements: list[BreakthroughElement],
    selected_elements: list[BreakthroughElement],
) -> BreakthroughSelection:
    record = _load_breakthrough_selection(db, assessment_id)
    if record is None:
        record = BreakthroughSelection(
            assessment_id=assessment_id,
            selection_mode=selection_mode,
            recommended_elements_json="[]",
            selected_elements_json="[]",
        )

    record.selection_mode = selection_mode
    record.recommended_elements_json = json.dumps(
        [e.model_dump() for e in recommended_elements], ensure_ascii=False
    )
    record.selected_elements_json = json.dumps(
        [e.key for e in selected_elements], ensure_ascii=False
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    _clear_directions_and_below(db, assessment_id)

    return record


def _build_breakthrough_selection_response(
    record: BreakthroughSelection,
) -> BreakthroughSelectionResponse:
    recommended = [
        BreakthroughElement.model_validate(item)
        for item in _parse_json_raw(
            record.recommended_elements_json,
            "Failed to parse breakthrough recommendation.",
        )
    ]

    selected_keys = _parse_json_string_list(
        record.selected_elements_json,
        "Failed to parse breakthrough selection.",
    )
    selected = [e for e in recommended if e.key in selected_keys]

    return BreakthroughSelectionResponse(
        assessment_id=record.assessment_id,
        selection_mode=record.selection_mode,
        recommended_elements=recommended,
        selected_elements=selected,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _load_direction_selection_record(
    db: Session,
    assessment_id: str,
) -> DirectionSelection | None:
    return db.scalar(
        select(DirectionSelection).where(
            DirectionSelection.assessment_id == assessment_id
        )
    )


def _load_direction_selection(
    db: Session,
    assessment_id: str,
) -> DirectionSelectionResponse | None:
    record = _load_direction_selection_record(db, assessment_id)
    if record is None:
        return None
    return _build_direction_selection_response(record)


def _normalize_direction_expansion(
    expansion: DirectionExpansionResult,
) -> DirectionExpansionResult:
    from app.schemas.direction import DirectionExpansionByElement

    seen_ids: set[str] = set()
    normalized_elements: list[DirectionExpansionByElement] = []
    for element in expansion.elements:
        suggestions = []
        for suggestion in element.suggestions:
            if suggestion.direction_id in seen_ids:
                continue
            seen_ids.add(suggestion.direction_id)
            suggestions.append(suggestion)
        normalized_elements.append(
            DirectionExpansionByElement(
                element_key=element.element_key,
                element_title=element.element_title,
                suggestions=suggestions,
            )
        )

    normalized = DirectionExpansionResult(
        generation_mode=expansion.generation_mode,
        llm_status=expansion.llm_status,
        elements=normalized_elements,
        total_suggestions=sum(
            len(element.suggestions) for element in normalized_elements
        ),
    )
    return normalized


def _load_direction_expansion_result(
    db: Session,
    assessment_id: str,
) -> DirectionExpansionResult | None:
    record = _load_direction_expansion(db, assessment_id)
    if record is None or not record.expansion_json:
        return None
    try:
        raw = json.loads(record.expansion_json)
        expansion = _normalize_direction_expansion(
            DirectionExpansionResult.model_validate(raw)
        )
        expansion.created_at = record.created_at
        expansion.updated_at = record.updated_at
        return expansion
    except Exception:
        return None


def _resolve_selected_directions_for_assessment(
    db: Session,
    assessment_id: str,
    direction_ids: list[str],
) -> tuple[list, list[str]]:
    """优先按当前 assessment 已保存的方向扩展结果解析选择，兼容增强后的自定义方向 ID。"""
    from app.schemas.direction import DirectionSuggestion

    expansion = _load_direction_expansion_result(db, assessment_id)
    if expansion is not None:
        suggestion_map = {
            suggestion.direction_id: suggestion
            for element in expansion.elements
            for suggestion in element.suggestions
        }
        selected = [
            suggestion_map[direction_id]
            for direction_id in direction_ids
            if direction_id in suggestion_map
        ]
        categories = list(
            dict.fromkeys(
                category
                for direction in selected
                for category in direction.related_scenario_categories
            )
        )
        return selected, categories

    service = DirectionExpansionService()
    return service.resolve_selected_directions(direction_ids)


def _load_direction_categories(
    db: Session,
    assessment_id: str,
) -> list[str] | None:
    from app.schemas.direction import DirectionSuggestion

    record = _load_direction_selection_record(db, assessment_id)
    if record is None:
        return None

    raw_directions = _parse_json_raw(
        record.directions_json,
        "Failed to parse direction selection for categories.",
    )
    categories = list(
        dict.fromkeys(
            category
            for item in raw_directions
            for category in (item.get("related_scenario_categories", []) if isinstance(item, dict) else getattr(item, "related_scenario_categories", []))
        )
    )
    return categories if categories else None


def _load_direction_labels(
    db: Session,
    assessment_id: str,
) -> list[str] | None:
    record = _load_direction_selection_record(db, assessment_id)
    if record is None:
        return None

    raw_directions = _parse_json_raw(
        record.directions_json,
        "Failed to parse direction selection for labels.",
    )
    labels = [
        item.get("title", "") if isinstance(item, dict) else getattr(item, "title", "")
        for item in raw_directions
    ]
    labels = [l for l in labels if l]
    return labels if labels else None


def _load_selected_directions(
    db: Session,
    assessment_id: str,
) -> list[DirectionSuggestion] | None:
    from app.schemas.direction import DirectionSuggestion

    record = _load_direction_selection_record(db, assessment_id)
    if record is None:
        return None

    raw_directions = _parse_json_raw(
        record.directions_json,
        "Failed to parse direction selection for report export.",
    )
    selected_directions: list[DirectionSuggestion] = []
    for item in raw_directions:
        if isinstance(item, DirectionSuggestion):
            selected_directions.append(item)
            continue
        if isinstance(item, dict):
            try:
                selected_directions.append(DirectionSuggestion.model_validate(item))
            except Exception:
                continue
    return selected_directions if selected_directions else None


def _upsert_direction_selection(
    db: Session,
    assessment_id: str,
    direction_ids: list[str],
    selected_directions,
) -> DirectionSelection:
    from app.schemas.direction import DirectionSuggestion

    record = _load_direction_selection_record(db, assessment_id)
    if record is None:
        record = DirectionSelection(
            assessment_id=assessment_id,
            generation_mode="rule_based",
            direction_ids_json="[]",
            directions_json="[]",
        )

    record.generation_mode = "rule_based"
    record.direction_ids_json = json.dumps(direction_ids, ensure_ascii=False)
    record.directions_json = json.dumps(
        [d.model_dump() if isinstance(d, DirectionSuggestion) else d for d in selected_directions],
        ensure_ascii=False,
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    _clear_scenarios_and_below(db, assessment_id)

    return record


def _build_direction_selection_response(
    record: DirectionSelection,
) -> DirectionSelectionResponse:
    from app.schemas.direction import DirectionSuggestion

    raw_directions = _parse_json_raw(
        record.directions_json,
        "Failed to parse direction selection.",
    )
    selected = [DirectionSuggestion.model_validate(item) for item in raw_directions]

    return DirectionSelectionResponse(
        assessment_id=record.assessment_id,
        generation_mode=record.generation_mode,
        selected_directions=selected,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _load_selected_directions(
    db: Session,
    assessment_id: str,
) -> list:
    from app.schemas.direction import DirectionSuggestion

    record = _load_direction_selection_record(db, assessment_id)
    if record is None:
        return []

    raw_directions = _parse_json_raw(
        record.directions_json,
        "Failed to parse direction selection.",
    )
    return [DirectionSuggestion.model_validate(item) for item in raw_directions]


def _inject_llm_directions_into_expansion(
    expansion,
    llm_directions,
):
    from app.schemas.direction import (
        DirectionExpansionByElement,
        DirectionExpansionResult,
    )

    llm_by_key: dict[str, list] = {}
    for d in llm_directions:
        llm_by_key.setdefault(d.element_key, []).append(d)

    elements: list[DirectionExpansionByElement] = []
    for elem in expansion.elements:
        llm_suggestions = llm_by_key.get(elem.element_key, [])
        if llm_suggestions:
            elements.append(
                DirectionExpansionByElement(
                    element_key=elem.element_key,
                    element_title=elem.element_title,
                    suggestions=llm_suggestions,
                )
            )
        else:
            elements.append(elem)

    total = sum(len(e.suggestions) for e in elements)
    return _normalize_direction_expansion(DirectionExpansionResult(
        generation_mode="llm" if llm_directions else expansion.generation_mode,
        elements=elements,
        total_suggestions=total,
    ))


def _upsert_direction_expansion(
    db: Session,
    assessment_id: str,
    expansion: DirectionExpansionResult,
) -> DirectionExpansion:
    normalized_expansion = _normalize_direction_expansion(expansion)
    record = db.scalar(
        select(DirectionExpansion).where(DirectionExpansion.assessment_id == assessment_id)
    )
    if record is None:
        record = DirectionExpansion(
            assessment_id=assessment_id,
            generation_mode=normalized_expansion.generation_mode,
            llm_status="pending",
            expansion_json=normalized_expansion.model_dump_json(),
        )
        db.add(record)
    else:
        record.generation_mode = normalized_expansion.generation_mode
        record.llm_status = "pending"
        record.expansion_json = normalized_expansion.model_dump_json()
    db.flush()
    db.refresh(record)
    return record


def _load_direction_expansion(
    db: Session,
    assessment_id: str,
) -> DirectionExpansion | None:
    return db.scalar(
        select(DirectionExpansion).where(DirectionExpansion.assessment_id == assessment_id)
    )


def _background_enhance_directions(
    assessment_id: str,
    canvas_json: str,
    breakthrough_keys: list[str],
) -> None:
    """Run LLM enhancement in a daemon thread with its own DB session."""
    from app.schemas.assessment import CanvasDiagnosisResult

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        canvas = CanvasDiagnosisResult.model_validate_json(canvas_json)
        enhancer = LLMEnhancer()
        llm_directions = enhancer.enhance_directions(canvas, breakthrough_keys)

        record = db.scalar(
            select(DirectionExpansion).where(DirectionExpansion.assessment_id == assessment_id)
        )
        if record is None:
            logger.warning("DirectionExpansion record vanished before background task completed")
            return

        if llm_directions:
            stored_expansion = DirectionExpansionResult.model_validate_json(record.expansion_json)
            merged = _inject_llm_directions_into_expansion(stored_expansion, llm_directions)
            record.generation_mode = merged.generation_mode
            record.llm_status = "completed"
            record.expansion_json = merged.model_dump_json()
        else:
            record.llm_status = "failed"

        record.updated_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "Background LLM enhancement %s for assessment %s",
            "completed" if llm_directions else "failed (no result)",
            assessment_id,
        )
    except Exception:
        logger.warning(
            "Background LLM enhancement failed for %s", assessment_id, exc_info=True
        )
        try:
            record = db.scalar(
                select(DirectionExpansion).where(DirectionExpansion.assessment_id == assessment_id)
            )
            if record is not None:
                record.llm_status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _load_competitiveness_analysis(
    db: Session,
    assessment_id: str,
) -> CompetitivenessAnalysis | None:
    return db.scalar(
        select(CompetitivenessAnalysis).where(
            CompetitivenessAnalysis.assessment_id == assessment_id
        )
    )


def _upsert_competitiveness_analysis(
    db: Session,
    assessment_id: str,
    result: CompetitivenessResult,
) -> CompetitivenessAnalysis:
    record = _load_competitiveness_analysis(db, assessment_id)
    if record is None:
        record = CompetitivenessAnalysis(
            assessment_id=assessment_id,
            generation_mode="rule_based",
            vp_json="{}",
            connections_json="[]",
            advantages_json="[]",
            strategy_json="{}",
        )

    record.generation_mode = result.generation_mode
    record.vp_json = json.dumps(result.vp_reconstruction.model_dump(), ensure_ascii=False)
    record.connections_json = json.dumps(
        [c.model_dump() for c in result.connections], ensure_ascii=False
    )
    record.advantages_json = json.dumps(
        [a.model_dump() for a in result.advantages], ensure_ascii=False
    )
    record.strategy_json = json.dumps(result.delivery_strategy.model_dump(), ensure_ascii=False)
    record.overall_narrative = result.overall_narrative

    db.add(record)
    db.commit()
    db.refresh(record)
    _clear_endgame_and_below(db, assessment_id)

    return record


def _build_competitiveness_result_from_record(
    record: CompetitivenessAnalysis,
) -> CompetitivenessResult:
    """Rehydrate a persisted competitiveness analysis into the API schema."""
    from app.schemas.competitiveness import (
        VPReconstruction,
        PointToLineConnection,
        CoreAdvantage,
        DeliveryStrategy,
    )

    vp_raw = _parse_json_raw(record.vp_json, "Failed to parse VP reconstruction.")
    connections_raw = _parse_json_raw(record.connections_json, "Failed to parse connections.")
    advantages_raw = _parse_json_raw(record.advantages_json, "Failed to parse advantages.")
    strategy_raw = _parse_json_raw(record.strategy_json, "Failed to parse delivery strategy.")
    normalized_connections = [_normalize_connection_summary(item) for item in connections_raw]

    return CompetitivenessResult(
        generation_mode=record.generation_mode,
        vp_reconstruction=VPReconstruction.model_validate(vp_raw),
        connections=[PointToLineConnection.model_validate(item) for item in normalized_connections],
        advantages=[CoreAdvantage.model_validate(item) for item in advantages_raw],
        delivery_strategy=DeliveryStrategy.model_validate(strategy_raw),
        overall_narrative=record.overall_narrative or "",
    )


def _normalize_connection_summary(item: dict) -> dict:
    """兼容历史线路结构，但不覆盖现有手工编辑内容。"""
    normalized = dict(item)
    line_name = str(normalized.get("line_name", "")).strip()
    competitive_impact = str(normalized.get("competitive_impact", "")).strip()
    if not str(normalized.get("strategic_narrative", "")).strip():
        normalized["strategic_narrative"] = build_line_summary(
            line_name,
            competitive_impact,
        )
    normalized.setdefault("competitive_moat", "")
    normalized.setdefault("linkage_logic", "")
    return normalized


def _load_endgame_analysis(
    db: Session,
    assessment_id: str,
) -> EndgameAnalysis | None:
    return db.scalar(
        select(EndgameAnalysis).where(
            EndgameAnalysis.assessment_id == assessment_id
        )
    )


def _upsert_endgame_analysis(
    db: Session,
    assessment_id: str,
    result: EndgameResult,
) -> EndgameAnalysis:
    record = _load_endgame_analysis(db, assessment_id)
    if record is None:
        record = EndgameAnalysis(
            assessment_id=assessment_id,
            generation_mode="rule_based",
            private_domain_json="{}",
            ecosystem_json="{}",
            opc_json="{}",
            three_stage_strategy_json="{}",
            strategic_paths_json="[]",
        )

    record.generation_mode = result.generation_mode
    record.private_domain_json = json.dumps(result.private_domain.model_dump(), ensure_ascii=False)
    record.ecosystem_json = json.dumps(result.ecosystem.model_dump(), ensure_ascii=False)
    record.opc_json = json.dumps(result.opc.model_dump(), ensure_ascii=False)
    record.three_stage_strategy_json = json.dumps(
        result.three_stage_strategy.model_dump(), ensure_ascii=False
    )
    record.strategic_paths_json = json.dumps(
        [p.model_dump() for p in result.strategic_paths], ensure_ascii=False
    )
    record.industry_essence = result.industry_essence
    record.overall_narrative = result.overall_narrative

    db.add(record)
    db.commit()
    db.refresh(record)
    _clear_reports_only(db, assessment_id)

    return record


def _derive_industry_essence(industry: str | None) -> str:
    analyzer = EndgameAnalyzer()
    industry_type = analyzer._detect_industry(industry or "")
    return analyzer._build_industry_essence(industry_type)


def _build_endgame_result_from_record(
    record: EndgameAnalysis,
    industry: str | None = None,
) -> EndgameResult:
    from app.schemas.endgame import (
        PrivateDomainDesign,
        EcosystemDesign,
        OPCDesign,
        StrategicPath,
        ThreeStageStrategy,
    )

    pd_raw = _parse_json_raw(record.private_domain_json, "Failed to parse private domain.")
    eco_raw = _parse_json_raw(record.ecosystem_json, "Failed to parse ecosystem.")
    opc_raw = _parse_json_raw(record.opc_json, "Failed to parse OPC.")
    three_stage_raw = _parse_json_raw(
        getattr(record, "three_stage_strategy_json", "{}"),
        "Failed to parse three-stage strategy.",
    )
    paths_raw = _parse_json_raw(record.strategic_paths_json, "Failed to parse strategic paths.")

    return EndgameResult(
        generation_mode=record.generation_mode,
        industry_essence=record.industry_essence or _derive_industry_essence(industry),
        private_domain=PrivateDomainDesign.model_validate(pd_raw),
        ecosystem=EcosystemDesign.model_validate(eco_raw),
        opc=OPCDesign.model_validate(opc_raw),
        three_stage_strategy=ThreeStageStrategy.model_validate(three_stage_raw),
        strategic_paths=[
            StrategicPath.model_validate(_normalize_endgame_strategic_path(item))
            for item in paths_raw
        ],
        overall_narrative=record.overall_narrative or "",
    )


def _normalize_endgame_strategic_path(item: dict) -> dict:
    """兼容历史终局路径结构，统一还原为当前定性字段。"""
    normalized = dict(item)
    if "execution_rhythm" not in normalized and "timeline" in normalized:
        normalized["execution_rhythm"] = normalized["timeline"]
    if "capability_requirements" not in normalized and "required_investments" in normalized:
        normalized["capability_requirements"] = normalized["required_investments"]
    return normalized


def _require_scenarios(
    db: Session,
    assessment_id: str,
) -> ScenarioRecommendationResult:
    scenarios = _load_scenario_recommendation(db, assessment_id)
    if scenarios is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scenario recommendation has not been generated for this assessment.",
        )
    return scenarios


def _require_report_prerequisites(
    db: Session,
    assessment: Assessment,
) -> tuple[
    CompanyProfileResult,
    CanvasDiagnosisResult,
    ScenarioRecommendationResult,
]:
    profile = _load_profile_from_assessment(assessment)
    canvas = _load_canvas_diagnosis(db, assessment.id)
    scenarios = _load_scenario_recommendation(db, assessment.id)
    direction_selection = _load_direction_selection(db, assessment.id)
    competitiveness = _load_competitiveness_analysis(db, assessment.id)
    endgame = _load_endgame_analysis(db, assessment.id)

    missing_steps: list[str] = []
    if profile is None:
        missing_steps.append("company profile")
    if canvas is None:
        missing_steps.append("canvas diagnosis")
    if direction_selection is None or not direction_selection.selected_directions:
        missing_steps.append("direction selection")
    if scenarios is None:
        missing_steps.append("scenario recommendation")
    if competitiveness is None:
        missing_steps.append("competitiveness analysis")
    if endgame is None:
        missing_steps.append("endgame design")

    if missing_steps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Report generation requires completed steps before continuing: "
                + ", ".join(missing_steps)
                + ". Generate them from the assessment workbench first."
            ),
        )

    return profile, canvas, scenarios


def _ensure_profile(
    db: Session,
    assessment: Assessment,
) -> tuple[CompanyProfileResult, str]:
    existing_profile = _load_profile_from_assessment(assessment)
    if existing_profile is not None:
        return existing_profile, assessment.profile_generation_mode or "mock"
    return _generate_and_store_profile(db, assessment)


def _generate_and_store_profile(
    db: Session,
    assessment: Assessment,
) -> tuple[CompanyProfileResult, str]:
    llm_client = LLMClient()
    profile, generation_mode = llm_client.generate_company_profile(assessment)

    assessment.profile_payload = json.dumps(profile.model_dump(), ensure_ascii=False)
    assessment.profile_generation_mode = generation_mode
    assessment.profile_generated_at = datetime.now(timezone.utc)

    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    _clear_canvas_and_below(db, assessment.id)

    return profile, generation_mode


def _calculate_canvas_metadata(
    canvas_result: BusinessModelCanvasResult,
) -> tuple[int, list[str], list[str]]:
    block_scores: list[tuple[str, int, str, str]] = []
    for block in canvas_result.blocks:
        score = 10
        completeness_issues = 0
        for content in (
            block.current_state,
            block.diagnosis,
            block.ai_opportunity,
            block.missing_information,
        ):
            if "待补充" in content:
                score -= 2
                completeness_issues += 1
            if "缺失" in content or "不完整" in content or "不足" in content:
                score -= 1
        block_scores.append(
            (block.title, max(3, score), block.ai_opportunity, block.diagnosis)
        )

    if not block_scores:
        return 0, [], []

    total_score = sum(item[1] for item in block_scores)
    # Demo mode: score based on 9-block completeness (0-100)
    overall_score = max(0, min(100, round(total_score / (len(block_scores) * 10) * 100)))
    weakest = sorted(block_scores, key=lambda item: item[1])[:3]
    weakest_blocks = [item[0] for item in weakest]

    # Build concise, actionable recommended_focus (one sentence per element)
    recommended_focus: list[str] = []
    for title, _, _, diagnosis in weakest:
        # Extract the core diagnostic insight and make it actionable
        short_diag = diagnosis.split("。")[0] if "。" in diagnosis else diagnosis
        abbr = _block_title_to_abbr(title)
        recommended_focus.append(f"{title}（{abbr}）：{short_diag}。—— 建议优先完善该模块数据基础并启动 AI 试点。")

    return overall_score, weakest_blocks, recommended_focus


def _block_title_to_abbr(title: str) -> str:
    abbr_map = {
        "关键合作伙伴": "KP",
        "关键业务活动": "KA",
        "关键资源": "KR",
        "价值主张": "VP",
        "客户关系": "CR",
        "渠道通路": "CH",
        "客户细分": "CS",
        "成本结构": "C$",
        "收入来源": "R$",
    }
    return abbr_map.get(title, title[:2])


def _upsert_canvas_diagnosis(
    db: Session,
    assessment_id: str,
    canvas_result: BusinessModelCanvasResult,
    generation_mode: str,
) -> CanvasDiagnosisResult:
    overall_score, weakest_blocks, recommended_focus = _calculate_canvas_metadata(
        canvas_result
    )
    record = db.scalar(
        select(CanvasDiagnosis).where(CanvasDiagnosis.assessment_id == assessment_id)
    )
    if record is None:
        record = CanvasDiagnosis(
            assessment_id=assessment_id,
            generation_mode=generation_mode,
            canvas_json="",
            overall_score=overall_score,
            weakest_blocks="[]",
            recommended_focus="[]",
        )

    record.generation_mode = generation_mode
    record.canvas_json = json.dumps(canvas_result.model_dump(), ensure_ascii=False)
    record.overall_score = overall_score
    record.weakest_blocks = json.dumps(weakest_blocks, ensure_ascii=False)
    record.recommended_focus = json.dumps(recommended_focus, ensure_ascii=False)

    db.add(record)
    db.commit()
    db.refresh(record)
    _clear_breakthrough_and_below(db, assessment_id)

    return CanvasDiagnosisResult(
        generation_mode=record.generation_mode,  # type: ignore[arg-type]
        overall_score=record.overall_score,
        weakest_blocks=weakest_blocks,
        recommended_focus=recommended_focus,
        canvas=canvas_result,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _upsert_scenario_recommendation(
    db: Session,
    assessment_id: str,
    evaluated_count: int,
    top_scenarios: list[ScenarioRecommendationItem],
    scoring_method: Literal["rule_based_v1", "four_quadrant_v1"] = "rule_based_v1",
    all_scores: list[ScenarioRecommendationItem] | None = None,
) -> ScenarioRecommendationResult:
    record = db.scalar(
        select(ScenarioRecommendation).where(
            ScenarioRecommendation.assessment_id == assessment_id
        )
    )
    if record is None:
        record = ScenarioRecommendation(
            assessment_id=assessment_id,
            scoring_method=scoring_method,
            evaluated_count=evaluated_count,
            scenario_json="[]",
            top_scenarios="[]",
        )

    record.scoring_method = scoring_method
    record.evaluated_count = evaluated_count
    record.scenario_json = json.dumps(
        [item.model_dump() for item in top_scenarios],
        ensure_ascii=False,
    )
    record.top_scenarios = json.dumps(
        [item.name for item in top_scenarios],
        ensure_ascii=False,
    )
    if all_scores is not None:
        record.all_scores_json = json.dumps(
            [item.model_dump() for item in all_scores],
            ensure_ascii=False,
        )
        record.active_scenario_ids_json = json.dumps(
            [item.scenario_id for item in all_scores],
            ensure_ascii=False,
        )
    else:
        record.all_scores_json = None
        record.active_scenario_ids_json = json.dumps(
            [item.scenario_id for item in top_scenarios],
            ensure_ascii=False,
        )

    db.add(record)
    db.commit()
    db.refresh(record)
    _clear_reports_only(db, assessment_id)

    return _build_scenario_recommendation_result_from_record(record)


def _match_and_store_cases(
    db: Session,
    assessment: Assessment,
    profile: CompanyProfileResult,
    canvas: CanvasDiagnosisResult,
    scenarios: ScenarioRecommendationResult,
) -> CaseRecommendationResult:
    matcher = CaseMatcher()
    top_cases, evaluated_count = matcher.match(
        assessment=assessment,
        profile=profile,
        canvas_diagnosis=canvas,
        scenario_recommendation=scenarios,
    )
    return _upsert_case_recommendation(
        db=db,
        assessment_id=assessment.id,
        evaluated_count=evaluated_count,
        top_cases=top_cases,
    )


def _upsert_case_recommendation(
    db: Session,
    assessment_id: str,
    evaluated_count: int,
    top_cases: list[CaseMatchItem],
) -> CaseRecommendationResult:
    record = db.scalar(
        select(CaseRecommendation).where(CaseRecommendation.assessment_id == assessment_id)
    )
    if record is None:
        record = CaseRecommendation(
            assessment_id=assessment_id,
            scoring_method="layered_v1",
            evaluated_count=evaluated_count,
            case_json="[]",
            top_cases="[]",
        )

    record.scoring_method = "layered_v1"
    record.evaluated_count = evaluated_count
    record.case_json = json.dumps(
        [item.model_dump() for item in top_cases],
        ensure_ascii=False,
    )
    record.top_cases = json.dumps([item.title for item in top_cases], ensure_ascii=False)

    db.add(record)
    db.commit()
    db.refresh(record)
    _clear_reports_only(db, assessment_id)

    return CaseRecommendationResult(
        scoring_method="layered_v1",
        evaluated_count=evaluated_count,
        top_cases=top_cases,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _build_progress(
    profile: CompanyProfileResult | None,
    canvas: CanvasDiagnosisResult | None,
    breakthrough_keys: list[str] | None,
    scenarios: ScenarioRecommendationResult | None,
    cases: CaseRecommendationResult | None,
    report_summary,
    direction_selection: object | None = None,
    competitiveness: object | None = None,
    endgame: object | None = None,
) -> AssessmentProgress:
    has_profile = profile is not None
    has_canvas = canvas is not None
    has_breakthrough = breakthrough_keys is not None and len(breakthrough_keys) >= 2
    has_directions = False
    if direction_selection is not None:
        has_directions = bool(
            getattr(direction_selection, "selected_directions", None)
            or getattr(direction_selection, "directions_json", None)
        )
    has_competitiveness = competitiveness is not None
    has_endgame = endgame is not None
    has_scenarios = scenarios is not None
    has_cases = cases is not None
    has_report = report_summary is not None
    return AssessmentProgress(
        has_profile=has_profile,
        has_canvas=has_canvas,
        has_breakthrough=has_breakthrough,
        has_directions=has_directions,
        has_competitiveness=has_competitiveness,
        has_endgame=has_endgame,
        has_scenarios=has_scenarios,
        has_cases=has_cases,
        has_report=has_report,
        ready_for_report=(
            has_profile
            and has_canvas
            and has_breakthrough
            and has_directions
            and has_scenarios
            and has_competitiveness
            and has_endgame
        ),
    )


def _clear_canvas_and_below(db: Session, assessment_id: str) -> None:
    _delete_records(
        db,
        [
            db.scalar(select(CanvasDiagnosis).where(CanvasDiagnosis.assessment_id == assessment_id)),
            db.scalar(select(BreakthroughSelection).where(BreakthroughSelection.assessment_id == assessment_id)),
            db.scalar(select(DirectionExpansion).where(DirectionExpansion.assessment_id == assessment_id)),
            db.scalar(select(DirectionSelection).where(DirectionSelection.assessment_id == assessment_id)),
            db.scalar(select(CompetitivenessAnalysis).where(CompetitivenessAnalysis.assessment_id == assessment_id)),
            db.scalar(select(EndgameAnalysis).where(EndgameAnalysis.assessment_id == assessment_id)),
            db.scalar(
                select(ScenarioRecommendation).where(
                    ScenarioRecommendation.assessment_id == assessment_id
                )
            ),
            db.scalar(select(CaseRecommendation).where(CaseRecommendation.assessment_id == assessment_id)),
            db.scalar(select(GeneratedReport).where(GeneratedReport.assessment_id == assessment_id)),
        ],
    )


def _clear_scenarios_and_below(db: Session, assessment_id: str) -> None:
    """Clear scenarios and all downstream outputs after direction changes."""
    _delete_records(
        db,
        [
            db.scalar(
                select(ScenarioRecommendation).where(
                    ScenarioRecommendation.assessment_id == assessment_id
                )
            ),
            db.scalar(select(CompetitivenessAnalysis).where(CompetitivenessAnalysis.assessment_id == assessment_id)),
            db.scalar(select(EndgameAnalysis).where(EndgameAnalysis.assessment_id == assessment_id)),
            db.scalar(select(CaseRecommendation).where(CaseRecommendation.assessment_id == assessment_id)),
            db.scalar(select(GeneratedReport).where(GeneratedReport.assessment_id == assessment_id)),
        ],
    )


def _clear_direction_selection_and_below(db: Session, assessment_id: str) -> None:
    _delete_records(
        db,
        [
            db.scalar(
                select(DirectionSelection).where(
                    DirectionSelection.assessment_id == assessment_id
                )
            ),
            db.scalar(
                select(ScenarioRecommendation).where(
                    ScenarioRecommendation.assessment_id == assessment_id
                )
            ),
            db.scalar(
                select(CompetitivenessAnalysis).where(
                    CompetitivenessAnalysis.assessment_id == assessment_id
                )
            ),
            db.scalar(
                select(EndgameAnalysis).where(
                    EndgameAnalysis.assessment_id == assessment_id
                )
            ),
            db.scalar(
                select(CaseRecommendation).where(
                    CaseRecommendation.assessment_id == assessment_id
                )
            ),
            db.scalar(
                select(GeneratedReport).where(
                    GeneratedReport.assessment_id == assessment_id
                )
            ),
        ],
    )


def _clear_competitiveness_outputs(db: Session, assessment_id: str) -> None:
    """Clear competitiveness, endgame, case and report outputs after scenario edits."""
    _delete_records(
        db,
        [
            db.scalar(
                select(CompetitivenessAnalysis).where(
                    CompetitivenessAnalysis.assessment_id == assessment_id
                )
            ),
            db.scalar(select(EndgameAnalysis).where(EndgameAnalysis.assessment_id == assessment_id)),
            db.scalar(select(CaseRecommendation).where(CaseRecommendation.assessment_id == assessment_id)),
            db.scalar(select(GeneratedReport).where(GeneratedReport.assessment_id == assessment_id)),
        ],
    )


def _clear_endgame_and_below(db: Session, assessment_id: str) -> None:
    """Clear endgame and report outputs after competitiveness changes."""
    _delete_records(
        db,
        [
            db.scalar(select(EndgameAnalysis).where(EndgameAnalysis.assessment_id == assessment_id)),
            db.scalar(select(GeneratedReport).where(GeneratedReport.assessment_id == assessment_id)),
        ],
    )


def _clear_directions_and_below(db: Session, assessment_id: str) -> None:
    """Clear direction expansion, direction selection, and everything downstream.

    Used after breakthrough re-selection, which invalidates all direction-related
    data plus competitiveness, endgame, scenarios, cases, and reports.
    """
    _delete_records(
        db,
        [
            db.scalar(select(DirectionExpansion).where(DirectionExpansion.assessment_id == assessment_id)),
            db.scalar(select(DirectionSelection).where(DirectionSelection.assessment_id == assessment_id)),
            db.scalar(select(CompetitivenessAnalysis).where(CompetitivenessAnalysis.assessment_id == assessment_id)),
            db.scalar(select(EndgameAnalysis).where(EndgameAnalysis.assessment_id == assessment_id)),
            db.scalar(
                select(ScenarioRecommendation).where(
                    ScenarioRecommendation.assessment_id == assessment_id
                )
            ),
            db.scalar(select(CaseRecommendation).where(CaseRecommendation.assessment_id == assessment_id)),
            db.scalar(select(GeneratedReport).where(GeneratedReport.assessment_id == assessment_id)),
        ],
    )


def _clear_breakthrough_and_below(db: Session, assessment_id: str) -> None:
    _delete_records(
        db,
        [
            db.scalar(select(BreakthroughSelection).where(BreakthroughSelection.assessment_id == assessment_id)),
            db.scalar(select(DirectionExpansion).where(DirectionExpansion.assessment_id == assessment_id)),
            db.scalar(select(DirectionSelection).where(DirectionSelection.assessment_id == assessment_id)),
            db.scalar(select(CompetitivenessAnalysis).where(CompetitivenessAnalysis.assessment_id == assessment_id)),
            db.scalar(select(EndgameAnalysis).where(EndgameAnalysis.assessment_id == assessment_id)),
            db.scalar(
                select(ScenarioRecommendation).where(
                    ScenarioRecommendation.assessment_id == assessment_id
                )
            ),
            db.scalar(select(CaseRecommendation).where(CaseRecommendation.assessment_id == assessment_id)),
            db.scalar(select(GeneratedReport).where(GeneratedReport.assessment_id == assessment_id)),
        ],
    )


def _clear_cases_and_reports(db: Session, assessment_id: str) -> None:
    _delete_records(
        db,
        [
            db.scalar(select(CaseRecommendation).where(CaseRecommendation.assessment_id == assessment_id)),
            db.scalar(select(GeneratedReport).where(GeneratedReport.assessment_id == assessment_id)),
        ],
    )


def _clear_reports_only(db: Session, assessment_id: str) -> None:
    _delete_records(
        db,
        [db.scalar(select(GeneratedReport).where(GeneratedReport.assessment_id == assessment_id))],
    )


def _delete_records(db: Session, records: list[object | None]) -> None:
    changed = False
    for record in records:
        if record is not None:
            db.delete(record)
            changed = True

    if changed:
        db.commit()

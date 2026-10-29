"""BMC 三维突破要素评分 — API 端点"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.assessments import _require_paid_workflow_access, _clear_directions_and_below
from app.db.session import get_db
from app.models.assessment import Assessment
from app.models.bmc_scoring import BMCScoring
from app.models.breakthrough_selection import BreakthroughSelection
from app.models.user import User
from app.schemas.assessment import CanvasDiagnosisResult, BusinessModelCanvasResult
from app.schemas.bmc_scoring import (
    AutoDeriveResponse,
    BMCScoringRequest,
    BMCScoringResponse,
    BMCScoringResult,
    BMCScoringSaveRequest,
    ModuleScoringResult,
)
from app.schemas.breakthrough import (
    BreakthroughElement,
    ELEMENT_KEY_TO_TITLE,
)
from app.services.bmc_scoring_service import BMCScoringService

router = APIRouter(prefix="/api/assessments", tags=["bmc-scoring"])


# ── 辅助函数 ──

def _get_assessment_or_404(db: Session, assessment_id: str) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return assessment


def _load_canvas_diagnosis(db: Session, assessment_id: str) -> CanvasDiagnosisResult | None:
    from app.models.canvas_diagnosis import CanvasDiagnosis

    record = db.scalar(
        select(CanvasDiagnosis).where(CanvasDiagnosis.assessment_id == assessment_id)
    )
    if record is None:
        return None

    import json as _json
    from pydantic import ValidationError

    try:
        canvas_raw = _json.loads(record.canvas_json)
        canvas = BusinessModelCanvasResult.model_validate(canvas_raw)
    except (_json.JSONDecodeError, ValidationError):
        return None

    return CanvasDiagnosisResult(
        generation_mode=record.generation_mode,
        overall_score=record.overall_score,
        weakest_blocks=_json.loads(record.weakest_blocks),
        recommended_focus=_json.loads(record.recommended_focus),
        canvas=canvas,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _load_bmc_scoring(db: Session, assessment_id: str) -> BMCScoring | None:
    return db.scalar(
        select(BMCScoring).where(BMCScoring.assessment_id == assessment_id)
    )


# ── 端点 ──


@router.post(
    "/{assessment_id}/bmc-scoring/calculate",
    response_model=BMCScoringResult,
    status_code=status.HTTP_200_OK,
)
def calculate_bmc_scoring(
    assessment_id: str,
    payload: BMCScoringRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BMCScoringResult:
    """计算三维评分，不持久化"""
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)

    service = BMCScoringService()
    return service.evaluate_all(payload.modules, assessment_id=assessment_id)


@router.post(
    "/{assessment_id}/bmc-scoring/auto-derive",
    response_model=AutoDeriveResponse,
    status_code=status.HTTP_200_OK,
)
def auto_derive_bmc_scores(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutoDeriveResponse:
    """从画布诊断自动推导三维初始分"""
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    canvas = _load_canvas_diagnosis(db, assessment_id)
    if canvas is None:
        raise HTTPException(400, detail="请先生成商业画布诊断。")

    service = BMCScoringService()
    modules = service.auto_derive_scores(canvas)
    return AutoDeriveResponse(modules=modules, derived_from_canvas=True)


@router.post(
    "/{assessment_id}/bmc-scoring/save",
    response_model=BMCScoringResponse,
    status_code=status.HTTP_200_OK,
)
def save_bmc_scoring(
    assessment_id: str,
    payload: BMCScoringSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BMCScoringResponse:
    """保存评分结果并同步 BreakthroughSelection"""
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)

    service = BMCScoringService()
    result = service.evaluate_all(payload.all_module_scores, assessment_id=assessment_id)
    available_keys = {item.key for item in result.module_results}
    if len(set(payload.selected_keys)) != len(payload.selected_keys) or any(
        key not in available_keys for key in payload.selected_keys
    ):
        raise HTTPException(422, detail="请选择本次评分中的有效且不重复的突破要素。")

    # 保存 BMCScoring 记录
    record = _load_bmc_scoring(db, assessment_id)
    if record is None:
        record = BMCScoring(
            assessment_id=assessment_id,
            module_scores_json="[]",
            scoring_result_json="{}",
            selected_keys_json="[]",
        )

    record.module_scores_json = json.dumps(
        [m.model_dump() for m in payload.all_module_scores], ensure_ascii=False
    )
    record.scoring_result_json = json.dumps(
        result.model_dump(), ensure_ascii=False
    )
    record.selected_keys_json = json.dumps(payload.selected_keys, ensure_ascii=False)
    record.updated_at = datetime.now(timezone.utc)

    db.add(record)

    # 同步 BreakthroughSelection
    _sync_breakthrough_selection(
        db=db,
        assessment_id=assessment_id,
        selected_keys=payload.selected_keys,
        all_results=result.module_results,
        selection_mode=payload.selection_mode,
    )

    # Re-selection invalidates every dependent output, including reports.
    _clear_directions_and_below(db, assessment_id)

    db.commit()
    db.refresh(record)

    return BMCScoringResponse(
        assessment_id=assessment_id,
        scoring_result=result,
        selected_keys=payload.selected_keys,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/{assessment_id}/bmc-scoring",
    response_model=BMCScoringResponse,
    status_code=status.HTTP_200_OK,
)
def get_bmc_scoring(
    assessment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BMCScoringResponse:
    """查询已保存的评分结果"""
    assessment = _get_assessment_or_404(db, assessment_id)
    _require_paid_workflow_access(db, assessment, current_user)
    record = _load_bmc_scoring(db, assessment_id)
    if record is None:
        raise HTTPException(404, detail="尚未保存 BMC 评分。")

    # 解析 scoring_result_json
    try:
        raw = json.loads(record.scoring_result_json)
        scoring_result = BMCScoringResult.model_validate(raw)
    except (json.JSONDecodeError, Exception):
        scoring_result = None

    selected_keys = json.loads(record.selected_keys_json)

    return BMCScoringResponse(
        assessment_id=assessment_id,
        scoring_result=scoring_result,
        selected_keys=selected_keys,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


# ── 内部同步逻辑 ──


def _sync_breakthrough_selection(
    db: Session,
    assessment_id: str,
    selected_keys: list[str],
    all_results: list[ModuleScoringResult],
    selection_mode: str,
) -> None:
    """将 BMC 评分结果同步到 BreakthroughSelection 表"""

    # 映射 ModuleScoringResult → BreakthroughElement
    recommended_elements = []
    # The existing selection reader resolves keys against this candidate snapshot.
    # Keep all scored modules, not only the automatic Top 3.
    for r in all_results:
        recommended_elements.append(
            BreakthroughElement(
                key=r.key,
                title=r.title,
                score=round(r.normalized_score),
                reason=f"痛点 {r.pain}/5 · 数据 {r.data}/5 · 可行度 {r.feasibility}/5 | {r.recommendation_label}",
                ai_opportunity="",  # 评分模块不直接提供 ai_opportunity
            )
        )

    # 加载或创建 BreakthroughSelection
    record = db.scalar(
        select(BreakthroughSelection).where(
            BreakthroughSelection.assessment_id == assessment_id
        )
    )
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
        selected_keys, ensure_ascii=False
    )

    db.add(record)

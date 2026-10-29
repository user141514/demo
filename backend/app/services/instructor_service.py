"""D3: Instructor Service — 讲师仪表盘 / 批量点评 / 成果导出"""
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.breakthrough_selection import BreakthroughSelection
from app.models.canvas_diagnosis import CanvasDiagnosis
from app.models.case_recommendation import CaseRecommendation
from app.models.competitiveness_analysis import CompetitivenessAnalysis
from app.models.direction_selection import DirectionSelection
from app.models.generated_report import GeneratedReport
from app.models.scenario_recommendation import ScenarioRecommendation
from app.models.user import User
from app.schemas.assessment import (
    BatchCommentRequest,
    BatchCommentResponse,
    InstructorDashboardResponse,
    InstructorExportResponse,
    StudentSummary,
)
from app.schemas.auth import CreateInstructorRequest, UserResponse
from app.services.auth_service import _hash_password, validate_instructor_password


class InstructorService:
    def get_dashboard(self, db: Session) -> InstructorDashboardResponse:
        assessments = db.query(Assessment).order_by(Assessment.created_at.desc()).all()

        # Batch-load all module records to avoid N+1 queries
        a_ids = [a.id for a in assessments]
        canvas_map = _one_per_assessment(db, CanvasDiagnosis, a_ids)
        breakthrough_map = _one_per_assessment(db, BreakthroughSelection, a_ids)
        direction_map = _one_per_assessment(db, DirectionSelection, a_ids)
        competitiveness_map = _one_per_assessment(db, CompetitivenessAnalysis, a_ids)
        scenario_map = _one_per_assessment(db, ScenarioRecommendation, a_ids)
        case_map = _one_per_assessment(db, CaseRecommendation, a_ids)
        report_map = _latest_report_per_assessment(db, a_ids)

        students: list[StudentSummary] = []
        group_counts: dict[str, int] = defaultdict(int)

        for a in assessments:
            report = report_map.get(a.id)
            canvas = canvas_map.get(a.id)
            has_profile = bool(a.profile_payload)
            has_canvas = canvas is not None
            has_breakthrough = breakthrough_map.get(a.id) is not None
            has_scenarios = scenario_map.get(a.id) is not None

            student = StudentSummary(
                assessment_id=a.id,
                company_name=a.company_name,
                industry=a.industry,
                company_size=a.company_size,
                class_group=a.class_group,
                instructor_comment=a.instructor_comment,
                has_profile=has_profile,
                has_canvas=has_canvas,
                has_breakthrough=has_breakthrough,
                has_directions=direction_map.get(a.id) is not None,
                has_competitiveness=competitiveness_map.get(a.id) is not None,
                has_scenarios=has_scenarios,
                has_cases=case_map.get(a.id) is not None,
                has_report=report is not None,
                ready_for_report=(
                    has_profile and has_canvas and has_breakthrough and has_scenarios
                ),
                canvas_score=canvas.overall_score if canvas else None,
                report_id=report.id if report else None,
                created_at=a.created_at.isoformat() if a.created_at else None,
                updated_at=a.updated_at.isoformat() if a.updated_at else None,
            )

            group = a.class_group or "未分组"
            group_counts[group] += 1
            students.append(student)

        groups = sorted(group_counts.keys())
        completed = sum(1 for s in students if s.has_report)
        pct = int(completed / max(len(students), 1) * 100)

        return InstructorDashboardResponse(
            total_students=len(students),
            groups=groups,
            students=students,
            summary_by_group=dict(group_counts),
            overall_completion_pct=pct,
        )

    def batch_comment(
        self,
        db: Session,
        request: BatchCommentRequest,
    ) -> BatchCommentResponse:
        assessments = (
            db.query(Assessment)
            .filter(Assessment.id.in_(request.assessment_ids))
            .all()
        )
        for a in assessments:
            a.instructor_comment = request.comment
            db.add(a)
        db.commit()

        return BatchCommentResponse(
            updated_count=len(assessments),
            comment=request.comment,
        )

    def export_csv(self, db: Session) -> InstructorExportResponse:
        assessments = db.query(Assessment).order_by(Assessment.created_at.desc()).all()
        a_ids = [a.id for a in assessments]
        canvas_map = _one_per_assessment(db, CanvasDiagnosis, a_ids)
        report_map = _latest_report_per_assessment(db, a_ids)

        rows = [
            ["assessment_id", "company_name", "industry", "company_size",
             "class_group", "instructor_comment", "has_profile", "has_canvas",
             "has_report", "canvas_score", "created_at"]
        ]
        for a in assessments:
            canvas = canvas_map.get(a.id)
            report = report_map.get(a.id)
            rows.append([
                a.id, a.company_name, a.industry, a.company_size,
                a.class_group or "", a.instructor_comment or "",
                "是" if a.profile_payload else "否",
                "是" if canvas else "否",
                "是" if report else "否",
                str(canvas.overall_score) if canvas else "",
                a.created_at.isoformat() if a.created_at else "",
            ])

        csv_content = "\n".join(",".join(str(c) for c in row) for row in rows)
        return InstructorExportResponse(
            export_format="csv",
            content=csv_content,
            student_count=len(assessments),
        )

    def create_instructor(self, db: Session, request: CreateInstructorRequest) -> UserResponse:
        existing = db.query(User).filter(User.email == request.email).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该邮箱已被注册。",
            )

        validate_instructor_password(request.password)
        user = User(
            email=request.email,
            hashed_password=_hash_password(request.password),
            display_name=request.display_name,
            role="instructor",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return UserResponse.model_validate(user, from_attributes=True)


# ── Batch-load helpers (avoid N+1 queries) ──────────────────────────

def _one_per_assessment(db: Session, model, a_ids: list[str]) -> dict:
    """Return {assessment_id: record} for the first record per assessment."""
    if not a_ids:
        return {}
    rows = (
        db.query(model)
        .filter(model.assessment_id.in_(a_ids))
        .all()
    )
    return {r.assessment_id: r for r in rows}


def _latest_report_per_assessment(db: Session, a_ids: list[str]) -> dict:
    """Return {assessment_id: latest GeneratedReport} per assessment."""
    if not a_ids:
        return {}
    rows = (
        db.query(GeneratedReport)
        .filter(GeneratedReport.assessment_id.in_(a_ids))
        .order_by(GeneratedReport.assessment_id, GeneratedReport.created_at.desc())
        .all()
    )
    # Keep first per assessment_id (already sorted desc)
    result: dict = {}
    for r in rows:
        if r.assessment_id not in result:
            result[r.assessment_id] = r
    return result

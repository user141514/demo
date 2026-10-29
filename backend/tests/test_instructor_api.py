"""Tests for instructor API — permission boundary + happy path."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import session as db_session
from app.main import create_app
from app.models.user import User  # noqa: F401

TEST_DB_PATH = Path(__file__).resolve().parent / "test_instructor_api.db"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "SessionLocal", testing_session_local)

    def _override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    db_session.Base.metadata.create_all(bind=engine)
    db_session._migrate_generated_reports_table()
    app.dependency_overrides[db_session.get_db] = _override_get_db
    with TestClient(app) as c:
        yield c

    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


# ── 权限边界 ──


def test_create_instructor_unauthenticated_returns_401(client: TestClient):
    resp = client.post("/api/instructor/create-instructor", json={
        "email": "new_teacher@test.com", "password": "123456"
    })
    assert resp.status_code == 401


def test_create_instructor_as_student_returns_403(client: TestClient):
    # 注册学生账号
    resp = client.post("/api/auth/register", json={
        "email": "student_for_test@example.com",
        "password": "test123456",
        "display_name": "Test Student",
        "company_name": "Test Company",
        "job_title": "Innovation Lead",
    })
    assert resp.status_code == 201
    student_token = resp.json()["access_token"]

    resp = client.post(
        "/api/instructor/create-instructor",
        json={"email": "should_fail@test.com", "password": "123456"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 403


def test_dashboard_as_student_returns_403(client: TestClient):
    # 注册学生账号
    resp = client.post("/api/auth/register", json={
        "email": "student_for_dash@example.com",
        "password": "test123456",
        "display_name": "Dash Student",
        "company_name": "Dash Company",
        "job_title": "Operations Lead",
    })
    assert resp.status_code == 201
    student_token = resp.json()["access_token"]

    resp = client.get(
        "/api/instructor/dashboard",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 403


def test_batch_comment_as_student_returns_403(client: TestClient):
    # 注册学生账号
    resp = client.post("/api/auth/register", json={
        "email": "student_for_batch@example.com",
        "password": "test123456",
        "display_name": "Batch Student",
        "company_name": "Batch Company",
        "job_title": "Project Lead",
    })
    assert resp.status_code == 201
    student_token = resp.json()["access_token"]

    resp = client.post(
        "/api/instructor/batch-comment",
        json={"assessment_ids": [], "comment": "test"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 403


def test_export_as_student_returns_403(client: TestClient):
    # 注册学生账号
    resp = client.post("/api/auth/register", json={
        "email": "student_for_export@example.com",
        "password": "test123456",
        "display_name": "Export Student",
        "company_name": "Export Company",
        "job_title": "Analyst",
    })
    assert resp.status_code == 201
    student_token = resp.json()["access_token"]

    resp = client.get(
        "/api/instructor/export?format=csv",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 403


# ── 正常路径 ──


def test_seed_teacher_can_create_instructor(client: TestClient):
    # 用种子账号登录
    resp = client.post("/api/auth/login", json={
        "email": "teacher", "password": "meitai123456"
    })
    assert resp.status_code == 200
    teacher_token = resp.json()["access_token"]

    resp = client.post(
        "/api/instructor/create-instructor",
        json={
            "email": "new_instructor_test_01@test.com",
            "password": "secure123",
            "display_name": "新管理员"
        },
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "instructor"
    assert data["display_name"] == "新管理员"


def test_create_instructor_duplicate_email(client: TestClient):
    resp = client.post("/api/auth/login", json={
        "email": "teacher", "password": "meitai123456"
    })
    assert resp.status_code == 200
    teacher_token = resp.json()["access_token"]

    # 第一次创建
    email = "duplicate_teacher@test.com"
    client.post(
        "/api/instructor/create-instructor",
        json={"email": email, "password": "123456"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    # 第二次应冲突
    resp = client.post(
        "/api/instructor/create-instructor",
        json={"email": email, "password": "123456"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 409


def test_create_instructor_weak_password(client: TestClient):
    resp = client.post("/api/auth/login", json={
        "email": "teacher", "password": "meitai123456"
    })
    assert resp.status_code == 200
    teacher_token = resp.json()["access_token"]

    resp = client.post(
        "/api/instructor/create-instructor",
        json={"email": "weakpw@test.com", "password": "12345"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 422


def test_dashboard_as_instructor_returns_200(client: TestClient):
    resp = client.post("/api/auth/login", json={
        "email": "teacher", "password": "meitai123456"
    })
    assert resp.status_code == 200
    teacher_token = resp.json()["access_token"]

    resp = client.get(
        "/api/instructor/dashboard",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_students" in data
    assert "students" in data


def test_batch_comment_as_instructor_returns_200(client: TestClient):
    # 先创建一个学生和测评，获得有效的 assessment_id
    resp = client.post("/api/auth/register", json={
        "email": "student_for_batch_positive@example.com",
        "password": "test123456",
        "display_name": "Positive Student",
        "company_name": "Positive Company",
        "job_title": "Growth Lead",
    })
    assert resp.status_code == 201
    student_token = resp.json()["access_token"]

    PAYLOAD = {
        "company_name": "测试科技有限公司",
        "industry": "科技",
        "company_size": "50-200人",
        "region": "华东",
        "annual_revenue_range": "1亿-10亿",
        "core_products": "测试产品",
        "target_customers": "企业客户",
        "current_challenges": "市场拓展",
        "ai_goals": "效率提升",
        "available_data": "销售数据",
        "notes": "测试",
    }
    resp = client.post(
        "/api/assessments",
        json=PAYLOAD,
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert resp.status_code == 201
    assessment_id = resp.json()["id"]

    # 用管理员账号批量评语
    resp = client.post("/api/auth/login", json={
        "email": "teacher", "password": "meitai123456"
    })
    assert resp.status_code == 200
    teacher_token = resp.json()["access_token"]

    resp = client.post(
        "/api/instructor/batch-comment",
        json={"assessment_ids": [assessment_id], "comment": "test comment"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 200


def test_export_as_instructor_returns_200(client: TestClient):
    resp = client.post("/api/auth/login", json={
        "email": "teacher", "password": "meitai123456"
    })
    assert resp.status_code == 200
    teacher_token = resp.json()["access_token"]

    resp = client.get(
        "/api/instructor/export?format=csv",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 200

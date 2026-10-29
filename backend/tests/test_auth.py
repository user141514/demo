from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db import session as db_session
from app.main import create_app
from app.models.user import User
from app.services.auth_service import _hash_password

TEST_DB_PATH = Path(__file__).resolve().parent / "test_auth.db"


def build_register_payload(
    email: str,
    password: str = "test123456",
    **overrides,
) -> dict[str, str]:
    payload = {
        "email": email,
        "password": password,
        "display_name": "测试用户",
        "company_name": "测试企业",
        "job_title": "创新负责人",
    }
    payload.update(overrides)
    return payload


def build_assessment_payload(company_name: str) -> dict[str, str]:
    return {
        "company_name": company_name,
        "industry": "零售",
        "company_size": "50-200人",
        "region": "华东",
        "annual_revenue_range": "1000万-5000万元",
        "core_products": "社区零售门店与会员运营",
        "target_customers": "社区家庭用户",
        "current_challenges": "门店效率波动，会员复购不稳定",
        "ai_goals": "提升门店运营效率和会员复购",
        "available_data": "POS、会员、客服数据",
        "notes": "测试数据",
    }


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
    db_session.Base.metadata.create_all(bind=engine)
    db_session._migrate_generated_reports_table()

    def _override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[db_session.get_db] = _override_get_db
    with TestClient(app) as test_client:
        with testing_session_local() as db:
            db.add(User(email="teacher", role="instructor", hashed_password=_hash_password("instructor-test-20261027")))
            db.commit()
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def test_teacher_login_returns_instructor_role(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "teacher", "password": "instructor-test-20261027"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "instructor"
    assert body["user"]["email"] == "teacher"


def test_teacher_login_wrong_password_fails(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "teacher", "password": "wrongpassword"},
    )

    assert response.status_code == 401


def test_student_register_and_login(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload(
            "student@test.com",
            display_name="测试学员",
        ),
    )
    assert register_response.status_code == 201, register_response.text
    register_body = register_response.json()
    assert register_body["user"]["role"] == "student"
    assert register_body["user"]["company_name"] == "测试企业"
    assert register_body["user"]["job_title"] == "创新负责人"

    login_response = client.post(
        "/api/auth/login",
        json={"email": "student@test.com", "password": "test123456"},
    )
    assert login_response.status_code == 200, login_response.text
    assert login_response.json()["user"]["email"] == "student@test.com"


def test_teacher_can_see_all_assessments(client: TestClient) -> None:
    register_a = client.post(
        "/api/auth/register",
        json=build_register_payload("a@test.com", display_name="学生A"),
    )
    assert register_a.status_code == 201, register_a.text
    token_a = register_a.json()["access_token"]

    register_b = client.post(
        "/api/auth/register",
        json=build_register_payload("b@test.com", display_name="学生B"),
    )
    assert register_b.status_code == 201, register_b.text
    token_b = register_b.json()["access_token"]

    response_a = client.post(
        "/api/assessments",
        json=build_assessment_payload("A公司"),
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response_a.status_code == 201, response_a.text

    response_b = client.post(
        "/api/assessments",
        json=build_assessment_payload("B公司"),
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response_b.status_code == 201, response_b.text

    teacher_login = client.post(
        "/api/auth/login",
        json={"email": "teacher", "password": "instructor-test-20261027"},
    )
    assert teacher_login.status_code == 200, teacher_login.text
    teacher_token = teacher_login.json()["access_token"]

    assessments_response = client.get(
        "/api/assessments",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert assessments_response.status_code == 200, assessments_response.text
    assert assessments_response.json()["total"] >= 2


def test_student_can_only_see_own_assessments(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload("onlyme@test.com", display_name="我自己"),
    )
    assert register_response.status_code == 201, register_response.text
    token = register_response.json()["access_token"]

    create_response = client.post(
        "/api/assessments",
        json=build_assessment_payload("我的公司"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201, create_response.text

    list_response = client.get(
        "/api/assessments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["total"] == 1


def test_login_returns_token_usable_for_me(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload("valid@test.com"),
    )
    assert register_response.status_code == 201, register_response.text

    login_response = client.post(
        "/api/auth/login",
        json={"email": "valid@test.com", "password": "test123456"},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == "valid@test.com"


def test_wrong_password_returns_uniform_401(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload("leak@test.com"),
    )
    assert register_response.status_code == 201, register_response.text

    existing_user = client.post(
        "/api/auth/login",
        json={"email": "leak@test.com", "password": "wrong"},
    )
    missing_user = client.post(
        "/api/auth/login",
        json={"email": "missing@test.com", "password": "test123456"},
    )

    assert existing_user.status_code == 401
    assert missing_user.status_code == 401
    assert existing_user.json()["detail"] == missing_user.json()["detail"]


def test_protected_routes_require_authentication(client: TestClient) -> None:
    me_response = client.get("/api/auth/me")
    assessments_response = client.get("/api/assessments")

    assert me_response.status_code == 401
    assert assessments_response.status_code == 401


def test_expired_token_returns_401(client: TestClient) -> None:
    with db_session.SessionLocal() as db:
        user = User(
            email="expired@test.com",
            hashed_password="not-used",
            role="student",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

    expired_token = jwt.encode(
        {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_register_requires_name_company_and_job_title(client: TestClient) -> None:
    for missing_field in ("display_name", "company_name", "job_title"):
        payload = build_register_payload("missing@test.com")
        payload.pop(missing_field)

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 422
        assert any(
            error["loc"][-1] == missing_field
            for error in response.json()["detail"]
        )


def test_register_rejects_blank_name_company_and_job_title(client: TestClient) -> None:
    cases = {
        "display_name": "   ",
        "company_name": "   ",
        "job_title": "   ",
    }
    for field_name, blank_value in cases.items():
        payload = build_register_payload("blank@test.com", **{field_name: blank_value})

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 422
        assert any(
            error["loc"][-1] == field_name
            for error in response.json()["detail"]
        )


def test_short_password_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json=build_register_payload("short@test.com", password="12345"),
    )

    assert response.status_code == 422


def test_duplicate_email_rejected(client: TestClient) -> None:
    first = client.post(
        "/api/auth/register",
        json=build_register_payload("dup@test.com"),
    )
    second = client.post(
        "/api/auth/register",
        json=build_register_payload("dup@test.com"),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 409


def test_register_with_profile_fields_and_recovery_settings(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json=build_register_payload(
            "recovery@test.com",
            display_name="测试用户",
            company_name="美太测试企业",
            job_title="创新负责人",
            recovery_question="你的第一位直属领导姓名是？",
            recovery_answer="张老师",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["display_name"] == "测试用户"
    assert body["user"]["company_name"] == "美太测试企业"
    assert body["user"]["job_title"] == "创新负责人"


def test_forgot_password_question_and_reset_flow(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload(
            "resetme@test.com",
            password="oldpass123",
            display_name="可重置用户",
            recovery_question="你的第一个独立项目名称是？",
            recovery_answer="星火计划",
        ),
    )
    assert register_response.status_code == 201, register_response.text

    question_response = client.post(
        "/api/auth/forgot-password/question",
        json={"email": "resetme@test.com"},
    )
    assert question_response.status_code == 200, question_response.text
    assert question_response.json()["recovery_question"] == "你的第一个独立项目名称是？"

    reset_response = client.post(
        "/api/auth/forgot-password/reset",
        json={
            "email": "resetme@test.com",
            "recovery_answer": "星火计划",
            "new_password": "newpass123",
        },
    )
    assert reset_response.status_code == 200, reset_response.text
    assert reset_response.json()["success"] is True

    old_login = client.post(
        "/api/auth/login",
        json={"email": "resetme@test.com", "password": "oldpass123"},
    )
    new_login = client.post(
        "/api/auth/login",
        json={"email": "resetme@test.com", "password": "newpass123"},
    )

    assert old_login.status_code == 401
    assert new_login.status_code == 200, new_login.text


def test_forgot_password_requires_existing_recovery_settings(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload("norecovery@test.com"),
    )
    assert register_response.status_code == 201, register_response.text

    question_response = client.post(
        "/api/auth/forgot-password/question",
        json={"email": "norecovery@test.com"},
    )

    assert question_response.status_code == 404


def test_forgot_password_requires_enabled_smtp(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.services import auth_service

    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload("smtp-off@test.com"),
    )
    assert register_response.status_code == 201, register_response.text

    monkeypatch.setattr(
        auth_service,
        "settings",
        SimpleNamespace(
            smtp_enabled=False,
            smtp_host="",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_from_email="",
            smtp_from_name="Meitai AI",
            smtp_use_tls=True,
            smtp_use_ssl=False,
            password_reset_url="",
            frontend_origin="http://localhost:3001",
            jwt_expire_minutes=1440,
            jwt_secret_key="test-secret",
            jwt_algorithm="HS256",
        ),
    )

    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "smtp-off@test.com"},
    )

    assert response.status_code == 503, response.text

    with db_session.SessionLocal() as db:
        user = db.query(User).filter(User.email == "smtp-off@test.com").first()
        assert user is not None
        assert user.reset_token is None
        assert user.reset_token_expires_at is None


def test_forgot_password_sends_reset_email_via_smtp(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.services import auth_service

    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload("smtp-reset@test.com"),
    )
    assert register_response.status_code == 201, register_response.text

    sent: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int):
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            sent["starttls"] = True

        def ehlo(self):
            sent["ehlo"] = sent.get("ehlo", 0) + 1

        def login(self, username: str, password: str):
            sent["login"] = (username, password)

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setattr(
        auth_service,
        "settings",
        SimpleNamespace(
            smtp_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="smtp-user",
            smtp_password="smtp-pass",
            smtp_from_email="noreply@example.com",
            smtp_from_name="Meitai AI",
            smtp_use_tls=True,
            smtp_use_ssl=False,
            password_reset_url="",
            frontend_origin="http://localhost:3001",
            jwt_expire_minutes=1440,
            jwt_secret_key="test-secret",
            jwt_algorithm="HS256",
        ),
    )
    monkeypatch.setattr(auth_service.smtplib, "SMTP", FakeSMTP)

    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "smtp-reset@test.com"},
    )

    assert response.status_code == 200, response.text
    assert sent["host"] == "smtp.example.com"
    assert sent["port"] == 587
    assert sent["starttls"] is True
    assert sent["login"] == ("smtp-user", "smtp-pass")

    message = sent["message"]
    assert message["To"] == "smtp-reset@test.com"
    html_body = message.get_body(preferencelist=("html",))
    assert html_body is not None
    assert "reset-password?token=" in html_body.get_content()

    with db_session.SessionLocal() as db:
        user = db.query(User).filter(User.email == "smtp-reset@test.com").first()
        assert user is not None
        assert user.reset_token is not None
        assert user.reset_token_expires_at is not None


def test_reset_password_by_token_succeeds_with_sqlite_naive_expiry(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.services import auth_service

    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload("token-reset@test.com", password="oldpass123"),
    )
    assert register_response.status_code == 201, register_response.text

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            pass

        def ehlo(self):
            pass

        def login(self, username: str, password: str):
            pass

        def send_message(self, message):
            pass

    monkeypatch.setattr(
        auth_service,
        "settings",
        SimpleNamespace(
            smtp_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="smtp-user",
            smtp_password="smtp-pass",
            smtp_from_email="noreply@example.com",
            smtp_from_name="Meitai AI",
            smtp_use_tls=True,
            smtp_use_ssl=False,
            password_reset_url="",
            frontend_origin="http://localhost:3001",
            jwt_expire_minutes=1440,
            jwt_secret_key="test-secret",
            jwt_algorithm="HS256",
        ),
    )
    monkeypatch.setattr(auth_service.smtplib, "SMTP", FakeSMTP)

    forgot_response = client.post(
        "/api/auth/forgot-password",
        json={"email": "token-reset@test.com"},
    )
    assert forgot_response.status_code == 200, forgot_response.text

    with db_session.SessionLocal() as db:
        user = db.query(User).filter(User.email == "token-reset@test.com").first()
        assert user is not None
        assert user.reset_token is not None
        assert user.reset_token_expires_at is not None
        assert user.reset_token_expires_at.tzinfo is None
        reset_token = user.reset_token

    reset_response = client.post(
        "/api/auth/reset-password",
        json={"token": reset_token, "new_password": "newpass123"},
    )
    assert reset_response.status_code == 200, reset_response.text

    old_login_response = client.post(
        "/api/auth/login",
        json={"email": "token-reset@test.com", "password": "oldpass123"},
    )
    assert old_login_response.status_code == 401, old_login_response.text

    new_login_response = client.post(
        "/api/auth/login",
        json={"email": "token-reset@test.com", "password": "newpass123"},
    )
    assert new_login_response.status_code == 200, new_login_response.text

    with db_session.SessionLocal() as db:
        user = db.query(User).filter(User.email == "token-reset@test.com").first()
        assert user is not None
        assert user.reset_token is None
        assert user.reset_token_expires_at is None


def test_forgot_password_smtp_failure_rolls_back_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import smtplib
    from types import SimpleNamespace

    from app.services import auth_service

    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload("smtp-fail@test.com"),
    )
    assert register_response.status_code == 201, register_response.text

    class FailingSMTP:
        def __init__(self, host: str, port: int, timeout: int):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            pass

        def ehlo(self):
            pass

        def login(self, username: str, password: str):
            pass

        def send_message(self, message):
            raise smtplib.SMTPException("send failed")

    monkeypatch.setattr(
        auth_service,
        "settings",
        SimpleNamespace(
            smtp_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="smtp-user",
            smtp_password="smtp-pass",
            smtp_from_email="noreply@example.com",
            smtp_from_name="Meitai AI",
            smtp_use_tls=True,
            smtp_use_ssl=False,
            password_reset_url="",
            frontend_origin="http://localhost:3001",
            jwt_expire_minutes=1440,
            jwt_secret_key="test-secret",
            jwt_algorithm="HS256",
        ),
    )
    monkeypatch.setattr(auth_service.smtplib, "SMTP", FailingSMTP)

    response = client.post(
        "/api/auth/forgot-password",
        json={"email": "smtp-fail@test.com"},
    )

    assert response.status_code == 503, response.text

    with db_session.SessionLocal() as db:
        user = db.query(User).filter(User.email == "smtp-fail@test.com").first()
        assert user is not None
        assert user.reset_token is None
        assert user.reset_token_expires_at is None


def test_reset_password_by_token_accepts_sqlite_naive_expiry(
    client: TestClient,
) -> None:
    register_response = client.post(
        "/api/auth/register",
        json=build_register_payload(
            "token-reset@test.com",
            password="oldpass123",
        ),
    )
    assert register_response.status_code == 201, register_response.text

    with db_session.SessionLocal() as db:
        user = db.query(User).filter(User.email == "token-reset@test.com").first()
        assert user is not None
        user.reset_token = "valid-reset-token"
        user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)
        db.add(user)
        db.commit()

    reset_response = client.post(
        "/api/auth/reset-password",
        json={"token": "valid-reset-token", "new_password": "newpass123"},
    )
    assert reset_response.status_code == 200, reset_response.text

    old_login = client.post(
        "/api/auth/login",
        json={"email": "token-reset@test.com", "password": "oldpass123"},
    )
    new_login = client.post(
        "/api/auth/login",
        json={"email": "token-reset@test.com", "password": "newpass123"},
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200, new_login.text

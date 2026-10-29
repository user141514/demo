from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.api.routes import admin
from app.db import session as db_session
from app.main import create_app
from app.models.user import User
from app.services.auth_service import _hash_password, _hash_recovery_answer


@pytest.fixture
def secured_client(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + (tmp_path / 'security.db').as_posix(),
                           connect_args={'check_same_thread': False})
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(db_session, 'engine', engine)
    monkeypatch.setattr(db_session, 'SessionLocal', sessions)
    monkeypatch.setattr(admin, 'get_snapshot', lambda: {'mode': 'mock'})
    writes = []
    monkeypatch.setattr(admin, 'update_config', lambda data: writes.append(data) or {'mode': 'mock'})
    with TestClient(create_app()) as client:
        yield client, sessions, writes
    engine.dispose()


def _request(client, method, headers=None):
    return client.request(method, '/api/admin/llm-config', headers=headers,
                          **({'json': {'model': 'qa-model'}} if method == 'PATCH' else {}))


@pytest.mark.parametrize('method', ['GET', 'PATCH'])
def test_admin_config_rejects_anonymous_requests(secured_client, method):
    client, _, writes = secured_client
    assert _request(client, method).status_code == 401
    assert writes == []


@pytest.mark.parametrize('method', ['GET', 'PATCH'])
def test_admin_config_rejects_students(secured_client, method):
    client, _, writes = secured_client
    response = client.post('/api/auth/register', json={
        'email': 'student@example.com', 'password': 'student-test-password',
        'display_name': 'Student', 'company_name': 'QA', 'job_title': 'QA',
    })
    assert response.status_code == 201
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    assert _request(client, method, headers).status_code == 403
    assert writes == []


def test_persisted_instructor_can_read_and_update_config(secured_client):
    client, sessions, writes = secured_client
    with sessions() as db:
        db.add(User(email='faculty@example.com', role='instructor',
                    hashed_password=_hash_password('instructor-test-password')))
        db.commit()
    response = client.post('/api/auth/login', json={
        'email': 'faculty@example.com', 'password': 'instructor-test-password',
    })
    assert response.status_code == 200
    headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
    assert _request(client, 'GET', headers).status_code == 200
    assert _request(client, 'PATCH', headers).status_code == 200
    assert writes == [{'model': 'qa-model'}]


def test_legacy_credentials_do_not_create_an_instructor(secured_client):
    client, sessions, _ = secured_client
    response = client.post('/api/auth/login', json={'email': 'teacher', 'password': 'meitai123456'})
    assert response.status_code == 401
    with sessions() as db:
        assert db.query(User).filter_by(email='teacher').first() is None


def test_instructor_login_checks_the_stored_password(secured_client):
    client, sessions, _ = secured_client
    with sessions() as db:
        db.add(User(email='teacher', role='instructor',
                    hashed_password=_hash_password('updated-instructor-password')))
        db.commit()
    assert client.post('/api/auth/login', json={
        'email': 'teacher', 'password': 'meitai123456',
    }).status_code == 401
    assert client.post('/api/auth/login', json={
        'email': 'teacher', 'password': 'updated-instructor-password',
    }).status_code == 200


def test_existing_instructors_must_replace_the_legacy_password(secured_client):
    client, sessions, _ = secured_client
    with sessions() as db:
        db.add(User(email='teacher', role='instructor', hashed_password=_hash_password('meitai123456')))
        db.commit()
    assert client.post('/api/auth/login', json={
        'email': 'teacher', 'password': 'meitai123456',
    }).status_code == 401


def test_retired_password_cannot_take_over_recovery_settings(secured_client):
    client, sessions, _ = secured_client
    with sessions() as db:
        db.add(User(email='teacher', role='instructor', hashed_password=_hash_password('meitai123456')))
        db.commit()
    response = client.post('/api/auth/setup-recovery', json={
        'email': 'teacher', 'password': 'meitai123456',
        'recovery_question': 'Attacker question', 'recovery_answer': 'Attacker answer',
    })
    assert response.status_code == 401
    with sessions() as db:
        user = db.query(User).filter_by(email='teacher').one()
        assert user.recovery_question is None and user.recovery_answer_hash is None


def test_instructor_recovery_rejects_retired_new_password(secured_client):
    client, sessions, _ = secured_client
    with sessions() as db:
        db.add(User(email='recovery-faculty@example.com', role='instructor',
                    hashed_password=_hash_password('current-instructor-password'),
                    recovery_question='QA question',
                    recovery_answer_hash=_hash_recovery_answer('QA answer')))
        db.commit()
    payload = {'email': 'recovery-faculty@example.com',
               'recovery_answer': 'QA answer', 'new_password': 'meitai123456'}
    response = client.post('/api/auth/forgot-password/reset', json=payload)
    assert response.status_code == 400
    assert '旧演示密码' in response.json()['detail']
    assert client.post('/api/auth/login', json={
        'email': payload['email'], 'password': 'current-instructor-password',
    }).status_code == 200

    payload['new_password'] = 'replacement-instructor-password'
    assert client.post('/api/auth/forgot-password/reset', json=payload).status_code == 200
    assert client.post('/api/auth/login', json={
        'email': payload['email'], 'password': payload['new_password'],
    }).status_code == 200


def test_instructor_token_reset_preserves_token_after_retired_password_rejection(secured_client):
    client, sessions, _ = secured_client
    with sessions() as db:
        db.add(User(email='token-faculty@example.com', role='instructor',
                    hashed_password=_hash_password('current-instructor-password'),
                    reset_token='qa-unused-reset-token',
                    reset_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
    response = client.post('/api/auth/reset-password', json={
        'token': 'qa-unused-reset-token', 'new_password': 'meitai123456',
    })
    assert response.status_code == 400
    with sessions() as db:
        user = db.query(User).filter_by(email='token-faculty@example.com').one()
        assert user.reset_token == 'qa-unused-reset-token'
        assert user.reset_token_expires_at is not None
    assert client.post('/api/auth/login', json={
        'email': 'token-faculty@example.com', 'password': 'current-instructor-password',
    }).status_code == 200

    assert client.post('/api/auth/reset-password', json={
        'token': 'qa-unused-reset-token', 'new_password': 'replacement-instructor-password',
    }).status_code == 200
    assert client.post('/api/auth/login', json={
        'email': 'token-faculty@example.com', 'password': 'replacement-instructor-password',
    }).status_code == 200


def test_instructor_creation_rejects_retired_password_without_creating_account(secured_client):
    client, sessions, _ = secured_client
    with sessions() as db:
        db.add(User(email='admin-faculty@example.com', role='instructor',
                    hashed_password=_hash_password('current-instructor-password')))
        db.commit()
    login = client.post('/api/auth/login', json={
        'email': 'admin-faculty@example.com', 'password': 'current-instructor-password',
    })
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    payload = {'email': 'new-faculty@example.com', 'password': 'meitai123456'}
    response = client.post('/api/instructor/create-instructor', json=payload, headers=headers)
    assert response.status_code == 400
    with sessions() as db:
        assert db.query(User).filter_by(email=payload['email']).first() is None

    payload['password'] = 'new-instructor-password'
    assert client.post('/api/instructor/create-instructor', json=payload, headers=headers).status_code == 201
    assert client.post('/api/auth/login', json={
        'email': payload['email'], 'password': payload['password'],
    }).status_code == 200

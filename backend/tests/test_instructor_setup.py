from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import create_app  # import all registered models
from app.db.session import Base
from app.models.user import User
from app.services.auth_service import _verify_password
from app.services.instructor_setup import configure_instructor


def test_local_setup_creates_a_hashed_account_and_requires_explicit_reset(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'setup.db').as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        configure_instructor(db, 'faculty@example.com', 'first-local-password')
        user = db.query(User).filter_by(email='faculty@example.com').one()
        assert user.role == 'instructor'
        assert user.hashed_password != 'first-local-password'
        assert _verify_password('first-local-password', user.hashed_password)
        with pytest.raises(ValueError, match='reset-password'):
            configure_instructor(db, 'faculty@example.com', 'second-local-password')
        configure_instructor(db, 'faculty@example.com', 'second-local-password', reset_password=True)
        assert _verify_password('second-local-password', user.hashed_password)
        assert not _verify_password('first-local-password', user.hashed_password)
    engine.dispose()


def test_local_setup_cannot_promote_an_existing_student(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'student.db').as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email='student@example.com', role='student', hashed_password='unchanged')
        db.add(user)
        db.commit()
        with pytest.raises(ValueError):
            configure_instructor(db, user.email, 'a-new-local-password', reset_password=True)
        assert user.role == 'student' and user.hashed_password == 'unchanged'
    engine.dispose()

from datetime import datetime, timezone

from app.schemas.auth import UserResponse


def user_response(name, role="instructor"):
    return UserResponse(id="existing-user", email="existing@example.test", display_name=name,
                        company_name=None, job_title=None, role=role,
                        created_at=datetime(2026, 10, 29, tzinfo=timezone.utc))


def test_legacy_default_role_name_is_presented_as_administrator_without_changing_identity():
    payload = user_response("讲师").model_dump()
    assert payload["display_name"] == "管理员"
    assert payload["id"] == "existing-user"
    assert payload["role"] == "instructor"


def test_custom_names_and_other_roles_are_not_rewritten():
    assert user_response("张三").model_dump()["display_name"] == "张三"
    assert user_response("讲师", role="student").model_dump()["display_name"] == "讲师"

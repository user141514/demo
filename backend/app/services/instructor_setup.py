from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth_service import _hash_password, is_legacy_instructor_password


def configure_instructor(db: Session, email: str, password: str, *, reset_password: bool = False) -> None:
    email = email.strip()
    if not email or len(email) > 255:
        raise ValueError("账号不能为空，且不能超过 255 个字符。")
    if len(password) < 12 or len(password.encode("utf-8")) > 72 or is_legacy_instructor_password(password):
        raise ValueError("请使用至少 12 个字符、UTF-8 不超过 72 字节的新密码；旧演示密码不可使用。")
    user = db.query(User).filter_by(email=email).first()
    if user is not None:
        if user.role != "instructor":
            raise ValueError("该账号已被学员使用，请指定另一个讲师账号。")
        if not reset_password:
            raise ValueError("讲师账号已存在；如需重置密码，请显式使用 --reset-password。")
        user.hashed_password = _hash_password(password)
        user.reset_token = None
        user.reset_token_expires_at = None
    else:
        db.add(User(email=email, hashed_password=_hash_password(password),
                    display_name="讲师", role="instructor"))
    db.commit()

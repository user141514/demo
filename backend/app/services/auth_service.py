import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import quote

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordQuestionRequest,
    ForgotPasswordQuestionResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserResponse,
)

TEACHER_EMAIL = "teacher"
TEACHER_PASSWORD = "meitai123456"
logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _hash_recovery_answer(answer: str) -> str:
    normalized = answer.strip().lower()
    return bcrypt.hashpw(normalized.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_recovery_answer(answer: str, hashed: str) -> bool:
    normalized = answer.strip().lower()
    return bcrypt.checkpw(normalized.encode("utf-8"), hashed.encode("utf-8"))


def _create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def register(db: Session, request: RegisterRequest) -> TokenResponse:
    existing = db.query(User).filter(User.email == request.email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已被注册。",
        )

    user = User(
        email=request.email,
        hashed_password=_hash_password(request.password),
        display_name=request.display_name,
        company_name=request.company_name,
        job_title=request.job_title,
        recovery_question=request.recovery_question.strip()
        if request.recovery_question and request.recovery_question.strip()
        else None,
        recovery_answer_hash=_hash_recovery_answer(request.recovery_answer)
        if request.recovery_answer and request.recovery_answer.strip()
        else None,
        role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user, from_attributes=True),
    )


def get_recovery_question(
    db: Session,
    request: ForgotPasswordQuestionRequest,
) -> ForgotPasswordQuestionResponse:
    user = db.query(User).filter(User.email == request.email).first()
    if user is None or not user.recovery_question or not user.recovery_answer_hash:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该账号未设置找回问题，请联系管理员协助处理。",
        )

    return ForgotPasswordQuestionResponse(
        email=user.email,
        recovery_question=user.recovery_question,
    )


def reset_password(
    db: Session,
    request: ResetPasswordRequest,
) -> ResetPasswordResponse:
    user = db.query(User).filter(User.email == request.email).first()
    if (
        user is None
        or not user.recovery_answer_hash
        or not _verify_recovery_answer(request.recovery_answer, user.recovery_answer_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="找回答案不正确，请重新输入。",
        )

    user.hashed_password = _hash_password(request.new_password)
    db.add(user)
    db.commit()
    return ResetPasswordResponse()


def update_recovery(
    db: Session,
    user: User,
    question: str,
    answer: str,
) -> None:
    user.recovery_question = question.strip()
    user.recovery_answer_hash = _hash_recovery_answer(answer)
    db.add(user)
    db.commit()


def setup_recovery(
    db: Session,
    email: str,
    password: str,
    question: str,
    answer: str,
) -> None:
    user = db.query(User).filter(User.email == email).first()
    if user is None or not _verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误，无法补录找回设置。",
        )

    user.recovery_question = question.strip()
    user.recovery_answer_hash = _hash_recovery_answer(answer)
    db.add(user)
    db.commit()


def _get_password_reset_mail_config_errors() -> list[str]:
    errors: list[str] = []
    if not settings.smtp_enabled:
        errors.append("SMTP_ENABLED is false")
    if not settings.smtp_host:
        errors.append("SMTP_HOST is empty")
    if not settings.smtp_from_email:
        errors.append("SMTP_FROM_EMAIL is empty")
    if settings.smtp_username and not settings.smtp_password:
        errors.append("SMTP_PASSWORD is empty while SMTP_USERNAME is set")
    if settings.smtp_password and not settings.smtp_username:
        errors.append("SMTP_USERNAME is empty while SMTP_PASSWORD is set")
    if settings.smtp_use_ssl and settings.smtp_use_tls:
        errors.append("SMTP_USE_SSL and SMTP_USE_TLS cannot both be true")
    return errors


def _validate_password_reset_mail_settings() -> None:
    errors = _get_password_reset_mail_config_errors()
    if not errors:
        return

    logger.warning(
        "Password reset email unavailable: %s",
        "; ".join(errors),
    )
    detail = "密码找回邮件服务配置不完整，请联系管理员。"
    if "SMTP_ENABLED is false" in errors:
        detail = "密码找回邮件服务未启用，请联系管理员。"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


def _build_password_reset_link(token: str) -> str:
    base_url = settings.password_reset_url or (
        f"{settings.frontend_origin.rstrip('/')}/reset-password"
    )
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}token={quote(token)}"


def _send_password_reset_email(recipient_email: str, token: str) -> None:
    _validate_password_reset_mail_settings()

    reset_link = _build_password_reset_link(token)
    message = EmailMessage()
    message["Subject"] = "美太 AI 创新智能体密码重置"
    message["From"] = formataddr(
        (settings.smtp_from_name, settings.smtp_from_email)
    )
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "您好，",
                "",
                "我们收到了您的密码重置申请。请在 1 小时内打开以下链接设置新密码：",
                reset_link,
                "",
                "如果这不是您的操作，请忽略此邮件。",
            ]
        )
    )
    message.add_alternative(
        (
            "<p>您好，</p>"
            "<p>我们收到了您的密码重置申请。请在 1 小时内点击以下链接设置新密码：</p>"
            f"<p><a href=\"{reset_link}\">{reset_link}</a></p>"
            "<p>如果这不是您的操作，请忽略此邮件。</p>"
        ),
        subtype="html",
    )

    smtp_client = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    try:
        with smtp_client(settings.smtp_host, settings.smtp_port, timeout=30) as client:
            client.ehlo()
            if not settings.smtp_use_ssl and settings.smtp_use_tls:
                client.starttls()
                client.ehlo()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning(
            "Failed to send password reset email to %s: %s",
            recipient_email,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="密码找回邮件发送失败，请稍后重试。",
        ) from exc


def request_password_reset(db: Session, email: str) -> None:
    _validate_password_reset_mail_settings()

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db.add(user)
    try:
        _send_password_reset_email(user.email, token)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected password reset failure for %s", email)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="密码找回服务暂时不可用，请稍后重试。",
        ) from exc


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def reset_password_by_token(db: Session, token: str, new_password: str) -> None:
    user = db.query(User).filter(User.reset_token == token).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="重置链接无效或已过期，请重新申请找回。",
        )
    expires_at = user.reset_token_expires_at
    if (
        expires_at is None
        or _as_utc_aware(expires_at) < datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重置链接已过期，请重新申请找回。",
        )

    user.hashed_password = _hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.add(user)
    db.commit()


def authenticate(db: Session, request: LoginRequest) -> TokenResponse:
    if request.email == TEACHER_EMAIL and request.password == TEACHER_PASSWORD:
        teacher = db.query(User).filter(User.email == TEACHER_EMAIL).first()
        if teacher is None:
            teacher = User(
                email=TEACHER_EMAIL,
                hashed_password=_hash_password(TEACHER_PASSWORD),
                display_name="管理员",
                role="instructor",
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)
        token = _create_access_token(teacher.id)
        return TokenResponse(
            access_token=token,
            user=UserResponse.model_validate(teacher, from_attributes=True),
        )

    user = db.query(User).filter(User.email == request.email).first()
    if user is None or not _verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误。",
        )

    token = _create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user, from_attributes=True),
    )


def get_user_from_token(db: Session, token: str) -> User:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise _unauthorized()
    except JWTError:
        raise _unauthorized()

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _unauthorized()
    return user


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证信息无效或已过期，请重新登录。",
    )

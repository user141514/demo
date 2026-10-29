from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    company_name: str = Field(min_length=1, max_length=255)
    job_title: str = Field(min_length=1, max_length=100)
    recovery_question: str | None = Field(default=None, max_length=255)
    recovery_answer: str | None = Field(default=None, max_length=255)

    @field_validator("email", "display_name", "company_name", "job_title", mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("该字段不能为空")
        normalized = value.strip()
        if not normalized:
            raise ValueError("该字段不能为空")
        return normalized

    @field_validator("recovery_question", "recovery_answer", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("字段格式不正确")
        normalized = value.strip()
        return normalized or None


class CreateInstructorRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None
    company_name: str | None
    job_title: str | None
    role: str
    has_recovery: bool = False
    created_at: datetime

    @field_serializer("display_name")
    def display_name_label(self, value: str | None) -> str | None:
        return "管理员" if self.role == "instructor" and value == "讲师" else value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ForgotPasswordQuestionRequest(BaseModel):
    email: str = Field(max_length=255)


class ForgotPasswordQuestionResponse(BaseModel):
    email: str
    recovery_question: str


class ResetPasswordRequest(BaseModel):
    email: str = Field(max_length=255)
    recovery_answer: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=6, max_length=128)


class ResetPasswordResponse(BaseModel):
    success: bool = True


class UpdateRecoveryRequest(BaseModel):
    recovery_question: str = Field(min_length=1, max_length=255)
    recovery_answer: str = Field(min_length=1, max_length=255)


class UpdateRecoveryResponse(BaseModel):
    success: bool = True


class SetupRecoveryRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)
    recovery_question: str = Field(min_length=1, max_length=255)
    recovery_answer: str = Field(min_length=1, max_length=255)


class SetupRecoveryResponse(BaseModel):
    success: bool = True


class ForgotPasswordRequest(BaseModel):
    email: str = Field(max_length=255)


class ForgotPasswordResponse(BaseModel):
    success: bool = True


class ResetPasswordByTokenRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6, max_length=128)


class ResetPasswordByTokenResponse(BaseModel):
    success: bool = True

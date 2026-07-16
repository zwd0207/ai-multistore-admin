from pydantic import BaseModel, EmailStr, Field, field_validator


class TenantInvitationCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=160)
    tenant_name: str = Field(min_length=1, max_length=160)

    @field_validator("display_name", "tenant_name", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class TenantInvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=12, max_length=128)


class MfaEnrollmentComplete(BaseModel):
    enrollment_token: str = Field(min_length=32, max_length=200)
    code: str = Field(pattern=r"^\d{6}$")


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetComplete(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=12, max_length=128)

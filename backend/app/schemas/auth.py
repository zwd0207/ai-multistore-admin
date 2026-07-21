from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login_identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=14, pattern=r"^(?:\d{6}|[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4})$")

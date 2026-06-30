from pydantic import BaseModel, Field, field_validator


class ApiCredentialSmokeTestRequest(BaseModel):
    platform: str = Field(default="all")
    mode: str = Field(default="readonly")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"naver", "coupang", "all"}:
            raise ValueError("platform must be naver, coupang, or all")
        return normalized

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "readonly":
            raise ValueError("mode must be readonly")
        return normalized

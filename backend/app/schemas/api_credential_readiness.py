from pydantic import BaseModel, Field, field_validator, model_validator


class ApiCredentialSmokeTestRequest(BaseModel):
    platform: str = Field(default="all")
    mode: str = Field(default="readonly")
    store_id: int | None = Field(default=None, ge=1)
    credential_id: int | None = Field(default=None, ge=1)

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

    @model_validator(mode="after")
    def validate_store_bound_fields(self) -> "ApiCredentialSmokeTestRequest":
        if self.credential_id is not None and self.store_id is None:
            raise ValueError("store_id is required when credential_id is provided")
        return self

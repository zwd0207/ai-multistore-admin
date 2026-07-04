from typing import Any

from pydantic import BaseModel, Field


class BatchReadonlyEvidenceRequest(BaseModel):
    evidence_items: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    max_items: int = Field(default=10, ge=1, le=10)

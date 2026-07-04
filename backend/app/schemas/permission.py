from typing import Any

from pydantic import BaseModel, Field


class PermissionMockCheckRequest(BaseModel):
    actor_context: dict[str, Any] = Field(default_factory=dict)
    store_id: int = Field(..., ge=1)
    operation_key: str = Field(..., min_length=1, max_length=120)


class SensitiveActionPermissionMockCheckRequest(BaseModel):
    actor_context: dict[str, Any] = Field(default_factory=dict)
    store_id: int = Field(..., ge=1)
    action_key: str = Field(..., min_length=1, max_length=120)
    manual_approval: bool = False


class StoreMembershipReadonlyCheckRequest(BaseModel):
    actor_context: dict[str, Any] = Field(default_factory=dict)
    target_user_key_hash: str = Field(..., min_length=1, max_length=120)
    target_store_id: int = Field(..., ge=1)
    target_role: str = Field(..., min_length=1, max_length=80)
    manual_approval: bool = False
    assignment_reason: str = Field(..., min_length=1, max_length=240)


class UserInvitationReadonlyCheckRequest(BaseModel):
    actor_context: dict[str, Any] = Field(default_factory=dict)
    target_user_key_hash: str = Field(..., min_length=1, max_length=120)
    login_identifier_hash: str = Field(..., min_length=1, max_length=120)
    login_identifier_masked: str = Field(..., min_length=1, max_length=120)
    target_store_ids: list[int] = Field(..., min_length=1, max_length=5)
    target_role: str = Field(..., min_length=1, max_length=80)
    manual_approval: bool = False
    invitation_reason: str = Field(..., min_length=1, max_length=240)
    backup_evidence_planned: bool = False
    audit_evidence_planned: bool = False
    membership_assignment_plan_ready: bool = False
    existing_user_hashes: list[str] = Field(default_factory=list, max_length=20)

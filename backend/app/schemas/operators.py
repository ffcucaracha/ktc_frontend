from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import LoginFailureReason
from app.schemas.auth import UserResponse


class OperatorCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=8)


class OperatorPatchRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class OperatorCreateResponse(BaseModel):
    operator: UserResponse
    temporary_password: str | None = None


class OperatorResetPasswordResponse(BaseModel):
    operator: UserResponse
    temporary_password: str


class OperatorListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    limit: int
    offset: int


class LoginHistoryItem(BaseModel):
    id: UUID
    occurred_at: datetime
    success: bool
    failure_reason: LoginFailureReason | None
    ip_address: str | None
    user_agent: str | None

    model_config = ConfigDict(from_attributes=True)


class LoginHistoryResponse(BaseModel):
    items: list[LoginHistoryItem]
    total: int
    limit: int
    offset: int


class LoginStatsResponse(BaseModel):
    successful_count: int
    last_successful_login_at: datetime | None

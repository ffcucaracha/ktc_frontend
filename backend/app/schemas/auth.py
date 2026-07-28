from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    username: str
    full_name: str
    role: UserRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MeResponse(BaseModel):
    user: UserResponse

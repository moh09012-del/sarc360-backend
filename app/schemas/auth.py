"""
SARC360 ERP - Auth Schemas
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    tenant_id: uuid.UUID
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=300)
    phone_e164: str | None = Field(None, max_length=20, description="+9665XXXXXXXX")
    user_type: str = Field("staff", description="staff | employee | client")
    client_id: uuid.UUID | None = None
    employee_id: uuid.UUID | None = None


class LoginRequest(BaseModel):
    tenant_id: uuid.UUID
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    roles: list[str]
    user_type: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    user_type: str
    is_active: bool
    is_email_verified: bool
    last_login_at: datetime | None
    created_at: datetime

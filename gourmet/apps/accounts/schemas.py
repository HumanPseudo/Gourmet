from __future__ import annotations

from uuid import UUID

from ninja import Schema


class RegisterIn(Schema):
    email: str
    name: str
    number: str = ""
    password: str
    role_id: UUID | None = None


class LoginIn(Schema):
    email: str
    password: str


class RoleOut(Schema):
    id: UUID
    name: str
    description: str | None = None
    model_config = {"from_attributes": True}


class RoleIn(Schema):
    name: str
    description: str | None = None


class UserOut(Schema):
    id: UUID
    email: str
    name: str
    number: str
    role: RoleOut | None = None
    is_staff: bool
    is_active: bool
    model_config = {"from_attributes": True}


class AuthTokenOut(Schema):
    token: str
    user: UserOut


class UserIn(Schema):
    email: str
    name: str
    number: str = ""
    role_id: UUID | None = None
    is_staff: bool = False
    is_active: bool = True
    password: str | None = None

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.contrib.auth import authenticate
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Router, Schema
from ninja.types import DictStrAny

from gourmet.apps.menu.api import router as menu_router
from gourmet.apps.tables.api import router as tables_router
from gourmet.apps.jukebox.api import router as jukebox_router

from gourmet.apps.schemas import MessageOut

from .auth import AdminTokenAuth, TokenAuth
from .forms import CustomUserCreationForm
from .models import AuthToken, Role, User

api = NinjaAPI(
    auth=TokenAuth(),
    title="Gourmet API",
    version="1.0.0",
    description="Restaurant management system — menu, orders, and administration.",
)
admin_api = Router(auth=AdminTokenAuth())


# ── Schemas ────────────────────────────────────────────────────────────


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


# ── Helpers ────────────────────────────────────────────────────────────


def user_to_out(u: User) -> UserOut:
    role_out: RoleOut | None = None
    if u.role_id is not None and u.role is not None:
        role_out = RoleOut(
            id=u.role.pk,
            name=u.role.name,
            description=u.role.description,
        )
    return UserOut(
        id=u.pk,
        email=u.email,
        name=u.name,
        number=u.number,
        role=role_out,
        is_staff=u.is_staff,
        is_active=u.is_active,
    )


# ── Public endpoints ───────────────────────────────────────────────────


@api.post(
    "/auth/register", auth=None, tags=["Auth"],
    response={201: AuthTokenOut, 400: MessageOut},
    summary="Register a new user",
)
def register(
    request: HttpRequest, payload: RegisterIn
) -> tuple[int, dict[str, str | UserOut]]:
    data: dict[str, str | UUID | None] = {
        "email": payload.email,
        "name": payload.name,
        "number": payload.number,
        "password1": payload.password,
        "password2": payload.password,
        "role_id": payload.role_id,
    }
    form = CustomUserCreationForm(data)
    if not form.is_valid():
        errors = "; ".join(
            f"{k}: {', '.join(str(e) for e in v)}" for k, v in form.errors.items()
        )
        return 400, {"detail": errors}
    user = form.save()
    token = AuthToken.create_token(user)
    return 201, {"token": token.key, "user": user_to_out(user)}


@api.post(
    "/auth/login", auth=None, tags=["Auth"],
    response={200: AuthTokenOut, 401: MessageOut},
    summary="Login and get auth token",
)
def login_view(
    request: HttpRequest, payload: LoginIn
) -> tuple[int, dict[str, str | UserOut]]:
    user = authenticate(request, email=payload.email, password=payload.password)
    if not isinstance(user, User):
        return 401, {"detail": "Invalid credentials"}
    token = AuthToken.create_token(user)
    return 200, {"token": token.key, "user": user_to_out(user)}


@api.post(
    "/auth/logout", tags=["Auth"], response=MessageOut,
    summary="Logout and invalidate token",
)
def logout_view(request: HttpRequest) -> dict[str, str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        key = auth_header.removeprefix("Bearer ")
        AuthToken.objects.filter(key=key).delete()
    return {"detail": "Logged out"}


@api.get(
    "/auth/me", tags=["Auth"],
    response={200: UserOut, 401: MessageOut},
    summary="Get current user profile",
)
def me(request: Any) -> tuple[int, UserOut] | tuple[int, DictStrAny]:
    if not request.auth:
        return 401, {"detail": "Not authenticated"}
    return 200, user_to_out(request.auth)


# ── Admin endpoints ────────────────────────────────────────────────────


@admin_api.get("/roles", response=list[RoleOut], summary="List all roles")
def list_roles(request: HttpRequest) -> list[RoleOut]:
    return [
        RoleOut(id=r.pk, name=r.name, description=r.description)
        for r in Role.objects.all().order_by("name")
    ]


@admin_api.post(
    "/roles", response={201: RoleOut, 400: MessageOut},
    summary="Create a role",
)
def create_role(
    request: HttpRequest, payload: RoleIn
) -> tuple[int, RoleOut] | tuple[int, dict[str, str]]:
    if Role.objects.filter(name=payload.name).exists():
        return 400, {"detail": "Role with this name already exists"}
    role = Role.objects.create(name=payload.name, description=payload.description)
    return 201, RoleOut(id=role.pk, name=role.name, description=role.description)


@admin_api.get("/roles/{role_id}", response=RoleOut, summary="Get role by ID")
def get_role(request: HttpRequest, role_id: UUID) -> RoleOut:
    role = get_object_or_404(Role, pk=role_id)
    return RoleOut(id=role.pk, name=role.name, description=role.description)


@admin_api.put("/roles/{role_id}", response=RoleOut, summary="Update a role")
def update_role(request: HttpRequest, role_id: UUID, payload: RoleIn) -> RoleOut:
    role = get_object_or_404(Role, pk=role_id)
    role.name = payload.name
    role.description = payload.description
    role.save()
    return RoleOut(id=role.pk, name=role.name, description=role.description)


@admin_api.delete("/roles/{role_id}", response=MessageOut, summary="Delete a role")
def delete_role(request: HttpRequest, role_id: UUID) -> dict[str, str]:
    role = get_object_or_404(Role, pk=role_id)
    role.delete()
    return {"detail": "Role deleted"}


@admin_api.get("/users", response=list[UserOut], summary="List all users")
def list_users(request: HttpRequest) -> list[UserOut]:
    return [user_to_out(u) for u in User.objects.all().order_by("email")]


@admin_api.get("/users/{user_id}", response=UserOut, summary="Get user by ID")
def get_user(request: HttpRequest, user_id: UUID) -> UserOut:
    user = get_object_or_404(User, pk=user_id)
    return user_to_out(user)


api.add_router("/admin", admin_api, tags=["Admin"])
api.add_router("/menu", menu_router, tags=["Menu"])
api.add_router("/tables", tables_router, tags=["Tables"])
api.add_router("/jukebox", jukebox_router, tags=["Jukebox"])

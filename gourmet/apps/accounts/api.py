from __future__ import annotations

from typing import Any
from uuid import UUID

from django.http import HttpRequest
from ninja import NinjaAPI, Router
from ninja.pagination import paginate
from ninja.throttling import AnonRateThrottle, AuthRateThrottle
from ninja.types import DictStrAny

from gourmet.apps.exceptions import register_exception_handlers
from gourmet.apps.jukebox.api import router as jukebox_router
from gourmet.apps.menu.api import router as menu_router
from gourmet.apps.schemas import MessageOut
from gourmet.apps.tables.api import router as tables_router

from .auth import AdminTokenAuth, TokenAuth
from .models import AuthToken, Role, User
from .schemas import AuthTokenOut, LoginIn, RegisterIn, RoleIn, RoleOut, UserOut
from .services import RoleService, UserService

api = NinjaAPI(
    auth=TokenAuth(),
    title="Gourmet API",
    version="1.0.0",
    description="Restaurant management system — menu, orders, and administration.",
    throttle=[AnonRateThrottle(), AuthRateThrottle()],
)
admin_api = Router(auth=AdminTokenAuth())

register_exception_handlers(api)


# ── Public endpoints ───────────────────────────────────────────────────


@api.post(
    "/auth/register",
    auth=None,
    tags=["Auth"],
    response={201: AuthTokenOut, 400: MessageOut},
    summary="Register a new user",
)
def register(
    request: HttpRequest, payload: RegisterIn
) -> tuple[int, AuthTokenOut | dict[str, str]]:
    try:
        user, token = UserService.register(payload)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 201, AuthTokenOut(token=token.key, user=UserOut.model_validate(user))


@api.post(
    "/auth/login",
    auth=None,
    tags=["Auth"],
    response={200: AuthTokenOut, 401: MessageOut},
    summary="Login and get auth token",
)
def login_view(
    request: HttpRequest, payload: LoginIn
) -> tuple[int, AuthTokenOut | dict[str, str]]:
    user = UserService.login(email=payload.email, password=payload.password)
    if not isinstance(user, User):
        return 401, {"detail": "Invalid credentials"}
    token = AuthToken.create_token(user)
    return 200, AuthTokenOut(token=token.key, user=UserOut.model_validate(user))


@api.post(
    "/auth/logout",
    tags=["Auth"],
    response=MessageOut,
    summary="Logout and invalidate token",
)
def logout_view(request: HttpRequest) -> dict[str, str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        key = auth_header.removeprefix("Bearer ")
        AuthToken.objects.filter(key=key).delete()
    return {"detail": "Logged out"}


@api.get(
    "/auth/me",
    tags=["Auth"],
    response={200: UserOut, 401: MessageOut},
    summary="Get current user profile",
)
def me(
    request: Any,
) -> tuple[int, UserOut] | tuple[int, DictStrAny]:
    if not request.auth:
        return 401, {"detail": "Not authenticated"}
    return 200, request.auth


# ── Admin endpoints ────────────────────────────────────────────────────


@admin_api.get("/roles", response=list[RoleOut], summary="List all roles")
def list_roles(request: HttpRequest) -> Any:
    return RoleService.list()


@admin_api.post(
    "/roles",
    response={201: RoleOut, 400: MessageOut},
    summary="Create a role",
)
def create_role(
    request: HttpRequest, payload: RoleIn
) -> tuple[int, RoleOut] | tuple[int, dict[str, str]]:
    try:
        role = RoleService.create(payload)
    except ValueError as e:
        return 400, {"detail": str(e)}
    return 201, RoleOut.model_validate(role)


@admin_api.get(
    "/roles/{role_id}", response=RoleOut, summary="Get role by ID"
)
def get_role(request: HttpRequest, role_id: UUID) -> Role:
    return RoleService.get(role_id)


@admin_api.put(
    "/roles/{role_id}", response=RoleOut, summary="Update a role"
)
def update_role(
    request: HttpRequest, role_id: UUID, payload: RoleIn
) -> Role:
    role = RoleService.get(role_id)
    return RoleService.update(role, payload)


@admin_api.delete(
    "/roles/{role_id}", response=MessageOut, summary="Delete a role"
)
def delete_role(request: HttpRequest, role_id: UUID) -> dict[str, str]:
    role = RoleService.get(role_id)
    RoleService.delete(role)
    return {"detail": "Role deleted"}


@admin_api.get(
    "/users", response=list[UserOut], summary="List all users"
)
@paginate
def list_users(request: HttpRequest) -> Any:
    return UserService.list()


@admin_api.get(
    "/users/{user_id}", response=UserOut, summary="Get user by ID"
)
def get_user(request: HttpRequest, user_id: UUID) -> User:
    return UserService.get(user_id)


api.add_router("/admin", admin_api, tags=["Admin"])
api.add_router("/menu", menu_router, tags=["Menu"])
api.add_router("/tables", tables_router, tags=["Tables"])
api.add_router("/jukebox", jukebox_router, tags=["Jukebox"])

import functools
from typing import Any

from django.http import HttpRequest
from django.shortcuts import redirect, render
from ninja.errors import HttpError
from ninja.security import HttpBearer

from .models import AuthToken


class TokenAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token: str) -> Any:
        try:
            user = AuthToken.objects.select_related("user").get(key=token).user
        except AuthToken.DoesNotExist:
            return None
        if not user.is_active:
            return None
        return user


class AdminTokenAuth(TokenAuth):
    def authenticate(self, request: HttpRequest, token: str) -> Any:
        user = super().authenticate(request, token)
        if user is not None and not user.is_staff:
            raise HttpError(403, "Admin access required")
        return user


class RoleTokenAuth(TokenAuth):
    def __init__(self, *roles: str) -> None:
        self.roles = roles

    def authenticate(self, request: HttpRequest, token: str) -> Any:
        user = super().authenticate(request, token)
        if user and not user.is_superuser and self.roles:
            if not (user.is_staff and user.role and user.role.name in self.roles):
                raise HttpError(403, "Role required")
        return user


def role_required(*roles: str):
    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if request.user.is_superuser:
                return view(request, *args, **kwargs)
            if request.user.is_staff and (
                not roles or (request.user.role and request.user.role.name in roles)
            ):
                return view(request, *args, **kwargs)
            return render(request, "errors/403.html", status=403)
        return wrapper
    return decorator

from typing import Any

from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import HttpBearer

from .models import AuthToken


class TokenAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token: str) -> Any:
        try:
            return AuthToken.objects.select_related("user").get(key=token).user
        except AuthToken.DoesNotExist:
            pass


class AdminTokenAuth(TokenAuth):
    def authenticate(self, request: HttpRequest, token: str) -> Any:
        user = super().authenticate(request, token)
        if user is not None and not user.is_staff:
            raise HttpError(403, "Admin access required")
        return user

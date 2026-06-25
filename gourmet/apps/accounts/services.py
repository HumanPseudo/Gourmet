from __future__ import annotations

from typing import Any
from uuid import UUID

from django.contrib.auth import authenticate
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from .forms import CustomUserCreationForm
from .models import AuthToken, Role, User
from .schemas import RegisterIn, RoleIn, UserIn


class UserService:
    @staticmethod
    def register(data: RegisterIn) -> tuple[User, AuthToken]:
        form_data: dict[str, Any] = {
            "email": data.email,
            "name": data.name,
            "number": data.number,
            "password1": data.password,
            "password2": data.password,
        }
        if data.role_id:
            form_data["role"] = data.role_id
        form = CustomUserCreationForm(form_data)
        if not form.is_valid():
            errors = "; ".join(
                f"{k}: {', '.join(str(e) for e in v)}"
                for k, v in form.errors.items()
            )
            raise ValueError(errors)
        user = form.save()
        token = AuthToken.create_token(user)
        return user, token

    @staticmethod
    def login(email: str, password: str) -> User | None:
        return authenticate(email=email, password=password)

    @staticmethod
    def list() -> QuerySet[User]:
        return User.objects.select_related("role").all().order_by("email")

    @staticmethod
    def get(user_id: UUID) -> User:
        return get_object_or_404(
            User.objects.select_related("role"),
            pk=user_id,
        )

    @staticmethod
    def update(user: User, data: UserIn) -> User:
        user.email = data.email
        user.name = data.name
        user.number = data.number
        user.role_id = data.role_id
        user.is_staff = data.is_staff
        user.is_active = data.is_active
        if data.password:
            user.set_password(data.password)
        user.save()
        return user


class RoleService:
    @staticmethod
    def list() -> QuerySet[Role]:
        return Role.objects.all().order_by("name")

    @staticmethod
    def create(data: RoleIn) -> Role:
        if Role.objects.filter(name=data.name).exists():
            raise ValueError("Role with this name already exists")
        return Role.objects.create(name=data.name, description=data.description)

    @staticmethod
    def get(role_id: UUID) -> Role:
        return get_object_or_404(Role, pk=role_id)

    @staticmethod
    def update(role: Role, data: RoleIn) -> Role:
        if data.name != role.name and Role.objects.filter(name=data.name).exists():
            raise ValueError("Role with this name already exists")
        role.name = data.name
        role.description = data.description
        role.save()
        return role

    @staticmethod
    def delete(role: Role) -> None:
        role.delete()

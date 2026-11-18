from __future__ import annotations

import secrets
import uuid
from typing import Any, TypeVar

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models

_T = TypeVar("_T", bound="User")


class Role(models.Model):
    """
    Model representing user roles (e.g., Admin, Manager, Customer).
    """

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name: models.CharField[str, str] = models.CharField(max_length=100, unique=True)
    description: models.TextField[str | None, str | None] = models.TextField(
        blank=True, null=True
    )

    def __str__(self) -> str:
        return self.name


class CustomUserManager(UserManager[_T]):
    """
    Custom manager for User model where email is the unique identifier
    for authentication instead of usernames.
    """

    def create_user(
        self,
        username: str | None = None,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> _T:
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        username: str | None = None,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> _T:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model for the gourmet project using Email as the primary identifier.
    """

    username = None  # type: ignore[assignment]

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    email: models.EmailField[str, str] = models.EmailField(
        unique=True, verbose_name="Email Address"
    )
    name: models.CharField[str, str] = models.CharField(
        max_length=255, blank=True, verbose_name="Full Name"
    )
    number: models.CharField[str, str] = models.CharField(
        max_length=20, blank=True, verbose_name="Phone Number"
    )
    role: models.ForeignKey[Role | None, Role | None] = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    role_id: uuid.UUID | None
    is_staff: bool
    is_active: bool

    # Disable default first_name and last_name in favor of 'name'
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()  # type: ignore[misc]

    def __str__(self) -> str:
        return self.email

    def _has_role(self, name: str) -> bool:
        return self.is_staff and self.role is not None and self.role.name == name

    @property
    def is_admin(self) -> bool:
        """Administrative access. Superusers always qualify (mirrors
        ``role_required``'s superuser bypass)."""
        return self.is_superuser or self._has_role("admin")

    @property
    def is_waiter(self) -> bool:
        """True for staff users whose role is ``waiter``."""
        return self._has_role("waiter")

    @property
    def is_kitchen(self) -> bool:
        """True for staff users whose role is ``kitchen``."""
        return self._has_role("kitchen")


class AuditLog(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField(max_length=50)
    target = models.CharField(max_length=200, blank=True)
    detail = models.CharField(max_length=500, blank=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.user} {self.action}"


class AuthToken(models.Model):
    key: models.CharField[str, str] = models.CharField(max_length=64, primary_key=True)
    user: models.ForeignKey[User, User] = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="auth_tokens"
    )
    created: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.key[:16] + "..."

    @classmethod
    def generate_key(cls) -> str:
        return secrets.token_hex(32)

    @classmethod
    def create_token(cls, user: User) -> AuthToken:
        return cls.objects.create(key=cls.generate_key(), user=user)

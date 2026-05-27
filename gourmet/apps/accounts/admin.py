from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin[Role]):
    list_display = ("name", "description")


@admin.register(User)
class CustomUserAdmin(UserAdmin[User]):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    # Fields to show when editing a user
    # Note: We remove 'username', 'first_name', and 'last_name'
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name", "number", "role")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    # Fields to show when creating a user
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "number", "role", "password1", "password2"),
            },
        ),
    )

    list_display = ("email", "name", "role", "is_staff", "is_active")
    search_fields = ("email", "name")
    ordering = ("email",)

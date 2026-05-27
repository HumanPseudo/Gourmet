from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class CustomUserCreationForm(UserCreationForm[User]):
    """
    Form for creating users with email instead of username.
    """

    class Meta:  # type: ignore[override]
        model = User
        fields = ("email", "name", "number", "role")


class CustomUserChangeForm(UserChangeForm[User]):
    """
    Form for updating users with email instead of username.
    """

    class Meta:  # type: ignore[override]
        model = User
        fields = ("email", "name", "number", "role")

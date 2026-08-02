from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import User


class CustomUserCreationForm(UserCreationForm[User]):
    class Meta:
        model = User
        fields = ("email",)


class CustomUserChangeForm(UserChangeForm[User]):
    class Meta:
        model = User
        fields = ("email",)


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if email and password:
            self.user_cache = authenticate(
                self.request, email=email, password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
        return self.cleaned_data

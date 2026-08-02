from django.contrib.auth import views as auth_views
from django.urls import URLPattern, path

from .forms import EmailAuthenticationForm

urlpatterns: list[URLPattern] = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=EmailAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]

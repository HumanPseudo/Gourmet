from __future__ import annotations

import typing as t

from django.http import HttpRequest
from django.test import Client
from django.urls import path
from pytest_django.asserts import assertTemplateUsed
from pytest_django.fixtures import SettingsWrapper


def error_view(request: HttpRequest) -> t.NoReturn:
    """View that raises a server error."""
    raise ValueError


# Test URLconf that extends the base project URLs.
# Mirror the project's custom 500 handler so the error template resolves the
# same way it does in production (see gourmet/urls.py).
handler500 = "gourmet.views.server_error"
urlpatterns = [path("error/", error_view)]


def test_404_page(client: Client) -> None:
    response = client.get("/non-existent-page/")
    assert response.status_code == 404
    assertTemplateUsed(response, "errors/404.html")


def test_500_page(client: Client, settings: SettingsWrapper) -> None:
    settings.ROOT_URLCONF = "tests.test_error_pages"
    client.raise_request_exception = False
    response = client.get("/error/")
    assert response.status_code == 500
    assertTemplateUsed(response, "errors/500.html")

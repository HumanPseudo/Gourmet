from __future__ import annotations

from django import http
from django.shortcuts import render


def bad_request(
    request: http.HttpRequest,
    exception: Exception | None = None,
) -> http.HttpResponse:
    return render(request, "errors/400.html", status=400)


def permission_denied(
    request: http.HttpRequest,
    exception: Exception | None = None,
) -> http.HttpResponse:
    return render(request, "errors/403.html", status=403)


def not_found(
    request: http.HttpRequest,
    exception: Exception | None = None,
) -> http.HttpResponse:
    return render(request, "errors/404.html", status=404)


def server_error(
    request: http.HttpRequest,
    exception: Exception | None = None,
) -> http.HttpResponse:
    return render(request, "errors/500.html", status=500)

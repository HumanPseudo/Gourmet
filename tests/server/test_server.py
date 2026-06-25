from __future__ import annotations

import requests
from django.conf import LazySettings


def test_admin_login_page(
    server: str,
    settings: LazySettings,
) -> None:
    """Admin login page returns 200."""
    response = requests.get(f"{server}/{settings.PROJECT_NAME}-admin/login/", timeout=3)
    assert response.status_code == 200


def test_static_css_bundle(server: str) -> None:
    """Static CSS bundle is served."""
    response = requests.get(f"{server}/static/bundles/main.css", timeout=3)
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:500]}"
    )

from __future__ import annotations

from django.test import Client


def test_index_page(client: Client) -> None:
    response = client.get("/")
    assert response.status_code == 200

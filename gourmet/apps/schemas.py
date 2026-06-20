from __future__ import annotations

from ninja import Schema


class MessageOut(Schema):
    detail: str

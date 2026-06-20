from __future__ import annotations

from uuid import UUID

from ninja import Schema


class SearchIn(Schema):
    query: str


class SearchResultOut(Schema):
    video_id: str
    title: str
    artist: str = ""
    thumbnail_url: str = ""
    duration: str = ""


class QueueItemOut(Schema):
    id: UUID
    video_id: str
    title: str
    artist: str
    thumbnail_url: str
    duration: str
    status: str
    sort_order: int
    model_config = {"from_attributes": True}


class QueueItemIn(Schema):
    video_id: str
    title: str
    artist: str = ""
    thumbnail_url: str = ""
    duration: str = ""

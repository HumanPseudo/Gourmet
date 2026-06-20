from __future__ import annotations

import time
import re
import logging
from typing import Any
from uuid import UUID
from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from gourmet.apps.schemas import MessageOut

from .models import JukeboxQueueItem

router = Router(tags=["Jukebox"], auth=None)
logger = logging.getLogger(__name__)

# ── Token cache ────────────────────────────────────────────────────────


class _TokenCache:
    def __init__(self, ttl: int = 300) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._ttl = ttl

    def get(self) -> str | None:
        if time.monotonic() >= self._expires_at:
            self._token = None
        return self._token

    def set(self, token: str) -> None:
        self._token = token
        self._expires_at = time.monotonic() + self._ttl

    def clear(self) -> None:
        self._token = None
        self._expires_at = 0.0


_token_cache = _TokenCache()


# ── Schemas ────────────────────────────────────────────────────────────


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


class QueueItemIn(Schema):
    video_id: str
    title: str
    artist: str = ""
    thumbnail_url: str = ""
    duration: str = ""


# ── Helpers ────────────────────────────────────────────────────────────


def proxy_request(method: str, path: str, json: Any = None) -> tuple[int, Any]:
    url = f"{settings.PEAR_API_URL.rstrip('/')}/{path.lstrip('/')}"
    headers: dict[str, str] = {}
    token = _token_cache.get()

    if token is None:
        try:
            token = _fetch_api_server_token()
            _token_cache.set(token)
        except requests.exceptions.RequestException as e:
            return 503, {"detail": f"Pear API auth failed: {e!s}"}

    headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(method, url, json=json, headers=headers, timeout=5)
        if response.status_code == 401:
            _token_cache.clear()
            try:
                token = _fetch_api_server_token()
                _token_cache.set(token)
            except requests.exceptions.RequestException as e:
                return 503, {"detail": f"Pear API reauth failed: {e!s}"}
            headers["Authorization"] = f"Bearer {token}"
            response = requests.request(
                method, url, json=json, headers=headers, timeout=5
            )
        if response.status_code == 204:
            return 204, None
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, {"detail": response.text}
    except requests.exceptions.RequestException as e:
        return 503, {"detail": f"Pear API unreachable: {e!s}"}


def _api_server_root_url() -> str:
    api_url = settings.PEAR_API_URL.rstrip("/")
    parts = urlsplit(api_url)
    path = parts.path
    if "/api/" in path:
        path = path.split("/api/", 1)[0]
    return urlunsplit((parts.scheme, parts.netloc, path.rstrip("/"), "", ""))


def _fetch_api_server_token() -> str:
    auth_url = f"{_api_server_root_url()}/auth/{settings.PROJECT_NAME}"
    response = requests.post(auth_url, timeout=5)
    if response.status_code != 200:
        msg = response.text.strip() or "Unable to authorize with Pear API Server"
        raise requests.exceptions.RequestException(msg)

    try:
        data = response.json()
    except ValueError as exc:
        raise requests.exceptions.RequestException(
            "Pear API Server returned invalid auth payload"
        ) from exc

    token = data.get("accessToken")
    if not isinstance(token, str) or not token:
        raise requests.exceptions.RequestException(
            "Pear API Server did not return an access token"
        )
    return token


def item_to_out(item: JukeboxQueueItem) -> QueueItemOut:
    return QueueItemOut(
        id=item.id,
        video_id=item.video_id,
        title=item.title,
        artist=item.artist,
        thumbnail_url=item.thumbnail_url,
        duration=item.duration,
        status=item.status,
        sort_order=item.sort_order,
    )


def create_queue_item(
    payload: QueueItemIn,
    *,
    status: str = JukeboxQueueItem.STATUS_QUEUED,
) -> JukeboxQueueItem:
    with transaction.atomic():
        max_order = JukeboxQueueItem.objects.select_for_update().aggregate(
            Max("sort_order")
        )["sort_order__max"]
        next_order = (max_order + 1) if max_order is not None else 0

        return JukeboxQueueItem.objects.create(
            video_id=payload.video_id,
            title=payload.title,
            artist=payload.artist,
            thumbnail_url=payload.thumbnail_url,
            duration=payload.duration,
            status=status,
            sort_order=next_order,
        )


def active_queue_items() -> list[JukeboxQueueItem]:
    return list(
        JukeboxQueueItem.objects.filter(
            status__in=(
                JukeboxQueueItem.STATUS_QUEUED,
                JukeboxQueueItem.STATUS_PLAYING,
            )
        )
    )


def ordered_queue_items() -> list[JukeboxQueueItem]:
    return list(JukeboxQueueItem.objects.all())


def sync_queue_to_player() -> tuple[int, dict[str, str] | None]:
    status, data = proxy_request("DELETE", "queue")
    if status != 204:
        return status, data

    for item in active_queue_items():
        status, data = proxy_request("POST", "queue", json={"videoId": item.video_id})
        if status != 204:
            return status, data

    return 204, None


def best_effort_sync_queue_to_player() -> None:
    status, data = sync_queue_to_player()
    if status != 204:
        logger.warning("Queue sync failed: %s", data)


def queue_index_for_item(item_id: UUID) -> int | None:
    for index, item in enumerate(active_queue_items()):
        if item.id == item_id:
            return index
    return None


def play_queue_index(index: int) -> tuple[int, dict[str, str] | None]:
    status, data = proxy_request("PATCH", "queue", json={"index": index})
    if status != 204:
        return status, data

    status, data = proxy_request("POST", "play")
    if status != 204:
        return status, data

    return 204, None


def sync_and_play_queue_index(index: int) -> tuple[int, dict[str, str] | None]:
    status, data = sync_queue_to_player()
    if status != 204:
        return status, data
    return play_queue_index(index)


def promote_queue_item(item_id: UUID) -> None:
    JukeboxQueueItem.objects.filter(
        status=JukeboxQueueItem.STATUS_PLAYING,
    ).exclude(id=item_id).update(status=JukeboxQueueItem.STATUS_PLAYED)
    JukeboxQueueItem.objects.filter(id=item_id).update(
        status=JukeboxQueueItem.STATUS_PLAYING
    )


def promote_next_queue_item() -> None:
    next_item = (
        JukeboxQueueItem.objects.filter(status=JukeboxQueueItem.STATUS_QUEUED)
        .order_by("sort_order", "created_at")
        .first()
    )
    if next_item is None:
        JukeboxQueueItem.objects.filter(status=JukeboxQueueItem.STATUS_PLAYING).update(
            status=JukeboxQueueItem.STATUS_PLAYED
        )
        return

    promote_queue_item(next_item.id)


def reconcile_queue_with_player() -> tuple[int, list[JukeboxQueueItem] | dict[str, str]]:
    status, data = proxy_request("GET", "song")
    if status != 200 and status != 204:
        return status, data

    if status == 204:
        current_video_id = ""
    elif status == 200 and isinstance(data, dict):
        video_id = _find_first_key(data, ("videoId", "video_id"))
        current_video_id = video_id if isinstance(video_id, str) else ""
    else:
        return 503, {"detail": "Unable to reconcile queue with Pear"}

    playing_item = (
        JukeboxQueueItem.objects.filter(status=JukeboxQueueItem.STATUS_PLAYING)
        .order_by("sort_order", "created_at")
        .first()
    )

    if not current_video_id:
        if playing_item is not None:
            playing_item.status = JukeboxQueueItem.STATUS_PLAYED
            playing_item.save(update_fields=["status"])
        return ordered_queue_items()

    current_item = next(
        (item for item in active_queue_items() if item.video_id == current_video_id),
        None,
    )
    if current_item is None:
        if playing_item is not None:
            playing_item.status = JukeboxQueueItem.STATUS_PLAYED
            playing_item.save(update_fields=["status"])
        return ordered_queue_items()

    if playing_item is None or playing_item.id != current_item.id:
        promote_queue_item(current_item.id)

    return 200, ordered_queue_items()


def _walk_values(data: Any) -> list[Any]:
    values: list[Any] = []

    def walk(value: Any) -> None:
        values.append(value)
        if isinstance(value, dict):
            for nested_value in value.values():
                walk(nested_value)
        elif isinstance(value, list):
            for nested_value in value:
                walk(nested_value)

    walk(data)
    return values


def _find_first_key(data: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(data, dict):
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        for nested_value in data.values():
            found = _find_first_key(nested_value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for nested_value in data:
            found = _find_first_key(nested_value, keys)
            if found not in (None, ""):
                return found
    return None


def _render_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("simpleText", "text", "name", "title"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
        runs = value.get("runs")
        if isinstance(runs, list):
            parts = []
            for run in runs:
                if isinstance(run, dict):
                    text = run.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return " ".join(parts).strip()
    if isinstance(value, list):
        parts = [_render_text(item) for item in value]
        parts = [part for part in parts if part]
        if parts:
            return " ".join(parts).strip()
    return ""


def _extract_video_id(data: dict[str, Any]) -> str:
    value = _find_first_key(
        data,
        (
            "videoId",
            "video_id",
        ),
    )
    return str(value) if isinstance(value, str) else ""


def _extract_title(data: dict[str, Any]) -> str:
    title = data.get("title")
    rendered = _render_text(title)
    if rendered:
        return rendered

    flex_columns = data.get("flexColumns")
    if isinstance(flex_columns, list):
        for column in flex_columns:
            if not isinstance(column, dict):
                continue
            column_renderer = column.get("musicResponsiveListItemFlexColumnRenderer")
            if isinstance(column_renderer, dict):
                rendered = _render_text(column_renderer.get("text"))
                if rendered:
                    return rendered
    return ""


def _extract_thumbnail_url(data: dict[str, Any]) -> str:
    thumbnail = _find_first_key(data, ("thumbnail",))
    if isinstance(thumbnail, dict):
        thumbnails = thumbnail.get("thumbnails")
        if isinstance(thumbnails, list):
            for item in thumbnails:
                if isinstance(item, dict):
                    url = item.get("url")
                    if isinstance(url, str) and url:
                        return url
        nested_thumbnails = _find_first_key(thumbnail, ("thumbnails",))
        if isinstance(nested_thumbnails, list):
            for item in nested_thumbnails:
                if isinstance(item, dict):
                    url = item.get("url")
                    if isinstance(url, str) and url:
                        return url
    if isinstance(thumbnail, list):
        for item in thumbnail:
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url:
                    return url
    thumbnail_url = _find_first_key(data, ("thumbnailUrl", "thumbnail_url"))
    return str(thumbnail_url) if isinstance(thumbnail_url, str) else ""


def _extract_duration(data: dict[str, Any]) -> str:
    value = _find_first_key(data, ("lengthText", "durationText", "duration"))
    rendered = _render_text(value)
    if rendered:
        return rendered

    subtitle = _find_first_key(data, ("subtitle",))
    subtitle_label = _find_first_key(
        subtitle,
        ("label",),
    )
    rendered_label = _render_text(subtitle_label)
    if rendered_label:
        match = re.search(
            r"(?P<minutes>\d+)\s+minutes?,\s*(?P<seconds>\d+)\s+seconds?",
            rendered_label,
            re.IGNORECASE,
        )
        if match:
            minutes = int(match.group("minutes"))
            seconds = int(match.group("seconds"))
            return f"{minutes}:{seconds:02d}"

    subtitle_text = _render_text(subtitle)
    if subtitle_text:
        for token in subtitle_text.replace("•", " ").split():
            if re.fullmatch(r"\d+:\d{2}(?::\d{2})?", token.strip()):
                return token.strip()

    for candidate in _walk_values(subtitle if subtitle is not None else data):
        if isinstance(candidate, str) and re.fullmatch(r"\d+:\d{2}(?::\d{2})?", candidate.strip()):
            return candidate.strip()
    return ""


def _extract_artist(data: dict[str, Any]) -> str:
    short_byline = _find_first_key(data, ("shortBylineText", "author", "artist", "uploader"))
    rendered = _render_text(short_byline)
    if rendered:
        return rendered

    subtitle = data.get("subtitle")
    subtitle_label = _find_first_key(
        subtitle,
        ("label",),
    )
    rendered_label = _render_text(subtitle_label)
    if rendered_label:
        parts = [part.strip() for part in rendered_label.split("•") if part.strip()]
        if len(parts) >= 2:
            return parts[1]

    subtitle_text = _render_text(subtitle)
    if subtitle_text:
        parts = [part.strip() for part in subtitle_text.split("•") if part.strip()]
        filtered_parts = []
        for part in parts:
            if re.search(r"\bviews?\b", part, re.IGNORECASE):
                continue
            if re.fullmatch(r"\d+:\d{2}(?::\d{2})?", part):
                continue
            if part in {"Video", "Song"}:
                continue
            filtered_parts.append(part)
        if filtered_parts:
            if len(filtered_parts) >= 2 and filtered_parts[0] in {"Video", "Song"}:
                return filtered_parts[1]
            if len(filtered_parts) >= 2:
                return filtered_parts[0]
            return filtered_parts[0]

    return ""


def search_item_to_out(item: dict[str, Any]) -> SearchResultOut | None:
    video_id = _extract_video_id(item)
    title = _extract_title(item)
    if not video_id or not title:
        return None

    return SearchResultOut(
        video_id=video_id,
        title=title,
        artist=_extract_artist(item),
        thumbnail_url=_extract_thumbnail_url(item),
        duration=_extract_duration(item),
    )


def filter_search_results(data: Any) -> list[SearchResultOut]:
    results: list[SearchResultOut] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key in (
                "musicCardShelfRenderer",
                "musicResponsiveListItemRenderer",
                "videoRenderer",
            ):
                renderer = value.get(key)
                if isinstance(renderer, dict):
                    candidate = search_item_to_out(renderer)
                    if candidate is not None:
                        results.append(candidate)
                    return
            for nested_value in value.values():
                walk(nested_value)
        elif isinstance(value, list):
            for nested_value in value:
                walk(nested_value)

    walk(data)
    return results


# ── Pear Proxy Endpoints ───────────────────────────────────────────────


@router.post(
    "/player/play",
    summary="Resume playback in Pear",
    response={204: None, 401: MessageOut, 503: MessageOut},
)
def play(request: HttpRequest) -> Any:
    status, data = proxy_request("POST", "play")
    return status, data


@router.post(
    "/player/pause",
    summary="Pause playback in Pear",
    response={204: None, 401: MessageOut, 503: MessageOut},
)
def pause(request: HttpRequest) -> Any:
    status, data = proxy_request("POST", "pause")
    return status, data


@router.get(
    "/player/song",
    summary="Get current Pear song info",
    response={200: Any, 204: None, 401: MessageOut, 503: MessageOut},
)
def song_info(request: HttpRequest) -> Any:
    status, data = proxy_request("GET", "song")
    return status, data


@router.post(
    "/player/search",
    summary="Search for a song in Pear",
    response={200: list[SearchResultOut], 401: MessageOut, 503: MessageOut},
)
def search(request: HttpRequest, payload: SearchIn) -> list[SearchResultOut] | tuple[int, dict[str, str]]:
    status, data = proxy_request("POST", "search", json={"query": payload.query})
    if status != 200:
        return status, data
    return filter_search_results(data)


# ── Custom Queue Endpoints ─────────────────────────────────────────────


@router.get("/queue", response=list[QueueItemOut], summary="List custom queue")
def list_custom_queue(request: HttpRequest) -> list[QueueItemOut]:
    return [item_to_out(i) for i in JukeboxQueueItem.objects.all()]


@router.post(
    "/queue",
    response={201: QueueItemOut},
    summary="Add to custom queue",
)
def add_to_custom_queue(request: HttpRequest, payload: QueueItemIn) -> tuple[int, QueueItemOut]:
    item = create_queue_item(payload)
    best_effort_sync_queue_to_player()
    return 201, item_to_out(item)


@router.post(
    "/queue/play",
    response={201: QueueItemOut, 503: MessageOut},
    summary="Add to queue and play",
)
def add_to_custom_queue_and_play(
    request: HttpRequest, payload: QueueItemIn
) -> tuple[int, QueueItemOut] | tuple[int, dict[str, str]]:
    item = create_queue_item(payload, status=JukeboxQueueItem.STATUS_PLAYING)
    promote_queue_item(item.id)
    index = queue_index_for_item(item.id)
    if index is None:
        return 503, {"detail": "Item not found in synced queue"}

    status, data = sync_and_play_queue_index(index)
    if status != 204:
        return status, data
    return 201, item_to_out(item)


@router.post(
    "/queue/sync",
    response={204: None, 503: MessageOut},
    summary="Sync local queue to player",
)
def sync_custom_queue(request: HttpRequest) -> tuple[int, Any]:
    return sync_queue_to_player()


@router.post(
    "/queue/reconcile",
    response={200: list[QueueItemOut], 503: MessageOut},
    summary="Reconcile local queue with player",
)
def reconcile_custom_queue(request: HttpRequest) -> tuple[int, list[QueueItemOut] | dict[str, str] | None]:
    status, data = reconcile_queue_with_player()
    if status != 200:
        return status, data  # type: ignore[return-value]
    return 200, [item_to_out(item) for item in data]  # type: ignore[arg-type]


@router.post(
    "/queue/clear",
    response={200: MessageOut},
    summary="Clear custom queue",
)
def clear_custom_queue(request: HttpRequest) -> tuple[int, MessageOut]:
    JukeboxQueueItem.objects.all().delete()
    best_effort_sync_queue_to_player()
    return 200, MessageOut(detail="Queue cleared")


@router.delete(
    "/queue/{item_id}",
    response={200: MessageOut},
    summary="Remove from custom queue",
)
def remove_from_custom_queue(request: HttpRequest, item_id: UUID) -> tuple[int, MessageOut]:
    item = get_object_or_404(JukeboxQueueItem, id=item_id)
    was_playing = item.status == JukeboxQueueItem.STATUS_PLAYING
    item.delete()
    if was_playing:
        promote_next_queue_item()
    best_effort_sync_queue_to_player()
    return 200, MessageOut(detail="Item removed from queue")


@router.post("/queue/{item_id}/push", response={204: None, 503: MessageOut}, summary="Push item to Pear")
def push_to_pear(request: HttpRequest, item_id: UUID) -> tuple[int, dict[str, str] | None]:
    """
    Syncs the queue and starts playback from the selected item.
    """
    item = get_object_or_404(JukeboxQueueItem, id=item_id)
    promote_queue_item(item.id)
    status, data = sync_queue_to_player()
    if status != 204:
        return status, data

    index = queue_index_for_item(item.id)
    if index is None:
        return 503, {"detail": "Item not found in synced queue"}
    return play_queue_index(index)

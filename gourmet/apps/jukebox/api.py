from __future__ import annotations

from typing import Any
from uuid import UUID

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router

from gourmet.apps.schemas import MessageOut

from .models import JukeboxQueueItem
from .schemas import QueueItemIn, QueueItemOut, SearchIn, SearchResultOut
from .services import JukeboxService

router = Router(tags=["Jukebox"], auth=None)


# ── Pear Proxy Endpoints ───────────────────────────────────────────────


@router.post(
    "/player/play",
    summary="Resume playback in Pear",
    response={204: None, 401: MessageOut, 503: MessageOut},
)
def play(request: HttpRequest) -> Any:
    return JukeboxService.proxy_request("POST", "play")


@router.post(
    "/player/pause",
    summary="Pause playback in Pear",
    response={204: None, 401: MessageOut, 503: MessageOut},
)
def pause(request: HttpRequest) -> Any:
    return JukeboxService.proxy_request("POST", "pause")


@router.get(
    "/player/song",
    summary="Get current Pear song info",
    response={200: Any, 204: None, 401: MessageOut, 503: MessageOut},
)
def song_info(request: HttpRequest) -> Any:
    return JukeboxService.proxy_request("GET", "song")


@router.post(
    "/player/search",
    summary="Search for a song in Pear",
    response={200: list[SearchResultOut], 401: MessageOut, 503: MessageOut},
)
def search(
    request: HttpRequest, payload: SearchIn
) -> list[SearchResultOut] | tuple[int, dict[str, str]]:
    status, data = JukeboxService.proxy_request(
        "POST", "search", json={"query": payload.query}
    )
    if status != 200:
        return status, data
    return JukeboxService.filter_search_results(data)


# ── Custom Queue Endpoints ─────────────────────────────────────────────


@router.get(
    "/queue", response=list[QueueItemOut], summary="List custom queue"
)
def list_custom_queue(request: HttpRequest) -> Any:
    return JukeboxService.ordered_queue_items()


@router.post(
    "/queue",
    response={201: QueueItemOut},
    summary="Add to custom queue",
)
def add_to_custom_queue(
    request: HttpRequest, payload: QueueItemIn
) -> tuple[int, QueueItemOut]:
    item = JukeboxService.create_queue_item(payload)
    JukeboxService.best_effort_sync_queue_to_player()
    return 201, QueueItemOut.model_validate(item)


@router.post(
    "/queue/play",
    response={201: QueueItemOut, 503: MessageOut},
    summary="Add to queue and play",
)
def add_to_custom_queue_and_play(
    request: HttpRequest, payload: QueueItemIn
) -> tuple[int, QueueItemOut] | tuple[int, dict[str, str]]:
    item = JukeboxService.create_queue_item(
        payload, status=JukeboxQueueItem.STATUS_PLAYING
    )
    JukeboxService.promote_queue_item(item.id)
    index = JukeboxService.queue_index_for_item(item.id)
    if index is None:
        return 503, {"detail": "Item not found in synced queue"}

    status, data = JukeboxService.sync_and_play_queue_index(index)
    if status != 204:
        return status, data  # type: ignore[return-value]
    return 201, QueueItemOut.model_validate(item)


@router.post(
    "/queue/sync",
    response={204: None, 503: MessageOut},
    summary="Sync local queue to player",
)
def sync_custom_queue(request: HttpRequest) -> tuple[int, Any]:
    return JukeboxService.sync_queue_to_player()


@router.post(
    "/queue/reconcile",
    response={200: list[QueueItemOut], 503: MessageOut},
    summary="Reconcile local queue with player",
)
def reconcile_custom_queue(
    request: HttpRequest,
) -> tuple[int, list[QueueItemOut] | dict[str, str]]:
    status, data = JukeboxService.reconcile_queue_with_player()
    if status != 200:
        return status, data  # type: ignore[return-value]
    return 200, [QueueItemOut.model_validate(item) for item in data]


@router.post(
    "/queue/clear",
    response={200: MessageOut},
    summary="Clear custom queue",
)
def clear_custom_queue(
    request: HttpRequest,
) -> tuple[int, MessageOut]:
    JukeboxService.clear_queue()
    JukeboxService.best_effort_sync_queue_to_player()
    return 200, MessageOut(detail="Queue cleared")


@router.delete(
    "/queue/{item_id}",
    response={200: MessageOut},
    summary="Remove from custom queue",
)
def remove_from_custom_queue(
    request: HttpRequest, item_id: UUID
) -> tuple[int, MessageOut]:
    JukeboxService.remove_queue_item(item_id)
    return 200, MessageOut(detail="Item removed from queue")


@router.post(
    "/queue/{item_id}/push",
    response={204: None, 503: MessageOut},
    summary="Push item to Pear",
)
def push_to_pear(
    request: HttpRequest, item_id: UUID
) -> tuple[int, dict[str, str] | None]:
    item = get_object_or_404(JukeboxQueueItem, id=item_id)
    JukeboxService.promote_queue_item(item.id)
    status, data = JukeboxService.sync_queue_to_player()
    if status != 204:
        return status, data

    index = JukeboxService.queue_index_for_item(item.id)
    if index is None:
        return 503, {"detail": "Item not found in synced queue"}
    return JukeboxService.play_queue_index(index)

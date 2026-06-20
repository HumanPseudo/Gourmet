from __future__ import annotations

import logging

from ninja import NinjaAPI
from ninja.errors import HttpError

logger = logging.getLogger(__name__)


def register_exception_handlers(api: NinjaAPI) -> None:
    @api.exception_handler(Exception)
    def handle_all_errors(request, exc: Exception):
        if isinstance(exc, HttpError):
            return api.create_response(
                request,
                {"detail": exc.message},
                status=exc.status_code,
            )

        logger.exception("Unhandled API exception: %s", exc)
        return api.create_response(
            request,
            {"detail": "Internal server error"},
            status=500,
        )

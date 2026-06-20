from __future__ import annotations

import uuid
from typing import Any

from django.db import models


class JukeboxQueueItem(models.Model):
    """
    Model representing a song in the custom Jukebox queue.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PLAYING = "playing", "Playing"
        PLAYED = "played", "Played"

    STATUS_QUEUED = Status.QUEUED
    STATUS_PLAYING = Status.PLAYING
    STATUS_PLAYED = Status.PLAYED
    STATUS_CHOICES = Status.choices

    id: models.UUIDField[uuid.UUID, uuid.UUID] = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    video_id: models.CharField[str, str] = models.CharField(
        max_length=50, verbose_name="Video ID"
    )
    title: models.CharField[str, str] = models.CharField(
        max_length=255, verbose_name="Title"
    )
    artist: models.CharField[str, str] = models.CharField(
        max_length=255, blank=True, verbose_name="Artist"
    )
    thumbnail_url: models.URLField[str, str] = models.URLField(
        blank=True, verbose_name="Thumbnail URL"
    )
    duration: models.CharField[str, str] = models.CharField(
        max_length=20, blank=True, verbose_name="Duration"
    )
    status: models.CharField[str, str] = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
        db_index=True,
        verbose_name="Status",
    )
    sort_order: models.PositiveIntegerField[int, int] = models.PositiveIntegerField(
        default=0, db_index=True, verbose_name="Sort Order"
    )
    created_at: models.DateTimeField[Any, Any] = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Jukebox Queue Item"
        verbose_name_plural = "Jukebox Queue Items"
        ordering = ["sort_order", "created_at"]

    def __str__(self) -> str:
        return f"{self.title} - {self.artist} ({self.status})"

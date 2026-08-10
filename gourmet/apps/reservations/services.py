from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Reservation


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = timezone.make_aware(datetime.combine(day, time.max))
    return start, end


class ReservationService:
    @staticmethod
    def list_for_date(day: date) -> QuerySet[Reservation]:
        start, end = _day_bounds(day)
        return (
            Reservation.objects.filter(reserved_for__range=(start, end))
            .select_related("table")
            .order_by("reserved_for")
        )

    @staticmethod
    def counts_by_day(start: date, end: date) -> dict[date, int]:
        start_dt, _ = _day_bounds(start)
        _, end_dt = _day_bounds(end)
        counts: dict[date, int] = {}
        reserved_dates = (
            Reservation.objects.filter(reserved_for__range=(start_dt, end_dt))
            .exclude(status=Reservation.Status.CANCELLED)
            .values_list("reserved_for", flat=True)
        )
        for reserved_for in reserved_dates:
            day = timezone.localtime(reserved_for).date()
            counts[day] = counts.get(day, 0) + 1
        return counts

    @staticmethod
    def get(reservation_id: UUID) -> Reservation:
        return get_object_or_404(
            Reservation.objects.select_related("table"), pk=reservation_id
        )

    @staticmethod
    def create(
        *,
        customer_name: str,
        customer_phone: str,
        party_size: int,
        reserved_for: datetime,
        table_id: UUID | None,
        notes: str,
    ) -> Reservation:
        return Reservation.objects.create(
            customer_name=customer_name,
            customer_phone=customer_phone,
            party_size=party_size,
            reserved_for=reserved_for,
            table_id=table_id,
            notes=notes,
        )

    @staticmethod
    def update(
        reservation: Reservation,
        *,
        customer_name: str,
        customer_phone: str,
        party_size: int,
        reserved_for: datetime,
        table_id: UUID | None,
        notes: str,
    ) -> Reservation:
        reservation.customer_name = customer_name
        reservation.customer_phone = customer_phone
        reservation.party_size = party_size
        reservation.reserved_for = reserved_for
        reservation.table_id = table_id
        reservation.notes = notes
        reservation.save()
        return reservation

    @staticmethod
    def cancel(reservation: Reservation) -> Reservation:
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status", "updated_at"])
        return reservation

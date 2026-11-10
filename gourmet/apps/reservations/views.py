from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from gourmet.apps.accounts.auth import role_required
from gourmet.apps.tables.models import Table

from .models import Reservation
from .services import ReservationService


def _redirect_to_date(selected_date: date):
    return redirect(f"{reverse('reservation_list')}?date={selected_date.isoformat()}")


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(value)
    except ValueError:
        return default


def _parse_reserved_for(request) -> datetime | None:
    day = request.POST.get("date", "")
    hour = request.POST.get("time", "")
    try:
        parsed_time = datetime.strptime(hour, "%H:%M").time()
        naive = datetime.combine(date.fromisoformat(day), parsed_time)
    except ValueError:
        return None
    return timezone.make_aware(naive)


@role_required("waiter", "admin")
def reservation_calendar(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        first_day = date(year, month, 1)
    except (ValueError, TypeError):
        year, month = today.year, today.month
        first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)
    counts = ReservationService.counts_by_day(first_day, last_day)

    def _cell(day: date) -> tuple[date, int | None]:
        return (day, counts.get(day, 0)) if day.month == month else (day, None)

    cal = calendar.Calendar(firstweekday=0)
    weeks = [
        [_cell(day) for day in week]
        for week in cal.monthdatescalendar(year, month)
    ]

    prev_month = (first_day.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (last_day + timedelta(days=1)).replace(day=1)

    return render(
        request,
        "pos/reservation_calendar.html",
        {
            "weeks": weeks,
            "month_name": first_day.strftime("%B %Y"),
            "today": today,
            "prev_year": prev_month.year,
            "prev_month": prev_month.month,
            "next_year": next_month.year,
            "next_month": next_month.month,
        },
    )


@role_required("waiter", "admin")
def reservation_list(request):
    today = timezone.localdate()
    selected_date = _parse_date(request.GET.get("date"), today)

    if request.method == "POST":
        action = request.POST.get("action")
        reserved_for = _parse_reserved_for(request)
        if action == "create":
            if not reserved_for:
                messages.error(request, "Fecha y hora inválidas")
            else:
                r = ReservationService.create(
                    customer_name=request.POST.get("customer_name", "").strip(),
                    customer_phone=request.POST.get("customer_phone", "").strip(),
                    party_size=int(request.POST.get("party_size", 2)),
                    reserved_for=reserved_for,
                    table_id=request.POST.get("table_id") or None,
                    notes=request.POST.get("notes", "").strip(),
                )
                messages.success(
                    request, f"Reserva creada para {r.customer_name}"
                )
                selected_date = timezone.localtime(reserved_for).date()
        elif action == "edit":
            reservation = get_object_or_404(
                Reservation, pk=request.POST.get("reservation_id")
            )
            if not reserved_for:
                messages.error(request, "Fecha y hora inválidas")
            else:
                ReservationService.update(
                    reservation,
                    customer_name=request.POST.get("customer_name", "").strip(),
                    customer_phone=request.POST.get("customer_phone", "").strip(),
                    party_size=int(request.POST.get("party_size", 2)),
                    reserved_for=reserved_for,
                    table_id=request.POST.get("table_id") or None,
                    notes=request.POST.get("notes", "").strip(),
                )
                messages.success(request, "Reserva actualizada")
                selected_date = timezone.localtime(reserved_for).date()
        return _redirect_to_date(selected_date)

    reservations = ReservationService.list_for_date(selected_date)
    tables = Table.objects.filter(is_active=True).order_by("code")
    return render(
        request,
        "pos/reservation_list.html",
        {
            "reservations": reservations,
            "tables": tables,
            "selected_date": selected_date,
            "prev_date": selected_date - timedelta(days=1),
            "next_date": selected_date + timedelta(days=1),
        },
    )


@role_required("waiter", "admin")
@require_POST
def reservation_cancel(request, reservation_id):
    reservation = ReservationService.get(reservation_id)
    ReservationService.cancel(reservation)
    messages.success(request, "Reserva cancelada")
    selected_date = timezone.localtime(reservation.reserved_for).date()
    return _redirect_to_date(selected_date)

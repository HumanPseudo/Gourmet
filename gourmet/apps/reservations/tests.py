from __future__ import annotations

from datetime import date, datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from gourmet.apps.accounts.models import User
from gourmet.apps.tables.models import Table

from .models import Reservation
from .services import ReservationService


class ReservationServiceTests(TestCase):
    def setUp(self) -> None:
        self.table = Table.objects.create(code="R1", capacity=4)

    def test_create_and_get(self) -> None:
        reserved_for = timezone.make_aware(datetime(2026, 8, 15, 19, 30))
        reservation = ReservationService.create(
            customer_name="Ana",
            customer_phone="3001234567",
            party_size=4,
            reserved_for=reserved_for,
            table_id=self.table.pk,
            notes="Cumpleaños",
        )
        fetched = ReservationService.get(reservation.pk)
        self.assertEqual(fetched.customer_name, "Ana")
        self.assertEqual(fetched.status, Reservation.Status.CONFIRMED)
        self.assertEqual(fetched.table, self.table)

    def test_list_for_date_only_returns_that_day(self) -> None:
        ReservationService.create(
            customer_name="Día 1",
            customer_phone="",
            party_size=2,
            reserved_for=timezone.make_aware(datetime(2026, 8, 15, 12, 0)),
            table_id=None,
            notes="",
        )
        ReservationService.create(
            customer_name="Día 2",
            customer_phone="",
            party_size=2,
            reserved_for=timezone.make_aware(datetime(2026, 8, 16, 12, 0)),
            table_id=None,
            notes="",
        )
        results = ReservationService.list_for_date(date(2026, 8, 15))
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().customer_name, "Día 1")  # type: ignore[union-attr]

    def test_counts_by_day_excludes_cancelled(self) -> None:
        r1 = ReservationService.create(
            customer_name="A",
            customer_phone="",
            party_size=2,
            reserved_for=timezone.make_aware(datetime(2026, 8, 15, 12, 0)),
            table_id=None,
            notes="",
        )
        ReservationService.create(
            customer_name="B",
            customer_phone="",
            party_size=2,
            reserved_for=timezone.make_aware(datetime(2026, 8, 15, 13, 0)),
            table_id=None,
            notes="",
        )
        ReservationService.cancel(r1)
        counts = ReservationService.counts_by_day(date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(counts.get(date(2026, 8, 15)), 1)

    def test_update(self) -> None:
        reservation = ReservationService.create(
            customer_name="Ana",
            customer_phone="",
            party_size=2,
            reserved_for=timezone.make_aware(datetime(2026, 8, 15, 19, 0)),
            table_id=None,
            notes="",
        )
        updated = ReservationService.update(
            reservation,
            customer_name="Ana María",
            customer_phone="3000000000",
            party_size=5,
            reserved_for=timezone.make_aware(datetime(2026, 8, 16, 20, 0)),
            table_id=self.table.pk,
            notes="Mesa junto a la ventana",
        )
        self.assertEqual(updated.customer_name, "Ana María")
        self.assertEqual(updated.party_size, 5)
        self.assertEqual(updated.table, self.table)

    def test_cancel(self) -> None:
        reservation = ReservationService.create(
            customer_name="Ana",
            customer_phone="",
            party_size=2,
            reserved_for=timezone.make_aware(datetime(2026, 8, 15, 19, 0)),
            table_id=None,
            notes="",
        )
        cancelled = ReservationService.cancel(reservation)
        self.assertEqual(cancelled.status, Reservation.Status.CANCELLED)


class ReservationViewTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="reservations-admin@test.com",
            password="admin1234",
            name="Admin",
        )
        self.client.force_login(self.admin)
        self.table = Table.objects.create(code="R2", capacity=4)

    def test_calendar_view(self) -> None:
        response = self.client.get(
            reverse("reservation_calendar") + "?year=2026&month=8"
        )
        assert response.status_code == 200

    def test_list_view_default_today(self) -> None:
        response = self.client.get(reverse("reservation_list"))
        assert response.status_code == 200

    def test_create_reservation(self) -> None:
        response = self.client.post(
            reverse("reservation_list"),
            {
                "action": "create",
                "customer_name": "Carlos",
                "customer_phone": "3009999999",
                "party_size": 3,
                "date": "2026-08-20",
                "time": "20:00",
                "table_id": str(self.table.pk),
                "notes": "",
            },
        )
        assert response.status_code == 302
        assert Reservation.objects.filter(customer_name="Carlos").exists()

    def test_create_reservation_invalid_datetime(self) -> None:
        response = self.client.post(
            reverse("reservation_list"),
            {
                "action": "create",
                "customer_name": "Carlos",
                "customer_phone": "",
                "party_size": 2,
                "date": "not-a-date",
                "time": "20:00",
                "table_id": "",
                "notes": "",
            },
        )
        assert response.status_code == 302
        assert not Reservation.objects.filter(customer_name="Carlos").exists()

    def test_edit_reservation(self) -> None:
        reservation = ReservationService.create(
            customer_name="Carlos",
            customer_phone="",
            party_size=2,
            reserved_for=timezone.make_aware(datetime(2026, 8, 20, 20, 0)),
            table_id=None,
            notes="",
        )
        response = self.client.post(
            reverse("reservation_list"),
            {
                "action": "edit",
                "reservation_id": str(reservation.pk),
                "customer_name": "Carlos Actualizado",
                "customer_phone": "",
                "party_size": 4,
                "date": "2026-08-20",
                "time": "21:00",
                "table_id": str(self.table.pk),
                "notes": "",
            },
        )
        assert response.status_code == 302
        reservation.refresh_from_db()
        assert reservation.customer_name == "Carlos Actualizado"
        assert reservation.party_size == 4
        assert reservation.table == self.table

    def test_cancel_reservation(self) -> None:
        reservation = ReservationService.create(
            customer_name="Carlos",
            customer_phone="",
            party_size=2,
            reserved_for=timezone.make_aware(datetime(2026, 8, 20, 20, 0)),
            table_id=None,
            notes="",
        )
        response = self.client.post(
            reverse("reservation_cancel", args=[reservation.pk])
        )
        assert response.status_code == 302
        reservation.refresh_from_db()
        assert reservation.status == Reservation.Status.CANCELLED

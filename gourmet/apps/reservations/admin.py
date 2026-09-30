from django.contrib import admin

from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin[Reservation]):
    list_display = (
        "customer_name",
        "reserved_for",
        "party_size",
        "table",
        "status",
    )
    list_filter = ("status",)
    search_fields = ("customer_name", "customer_phone")
    ordering = ("-reserved_for",)

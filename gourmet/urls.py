"""gourmet URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path
from django.views.generic import TemplateView

from gourmet.apps.accounts.api import api
from gourmet.apps.inventory.views import (
    inventory_adjust,
    inventory_delete,
    inventory_list,
    movement_list,
    recipe_list,
    used_today,
)
from gourmet.apps.orders import views as order_views
from gourmet.apps.orders.views import (
    add_payment,
    audit_logs,
    close_order,
    close_report,
    create_order,
    dashboard,
    floor_view,
    kitchen,
    order_detail,
    order_list,
    pos,
    pos_add_items,
    pos_close,
    pos_create_order,
    pos_floor_status,
    pos_order_json,
    pos_pay,
    pos_remove_item,
    pos_set_priority,
    pos_set_table,
    pos_update_item_status,
    print_kitchen,
    print_receipt,
    reopen_order,
    sales_csv,
    split_order,
)
from gourmet.apps.reservations.views import (
    reservation_calendar,
    reservation_cancel,
    reservation_list,
)
from gourmet.apps.tables.views import (
    table_layout_create,
    table_layout_delete,
    table_layout_edit,
    table_layout_list,
    table_layout_save_positions,
)

handler400 = "gourmet.views.bad_request"
handler403 = "gourmet.views.permission_denied"
handler404 = "gourmet.views.not_found"
handler500 = "gourmet.views.server_error"

urlpatterns: list[URLPattern | URLResolver] = [
    path(f"{settings.PROJECT_NAME}-admin/", admin.site.urls),
    path("-/", include("django_alive.urls")),
    path("api/", api.urls),
    path("accounts/", include("gourmet.apps.accounts.urls")),
    path(
        "",
        TemplateView.as_view(
            template_name="index.html",
            extra_context={"project_name": settings.PROJECT_NAME},
        ),
        name="index",
    ),
    path("pos/", pos, name="pos"),
    path("pos/dashboard/", dashboard, name="dashboard"),
    path("pos/create/", pos_create_order, name="pos_create_order"),
    path("pos/add-items/<uuid:order_id>/", pos_add_items, name="pos_add_items"),
    path("pos/pay/<uuid:order_id>/", pos_pay, name="pos_pay"),
    path("pos/close/<uuid:order_id>/", pos_close, name="pos_close"),
    path("pos/floor-status/", pos_floor_status, name="pos_floor_status"),
    path("pos/order-json/<uuid:order_id>/", pos_order_json, name="pos_order_json"),
    path(
        "pos/remove-item/<uuid:order_id>/<uuid:item_id>/",
        pos_remove_item,
        name="pos_remove_item",
    ),
    path("pos/set-table/<uuid:order_id>/", pos_set_table, name="pos_set_table"),
    path("pos/kitchen/", kitchen, name="kitchen"),
    path("pos/orders/", order_list, name="order_list"),
    path("pos/orders/create/", create_order, name="create_order"),
    path("pos/orders/<uuid:order_id>/", order_detail, name="order_detail"),
    path("pos/orders/<uuid:order_id>/pay/", add_payment, name="add_payment"),
    path("pos/orders/<uuid:order_id>/close/", close_order, name="close_order"),
    path("pos/orders/<uuid:order_id>/reopen/", reopen_order, name="reopen_order"),
    path("pos/orders/<uuid:order_id>/split/", split_order, name="split_order"),
    path("pos/orders/<uuid:order_id>/print/", print_receipt, name="print_receipt"),
    path(
        "pos/orders/<uuid:order_id>/print/kitchen/",
        print_kitchen,
        name="print_kitchen",
    ),
    path("pos/inventory/", inventory_list, name="inventory_list"),
    path(
        "pos/inventory/<uuid:item_id>/adjust/",
        inventory_adjust,
        name="inventory_adjust",
    ),
    path(
        "pos/inventory/<uuid:item_id>/delete/",
        inventory_delete,
        name="inventory_delete",
    ),
    path("pos/inventory/movements/", movement_list, name="movement_list"),
    path("pos/inventory/used-today/", used_today, name="used_today"),
    path("pos/inventory/recipes/", recipe_list, name="recipe_list"),
    path("pos/close-report/", close_report, name="close_report"),
    path("pos/reports/sales.csv", sales_csv, name="sales_csv"),
    path("pos/priority/<uuid:item_id>/", pos_set_priority, name="pos_set_priority"),
    path(
        "pos/orders/<uuid:order_id>/items/<uuid:item_id>/status/",
        pos_update_item_status,
        name="pos_update_item_status",
    ),
    path("pos/audit-logs/", audit_logs, name="audit_logs"),
    path(
        "pos/qr/generate/<str:table_code>/",
        order_views.generate_qr_table,
        name="generate_qr_table",
    ),
    path("pos/qr/print/", order_views.print_qr_tables, name="print_qr_tables"),
    path(
        "menu/mesa/<str:table_code>/",
        order_views.menu_public,
        name="menu_public",
    ),
    path(
        "menu/mesa/<str:table_code>/add/",
        order_views.add_to_cart,
        name="add_to_cart",
    ),
    path(
        "menu/mesa/<str:table_code>/remove/",
        order_views.remove_from_cart,
        name="remove_from_cart",
    ),
    path(
        "menu/mesa/<str:table_code>/checkout/",
        order_views.checkout_qr,
        name="checkout_qr",
    ),
    path("pos/reservations/", reservation_list, name="reservation_list"),
    path(
        "pos/reservations/calendar/",
        reservation_calendar,
        name="reservation_calendar",
    ),
    path(
        "pos/reservations/<uuid:reservation_id>/cancel/",
        reservation_cancel,
        name="reservation_cancel",
    ),
    path("pos/floor/", floor_view, name="floor_view"),
    path("pos/floor/layouts/", table_layout_list, name="floor_layout_list"),
    path(
        "pos/floor/layouts/new/", table_layout_create, name="floor_layout_create"
    ),
    path(
        "pos/floor/layouts/<uuid:layout_id>/",
        table_layout_edit,
        name="floor_layout_edit",
    ),
    path(
        "pos/floor/layouts/<uuid:layout_id>/positions/",
        table_layout_save_positions,
        name="floor_layout_save_positions",
    ),
    path(
        "pos/floor/layouts/<uuid:layout_id>/delete/",
        table_layout_delete,
        name="floor_layout_delete",
    ),
]

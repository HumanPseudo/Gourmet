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
from gourmet.apps.inventory.views import inventory_list, movement_list, recipe_list
from gourmet.apps.orders.views import (
    add_payment,
    close_order,
    create_order,
    kitchen,
    order_detail,
    order_list,
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
    path("pos/kitchen/", kitchen, name="kitchen"),
    path("pos/orders/", order_list, name="order_list"),
    path("pos/orders/create/", create_order, name="create_order"),
    path("pos/orders/<uuid:order_id>/", order_detail, name="order_detail"),
    path("pos/orders/<uuid:order_id>/pay/", add_payment, name="add_payment"),
    path("pos/orders/<uuid:order_id>/close/", close_order, name="close_order"),
    path("pos/inventory/", inventory_list, name="inventory_list"),
    path("pos/inventory/movements/", movement_list, name="movement_list"),
    path("pos/inventory/recipes/", recipe_list, name="recipe_list"),
]

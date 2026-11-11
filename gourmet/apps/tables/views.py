from __future__ import annotations

import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from gourmet.apps.accounts.auth import role_required

from .models import Table, TableLayout
from .services import TableLayoutService


@role_required("waiter", "admin")
def table_layout_list(request):
    layouts = TableLayoutService.list()
    for layout in layouts:
        layout.table_count = layout.items.count()  # type: ignore[attr-defined]
    return render(request, "pos/floor/floor_layouts.html", {"layouts": layouts})


@role_required("waiter", "admin")
def table_layout_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        width = int(request.POST.get("width", 800))
        height = int(request.POST.get("height", 600))
        if not name:
            messages.error(request, "El nombre del plano es requerido")
            return render(request, "pos/floor/floor_layout_form.html")
        layout = TableLayoutService.create(name, width, height)
        messages.success(request, f"Plano '{layout.name}' creado")
        return redirect("floor_layout_edit", layout_id=layout.pk)
    return render(request, "pos/floor/floor_layout_form.html")


@role_required("waiter", "admin")
def table_layout_edit(request, layout_id):
    layout = TableLayoutService.get(layout_id)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        width = int(request.POST.get("width", layout.width))
        height = int(request.POST.get("height", layout.height))
        if name:
            TableLayoutService.update(layout, name, width, height)
            messages.success(request, "Plano actualizado")
        return redirect("floor_layout_edit", layout_id=layout.pk)

    items = list(layout.items.select_related("table").all())
    placed_table_ids = {item.table_id for item in items}
    available_tables = Table.objects.filter(is_active=True).exclude(
        pk__in=placed_table_ids
    ).order_by("code")
    return render(
        request,
        "pos/floor/floor_layout_editor.html",
        {
            "layout": layout,
            "items": items,
            "available_tables": available_tables,
            "layout_config": {
                "id": str(layout.pk),
                "width": layout.width,
                "height": layout.height,
            },
            "layout_items_json": [
                {
                    "table_id": str(item.table_id),
                    "code": item.table.code,
                    "capacity": item.table.capacity,
                    "status": item.table.status,
                    "pos_x": item.pos_x,
                    "pos_y": item.pos_y,
                    "shape": item.shape,
                    "rotation": item.rotation,
                }
                for item in items
            ],
            "available_tables_json": [
                {
                    "id": str(t.pk),
                    "code": t.code,
                    "capacity": t.capacity,
                    "status": t.status,
                }
                for t in available_tables
            ],
        },
    )


@role_required("waiter", "admin")
@require_POST
def table_layout_save_positions(request, layout_id):
    layout = TableLayoutService.get(layout_id)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({"error": f"Invalid JSON: {e}"}, status=400)
    items = data.get("items", [])
    try:
        TableLayoutService.save_positions(layout, items)
    except (KeyError, TypeError, ValueError) as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"status": "saved", "count": len(items)})


@role_required("admin")
@require_POST
def table_layout_delete(request, layout_id):
    layout = get_object_or_404(TableLayout, pk=layout_id)
    layout.delete()
    messages.success(request, "Plano eliminado")
    return redirect("floor_layout_list")

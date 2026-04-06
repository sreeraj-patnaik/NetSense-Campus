from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import json

from django.http import JsonResponse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, render

from .aggregation import rebuild_aggregates_for_floor, refresh_cell_aggregates
from .models import CellAggregate, Scan
from .utils import (
    get_floor_dimensions,
    get_floor_plan,
    get_floor_registry,
    get_service_providers,
    interpolate_missing_cells,
    is_blocked_cell,
    ensure_service_provider,
)


def _viewer_context():
    registry = get_floor_registry()
    blocks = registry["blocks"]
    block_floors = registry["block_floors"]
    floor_configs = registry["floor_configs"]

    initial_block = blocks[0] if blocks else ""
    floors = block_floors.get(initial_block, [])
    initial_floor = floors[0] if floors else ""
    initial_cfg = floor_configs.get(f"{initial_block}:{initial_floor}", {})
    default_dims = {
        "rows": max(1, int(initial_cfg.get("rows", settings.HEATMAP_GRID_ROWS))),
        "cols": max(1, int(initial_cfg.get("cols", settings.HEATMAP_GRID_COLS))),
    }

    return {
        "blocks": blocks,
        "floors": floors,
        "initial_block": initial_block,
        "initial_floor": initial_floor,
        "grid_rows": default_dims["rows"],
        "grid_cols": default_dims["cols"],
        "block_floors": block_floors,
        "floor_configs": floor_configs,
        "service_providers": get_service_providers(),
        "modes": Scan.MODE_CHOICES,
    }


def _parse_scan_payload(request):
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST


def _validate_scan_payload(data):
    registry = get_floor_registry()
    block = (data.get("block") or "").strip()
    floor = data.get("floor")
    mode = data.get("mode") or Scan.WIFI
    service_provider = (data.get("service_provider") or "").strip()
    network_name = (data.get("network_name") or "").strip()
    signal_strength = data.get("signal_strength")
    cell_x = data.get("cell_x")
    cell_y = data.get("cell_y")

    try:
        floor = int(floor)
        signal_strength = int(signal_strength)
        cell_x = int(cell_x)
        cell_y = int(cell_y)
    except (TypeError, ValueError):
        return None, "Invalid input. Ensure floor, cell and signal values are numeric."

    if block not in registry["blocks"]:
        return None, "Invalid block."

    if floor not in registry["block_floors"].get(block, []):
        return None, "Invalid floor."

    if mode not in [Scan.WIFI, Scan.MOBILE]:
        return None, "Invalid mode."

    if not service_provider:
        service_provider = "Unknown"

    floor_dims = get_floor_dimensions(block, floor)
    if cell_x < 0 or cell_x >= floor_dims["cols"]:
        return None, "Cell X is out of range."

    if cell_y < 0 or cell_y >= floor_dims["rows"]:
        return None, "Cell Y is out of range."

    if is_blocked_cell(block, floor, cell_x, cell_y):
        return None, "Selected cell is blocked."

    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return None, "Floor plan is not configured."

    return {
        "floor_plan": floor_plan,
        "mode": mode,
        "service_provider": service_provider,
        "network_name": network_name,
        "signal_strength": signal_strength,
        "cell_x": cell_x,
        "cell_y": cell_y,
        "cell_id": (cell_y * floor_dims["cols"] + cell_x),
    }, None


def home_view(request):
    return render(request, "heatmap/landing.html", _viewer_context())


def heatmap_view(request):
    return render(request, "heatmap/home.html", _viewer_context())


def dti_view(request):
    return render(request, "heatmap/dti.html", _viewer_context())


def project_structure_view(request):
    return render(request, "heatmap/project_structure.html", _viewer_context())


def data_models_view(request):
    return render(request, "heatmap/data_models.html", _viewer_context())


def workflow_view(request):
    return render(request, "heatmap/workflow.html", _viewer_context())


@login_required
def scan_view(request):
    context = _viewer_context()
    if request.method == "POST":
        payload, error = _validate_scan_payload(request.POST)
        if error:
            messages.error(request, error)
            return redirect("scan")

        scan = Scan.objects.create(**payload)
        ensure_service_provider(scan.mode, scan.service_provider)
        refresh_cell_aggregates(scan)
        messages.success(request, "Scan saved.")
        return redirect("scan")

    return render(request, "heatmap/scan.html", context)


def heatmap_api(request):
    block = request.GET.get("block")
    floor = request.GET.get("floor")
    mode = request.GET.get("mode", Scan.WIFI)
    service_provider = request.GET.get("service_provider", "").strip()
    interpolate = request.GET.get("interpolate", "1").strip() != "0"

    if not block or not floor:
        return JsonResponse({"error": "block and floor are required query params"}, status=400)

    try:
        floor = int(floor)
    except ValueError:
        return JsonResponse({"error": "floor must be an integer"}, status=400)

    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return JsonResponse({"error": "floor not configured"}, status=404)

    queryset = CellAggregate.objects.filter(floor_plan=floor_plan)
    if mode in [Scan.WIFI, Scan.MOBILE]:
        queryset = queryset.filter(mode=mode)

    if not service_provider or service_provider.lower() == "all":
        queryset = queryset.filter(is_all_providers=True)
    else:
        queryset = queryset.filter(is_all_providers=False, service_provider=service_provider)

    if not queryset.exists():
        rebuild_aggregates_for_floor(floor_plan, mode=mode)
        queryset = CellAggregate.objects.filter(floor_plan=floor_plan)
        if mode in [Scan.WIFI, Scan.MOBILE]:
            queryset = queryset.filter(mode=mode)
        if not service_provider or service_provider.lower() == "all":
            queryset = queryset.filter(is_all_providers=True)
        else:
            queryset = queryset.filter(is_all_providers=False, service_provider=service_provider)

    payload = [
        {
            "cell_x": row.cell_x,
            "cell_y": row.cell_y,
            "signal": round(row.median_signal, 2),
            "count": row.scan_count,
            "interpolated": False,
        }
        for row in queryset.order_by("cell_y", "cell_x")
    ]
    if interpolate:
        floor_cfg = get_floor_registry()["floor_configs"].get(f"{block}:{floor}", {})
        rows = int(floor_cfg.get("rows", floor_plan.grid_rows))
        cols = int(floor_cfg.get("cols", floor_plan.grid_cols))
        blocked_cells = floor_cfg.get("blocked_cells") or []
        points = {(row["cell_x"], row["cell_y"]): (row["signal"], row["count"]) for row in payload}
        payload.extend(
            interpolate_missing_cells(
                points=points,
                rows=rows,
                cols=cols,
                blocked_cells=blocked_cells,
                max_distance=2,
            )
        )

    return JsonResponse(payload, safe=False)


@csrf_exempt
def scan_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = _parse_scan_payload(request)
    payload, error = _validate_scan_payload(data)
    if error:
        return JsonResponse({"error": error}, status=400)

    scan = Scan.objects.create(**payload)
    ensure_service_provider(scan.mode, scan.service_provider)
    refresh_cell_aggregates(scan)
    return JsonResponse(
        {
            "status": "ok",
            "scan_id": scan.id,
            "block": scan.block_code,
            "floor": scan.floor_number,
            "cell_x": scan.cell_x,
            "cell_y": scan.cell_y,
        }
    )


def config_api(request):
    registry = get_floor_registry()
    return JsonResponse(
        {
            "blocks": registry["blocks"],
            "block_floors": registry["block_floors"],
            "floor_configs": registry["floor_configs"],
            "service_providers": get_service_providers(),
        }
    )


def service_worker(_request):
    content = """self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {
  // Online-only app: allow the request to hit the network.
});
"""
    response = HttpResponse(content, content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    return response


def manifest_view(_request):
    content = """{
  "name": "NetSense Campus",
  "short_name": "NetSense",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0b1324",
  "theme_color": "#0b1324",
  "icons": [
    {
      "src": "/static/logo.jpeg",
      "sizes": "192x192",
      "type": "image/jpeg",
      "purpose": "any"
    },
    {
      "src": "/static/logo.jpeg",
      "sizes": "512x512",
      "type": "image/jpeg",
      "purpose": "any"
    }
  ]
}
"""
    response = HttpResponse(content, content_type="application/manifest+json")
    response["Cache-Control"] = "no-cache"
    return response

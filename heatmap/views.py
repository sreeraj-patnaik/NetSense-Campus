from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .models import Scan
from .utils import get_floor_registry, get_service_providers


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


def home_view(request):
    return render(request, "heatmap/home.html", _viewer_context())


@login_required
def scan_view(request):
    context = _viewer_context()
    if request.method == "POST":
        registry = get_floor_registry()
        block = request.POST.get("block", "").strip()
        floor = request.POST.get("floor")
        mode = request.POST.get("mode", Scan.WIFI)
        service_provider = request.POST.get("service_provider", "").strip()
        network_name = request.POST.get("network_name", "").strip()
        signal_strength = request.POST.get("signal_strength")
        cell_x = request.POST.get("cell_x")
        cell_y = request.POST.get("cell_y")

        try:
            floor = int(floor)
            signal_strength = int(signal_strength)
            cell_x = int(cell_x)
            cell_y = int(cell_y)
        except (TypeError, ValueError):
            messages.error(request, "Invalid input. Ensure floor, cell and signal values are numeric.")
            return redirect("scan")

        if block not in registry["blocks"]:
            messages.error(request, "Invalid block.")
            return redirect("scan")

        if floor not in registry["block_floors"].get(block, []):
            messages.error(request, "Invalid floor.")
            return redirect("scan")

        if mode not in [Scan.WIFI, Scan.MOBILE]:
            messages.error(request, "Invalid mode.")
            return redirect("scan")

        provider_choices = get_service_providers().get(mode, [])
        if not service_provider:
            messages.error(request, "Service provider is required.")
            return redirect("scan")
        if provider_choices and service_provider not in provider_choices:
            messages.error(request, "Invalid service provider for selected mode.")
            return redirect("scan")

        floor_cfg = registry["floor_configs"].get(f"{block}:{floor}", {})
        floor_dims = {
            "rows": max(1, int(floor_cfg.get("rows", settings.HEATMAP_GRID_ROWS))),
            "cols": max(1, int(floor_cfg.get("cols", settings.HEATMAP_GRID_COLS))),
        }
        if cell_x < 0 or cell_x >= floor_dims["cols"]:
            messages.error(request, "Cell X is out of range.")
            return redirect("scan")

        if cell_y < 0 or cell_y >= floor_dims["rows"]:
            messages.error(request, "Cell Y is out of range.")
            return redirect("scan")

        Scan.objects.create(
            block=block,
            floor=floor,
            cell_x=cell_x,
            cell_y=cell_y,
            mode=mode,
            service_provider=service_provider,
            network_name=network_name,
            signal_strength=signal_strength,
        )
        messages.success(request, "Scan saved.")
        return redirect("scan")

    return render(request, "heatmap/scan.html", context)


def heatmap_api(request):
    block = request.GET.get("block")
    floor = request.GET.get("floor")
    mode = request.GET.get("mode", Scan.WIFI)
    service_provider = request.GET.get("service_provider", "").strip()

    if not block or not floor:
        return JsonResponse({"error": "block and floor are required query params"}, status=400)

    try:
        floor = int(floor)
    except ValueError:
        return JsonResponse({"error": "floor must be an integer"}, status=400)

    scans = Scan.objects.filter(block=block, floor=floor)
    if mode in [Scan.WIFI, Scan.MOBILE]:
        scans = scans.filter(mode=mode)
    if service_provider and service_provider.lower() != "all":
        scans = scans.filter(service_provider=service_provider)

    points = (
        scans.values("cell_x", "cell_y")
        .annotate(signal=Avg("signal_strength"), count=Count("id"))
        .order_by("cell_y", "cell_x")
    )

    payload = [
        {
            "cell_x": row["cell_x"],
            "cell_y": row["cell_y"],
            "signal": round(row["signal"], 2),
            "count": row["count"],
        }
        for row in points
    ]
    return JsonResponse(payload, safe=False)

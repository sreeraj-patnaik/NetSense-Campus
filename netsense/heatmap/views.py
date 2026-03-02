from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .models import Scan


def _viewer_context():
    return {
        "blocks": settings.HEATMAP_BLOCKS,
        "floors": settings.HEATMAP_FLOORS,
        "grid_rows": settings.HEATMAP_GRID_ROWS,
        "grid_cols": settings.HEATMAP_GRID_COLS,
        "modes": Scan.MODE_CHOICES,
    }


def home_view(request):
    return render(request, "heatmap/home.html", _viewer_context())


@login_required
def scan_view(request):
    context = _viewer_context()
    if request.method == "POST":
        block = request.POST.get("block", "").strip()
        floor = request.POST.get("floor")
        mode = request.POST.get("mode", Scan.WIFI)
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

        if block not in settings.HEATMAP_BLOCKS:
            messages.error(request, "Invalid block.")
            return redirect("scan")

        if floor not in settings.HEATMAP_FLOORS:
            messages.error(request, "Invalid floor.")
            return redirect("scan")

        if mode not in [Scan.WIFI, Scan.MOBILE]:
            messages.error(request, "Invalid mode.")
            return redirect("scan")

        if cell_x < 0 or cell_x >= settings.HEATMAP_GRID_COLS:
            messages.error(request, "Cell X is out of range.")
            return redirect("scan")

        if cell_y < 0 or cell_y >= settings.HEATMAP_GRID_ROWS:
            messages.error(request, "Cell Y is out of range.")
            return redirect("scan")

        Scan.objects.create(
            block=block,
            floor=floor,
            cell_x=cell_x,
            cell_y=cell_y,
            mode=mode,
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

    if not block or not floor:
        return JsonResponse({"error": "block and floor are required query params"}, status=400)

    try:
        floor = int(floor)
    except ValueError:
        return JsonResponse({"error": "floor must be an integer"}, status=400)

    scans = Scan.objects.filter(block=block, floor=floor)
    if mode in [Scan.WIFI, Scan.MOBILE]:
        scans = scans.filter(mode=mode)

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

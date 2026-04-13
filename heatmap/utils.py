from collections import defaultdict
import time

from django.conf import settings

from django.db.utils import OperationalError, ProgrammingError

from .models import Block, FloorPlan, ServiceProvider


def _settings_floor_dims(floor):
    floor_dimensions = getattr(settings, "HEATMAP_FLOOR_DIMENSIONS", {})
    raw_dims = floor_dimensions.get(floor) or floor_dimensions.get(str(floor)) or {}
    rows = int(raw_dims.get("rows", settings.HEATMAP_GRID_ROWS))
    cols = int(raw_dims.get("cols", settings.HEATMAP_GRID_COLS))
    return {"rows": max(1, rows), "cols": max(1, cols)}


def get_floor_registry():
    active_floors = list(
        FloorPlan.objects.select_related("block")
        .filter(is_active=True, block__is_active=True)
        .order_by("block__code", "number")
    )

    block_floors = defaultdict(list)
    floor_configs = {}
    blocks = []

    if active_floors:
        for floor in active_floors:
            block_code = floor.block.code
            if block_code not in blocks:
                blocks.append(block_code)
            block_floors[block_code].append(floor.number)
            floor_configs[f"{block_code}:{floor.number}"] = {
                "rows": max(1, floor.grid_rows),
                "cols": max(1, floor.grid_cols),
                "image_url": floor.image.url if floor.image else "",
                "floor_name": floor.name or f"Floor {floor.number}",
                "blocked_cells": floor.blocked_cell_ids(),
            }
    else:
        fallback_blocks = list(getattr(settings, "HEATMAP_BLOCKS", []))
        fallback_floors = list(getattr(settings, "HEATMAP_FLOORS", []))
        for block_code in fallback_blocks:
            blocks.append(block_code)
            block_floors[block_code] = list(fallback_floors)
            for floor_number in fallback_floors:
                dims = _settings_floor_dims(floor_number)
                blocked_cfg = getattr(settings, "HEATMAP_BLOCKED_CELLS", {})
                blocked_cells = (
                    blocked_cfg.get(f"{block_code}:{floor_number}")
                    or blocked_cfg.get(str(floor_number))
                    or []
                )
                floor_configs[f"{block_code}:{floor_number}"] = {
                    "rows": dims["rows"],
                    "cols": dims["cols"],
                    "image_url": "",
                    "floor_name": f"Floor {floor_number}",
                    "blocked_cells": list(blocked_cells),
                }

    return {
        "blocks": blocks,
        "block_floors": dict(block_floors),
        "floor_configs": floor_configs,
    }


def get_floor_dimensions(block, floor):
    key = f"{block}:{floor}"
    registry = get_floor_registry()
    floor_cfg = registry["floor_configs"].get(key)
    if floor_cfg:
        return {
            "rows": max(1, int(floor_cfg.get("rows", settings.HEATMAP_GRID_ROWS))),
            "cols": max(1, int(floor_cfg.get("cols", settings.HEATMAP_GRID_COLS))),
        }
    return _settings_floor_dims(floor)


def ensure_floor_plan(block_code, floor_number):
    block, _ = Block.objects.get_or_create(code=block_code, defaults={"name": ""})
    floor_plan = FloorPlan.objects.filter(block=block, number=floor_number).first()
    if floor_plan:
        return floor_plan
    dims = get_floor_dimensions(block_code, floor_number)
    blocked_cfg = getattr(settings, "HEATMAP_BLOCKED_CELLS", {})
    blocked_cells = (
        blocked_cfg.get(f"{block_code}:{floor_number}")
        or blocked_cfg.get(str(floor_number))
        or []
    )
    return FloorPlan.objects.create(
        block=block,
        number=floor_number,
        name=f"Floor {floor_number}",
        grid_rows=dims["rows"],
        grid_cols=dims["cols"],
        blocked_cells=list(blocked_cells),
        is_active=True,
    )


def get_floor_plan(block_code, floor_number):
    return (
        FloorPlan.objects.select_related("block")
        .filter(block__code=block_code, number=floor_number, is_active=True, block__is_active=True)
        .first()
    )


def cell_to_id(cell_x, cell_y, cols):
    return int(cell_y) * int(cols) + int(cell_x)


def cell_from_id(cell_id, cols):
    cell_id = int(cell_id)
    cols = int(cols)
    return cell_id % cols, cell_id // cols


def is_blocked_cell(block, floor, cell_x, cell_y):
    registry = get_floor_registry()
    floor_cfg = registry["floor_configs"].get(f"{block}:{floor}", {})
    blocked_cells = set(floor_cfg.get("blocked_cells") or [])
    if not blocked_cells:
        return False
    cols = max(1, int(floor_cfg.get("cols", settings.HEATMAP_GRID_COLS)))
    cell_id = cell_to_id(cell_x, cell_y, cols)
    return cell_id in blocked_cells


def get_service_providers():
    providers = getattr(settings, "HEATMAP_SERVICE_PROVIDERS", {})
    fallback_wifi = list(providers.get("wifi", []))
    fallback_mobile = list(providers.get("mobile", []))

    db_wifi = []
    db_mobile = []
    try:
        for row in ServiceProvider.objects.filter(is_active=True).order_by("mode", "name"):
            if row.mode == ServiceProvider.MOBILE:
                db_mobile.append(row.name)
            else:
                db_wifi.append(row.name)
    except (OperationalError, ProgrammingError):
        return {
            "wifi": fallback_wifi,
            "mobile": fallback_mobile,
        }

    def _unique(values):
        seen = set()
        result = []
        for item in values:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    return {
        "wifi": _unique(db_wifi + fallback_wifi),
        "mobile": _unique(db_mobile + fallback_mobile),
    }


def ensure_service_provider(mode, name):
    cleaned = (name or "").strip() or "Unknown"
    try:
        ServiceProvider.objects.get_or_create(
            mode=mode,
            name=cleaned,
            defaults={"is_active": True},
        )
    except (OperationalError, ProgrammingError):
        return cleaned
    return cleaned


def compute_confidence(scan_count, variance, last_updated):
    count_score = min(1.0, (scan_count or 0) / 10)
    variance_score = 1.0 - min(1.0, (variance or 0) / 100)
    if last_updated:
        age = time.time() - last_updated.timestamp()
        recency_score = max(0.0, 1 - (age / 86400))
    else:
        recency_score = 0.0

    return round(
        0.5 * count_score +
        0.3 * variance_score +
        0.2 * recency_score,
        3,
    )


def score_cell(cell_x, cell_y, points, confidence_map, blocked):
    if (cell_x, cell_y) in blocked:
        return -1

    if (cell_x, cell_y) not in points:
        return 1.0

    confidence = confidence_map.get((cell_x, cell_y), 0)
    return 1 - confidence


def interpolate_missing_cells(*, points, rows, cols, blocked_cells, max_distance=2):
    if not points:
        return []

    blocked = set(int(cell_id) for cell_id in (blocked_cells or []))
    interpolated = []

    for cell_y in range(rows):
        for cell_x in range(cols):
            cell_id = cell_to_id(cell_x, cell_y, cols)
            if cell_id in blocked:
                continue
            if (cell_x, cell_y) in points:
                continue

            neighbors = []
            for dy in range(-max_distance, max_distance + 1):
                for dx in range(-max_distance, max_distance + 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx = cell_x + dx
                    ny = cell_y + dy
                    if nx < 0 or nx >= cols or ny < 0 or ny >= rows:
                        continue
                    neighbor = points.get((nx, ny))
                    if not neighbor:
                        continue
                    distance_sq = dx * dx + dy * dy
                    if distance_sq == 0:
                        continue
                    signal, count = neighbor
                    weight = (1 / distance_sq) * max(1.0, (count or 1) ** 0.5)
                    neighbors.append((signal, weight))

            if not neighbors:
                continue
            weighted_sum = sum(signal * weight for signal, weight in neighbors)
            weight_total = sum(weight for _, weight in neighbors)
            if weight_total <= 0:
                continue
            interpolated_signal = weighted_sum / weight_total
            interpolated.append(
                {
                    "cell_x": cell_x,
                    "cell_y": cell_y,
                    "signal": round(float(interpolated_signal), 2),
                    "count": 0,
                    "confidence": 0.0,
                    "interpolated": True,
                }
            )

    return interpolated


def find_weak_clusters(points, threshold=-80):
    visited = set()
    clusters = []

    for (x, y), (signal, _) in points.items():
        if signal >= threshold or (x, y) in visited:
            continue

        stack = [(x, y)]
        cluster = []

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))

            s, _ = points.get((cx, cy), (None, None))
            if s is None:
                continue
            if s < threshold:
                cluster.append((cx, cy))

                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in points:
                        stack.append((nx, ny))

        if len(cluster) >= 3:
            clusters.append(cluster)

    return clusters

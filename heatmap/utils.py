from collections import defaultdict

from django.conf import settings

from .models import FloorPlan


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
            }
    else:
        fallback_blocks = list(getattr(settings, "HEATMAP_BLOCKS", []))
        fallback_floors = list(getattr(settings, "HEATMAP_FLOORS", []))
        for block_code in fallback_blocks:
            blocks.append(block_code)
            block_floors[block_code] = list(fallback_floors)
            for floor_number in fallback_floors:
                dims = _settings_floor_dims(floor_number)
                floor_configs[f"{block_code}:{floor_number}"] = {
                    "rows": dims["rows"],
                    "cols": dims["cols"],
                    "image_url": "",
                    "floor_name": f"Floor {floor_number}",
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


def get_service_providers():
    providers = getattr(settings, "HEATMAP_SERVICE_PROVIDERS", {})
    return {
        "wifi": list(providers.get("wifi", [])),
        "mobile": list(providers.get("mobile", [])),
    }

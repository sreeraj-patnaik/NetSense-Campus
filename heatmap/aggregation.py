from statistics import median

from django.db import transaction

from .models import CellAggregate, Scan
from .utils import cell_to_id


def _median(values):
    if not values:
        return None
    return float(median(values))


def _upsert_aggregate(
    *,
    floor_plan,
    cell_x,
    cell_y,
    mode,
    service_provider,
    is_all_providers,
    signal_values,
):
    if not signal_values:
        return None
    cell_id = cell_to_id(cell_x, cell_y, floor_plan.grid_cols)
    aggregate, _ = CellAggregate.objects.update_or_create(
        floor_plan=floor_plan,
        cell_x=cell_x,
        cell_y=cell_y,
        mode=mode,
        service_provider=service_provider,
        is_all_providers=is_all_providers,
        defaults={
            "cell_id": cell_id,
            "median_signal": _median(signal_values),
            "scan_count": len(signal_values),
        },
    )
    return aggregate


@transaction.atomic
def refresh_cell_aggregates(scan):
    floor_plan = scan.floor_plan
    cell_x = scan.cell_x
    cell_y = scan.cell_y
    mode = scan.mode
    provider = scan.service_provider or "Unknown"

    provider_signals = list(
        Scan.objects.filter(
            floor_plan=floor_plan,
            mode=mode,
            service_provider=provider,
            cell_x=cell_x,
            cell_y=cell_y,
        ).values_list("signal_strength", flat=True)
    )
    _upsert_aggregate(
        floor_plan=floor_plan,
        cell_x=cell_x,
        cell_y=cell_y,
        mode=mode,
        service_provider=provider,
        is_all_providers=False,
        signal_values=provider_signals,
    )

    all_signals = list(
        Scan.objects.filter(
            floor_plan=floor_plan,
            mode=mode,
            cell_x=cell_x,
            cell_y=cell_y,
        ).values_list("signal_strength", flat=True)
    )
    _upsert_aggregate(
        floor_plan=floor_plan,
        cell_x=cell_x,
        cell_y=cell_y,
        mode=mode,
        service_provider="",
        is_all_providers=True,
        signal_values=all_signals,
    )


def rebuild_aggregates_for_floor(floor_plan, mode=None):
    scans = Scan.objects.filter(floor_plan=floor_plan)
    if mode in [Scan.WIFI, Scan.MOBILE]:
        scans = scans.filter(mode=mode)
    delete_qs = CellAggregate.objects.filter(floor_plan=floor_plan)
    if mode in [Scan.WIFI, Scan.MOBILE]:
        delete_qs = delete_qs.filter(mode=mode)
    delete_qs.delete()

    grouped = {}
    for scan in scans.iterator():
        provider = scan.service_provider or "Unknown"
        key = (scan.cell_x, scan.cell_y, scan.mode, provider, False)
        grouped.setdefault(key, []).append(scan.signal_strength)
        all_key = (scan.cell_x, scan.cell_y, scan.mode, "", True)
        grouped.setdefault(all_key, []).append(scan.signal_strength)

    for (cell_x, cell_y, scan_mode, provider, is_all), values in grouped.items():
        _upsert_aggregate(
            floor_plan=floor_plan,
            cell_x=cell_x,
            cell_y=cell_y,
            mode=scan_mode,
            service_provider=provider,
            is_all_providers=is_all,
            signal_values=values,
        )

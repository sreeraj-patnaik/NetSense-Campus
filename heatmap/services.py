from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from math import sqrt
from statistics import mean, pstdev
from typing import Any

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from .models import (
    Block,
    CellAggregate,
    Institution,
    InstitutionMembership,
    Scan,
    UserDashboardPreference,
)
from .utils import compute_confidence, get_floor_plan, get_floor_registry, get_service_providers


User = get_user_model()


@dataclass(frozen=True)
class DashboardSelection:
    institution: Institution | None
    preset: str
    compare_block: str
    compare_floor: int | None
    weak_threshold: int


def current_membership(user):
    if not user or not user.is_authenticated:
        return None
    memberships = InstitutionMembership.objects.select_related("institution").filter(
        user=user,
        status=InstitutionMembership.APPROVED,
    )
    admin_membership = memberships.filter(role=InstitutionMembership.ADMIN).order_by(
        "-approved_at",
        "-created_at",
    ).first()
    if admin_membership:
        return admin_membership
    return memberships.order_by("-approved_at", "-created_at").first()


def current_institution(user):
    membership = current_membership(user)
    return membership.institution if membership else None


def institution_for_user(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        preference = get_dashboard_preference(user)
        if preference and preference.selected_institution and preference.selected_institution.is_active:
            return preference.selected_institution
        return None
    return current_institution(user)


def institution_queryset_for_user(user):
    if not user or not user.is_authenticated:
        return Institution.objects.none()
    if user.is_superuser:
        return Institution.objects.filter(is_active=True)
    institution = institution_for_user(user)
    if not institution:
        return Institution.objects.none()
    return Institution.objects.filter(id=institution.id, is_active=True)


def approved_institutions_for_user(user):
    return institution_queryset_for_user(user)


def is_institution_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return InstitutionMembership.objects.filter(
        user=user,
        status=InstitutionMembership.APPROVED,
        role=InstitutionMembership.ADMIN,
    ).exists()


def user_can_scan(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return InstitutionMembership.objects.filter(
        user=user,
        status=InstitutionMembership.APPROVED,
    ).filter(
        models.Q(role=InstitutionMembership.ADMIN) | models.Q(can_scan=True)
    ).exists()


def user_can_view_heatmap(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return InstitutionMembership.objects.filter(
        user=user,
        status=InstitutionMembership.APPROVED,
    ).exists()


def get_dashboard_preference(user):
    if not user or not user.is_authenticated:
        return None
    preference, _ = UserDashboardPreference.objects.get_or_create(user=user)
    return preference


def save_dashboard_preference(
    user,
    *,
    selected_institution_id: int | None = None,
    dashboard_preset: str | None = None,
    compare_block: str | None = None,
    compare_floor: int | None = None,
    weak_threshold: int | None = None,
):
    if not user or not user.is_authenticated:
        return None

    preference = get_dashboard_preference(user)
    if not preference:
        return None

    updated_fields = []

    if selected_institution_id is not None:
        if not user.is_superuser:
            selected_institution_id = institution_for_user(user).id if institution_for_user(user) else None
        if selected_institution_id in {"", "auto", "none"}:
            preference.selected_institution = None
        else:
            institution = Institution.objects.filter(id=selected_institution_id, is_active=True).first()
            preference.selected_institution = institution
        updated_fields.append("selected_institution")

    if dashboard_preset:
        preference.dashboard_preset = dashboard_preset
        updated_fields.append("dashboard_preset")

    if compare_block is not None:
        preference.compare_block = compare_block.strip()
        updated_fields.append("compare_block")

    if compare_floor is not None:
        preference.compare_floor = compare_floor
        updated_fields.append("compare_floor")

    if weak_threshold is not None:
        preference.weak_threshold = weak_threshold
        updated_fields.append("weak_threshold")

    if not updated_fields:
        return preference

    preference.save(update_fields=updated_fields + ["updated_at"])
    return preference


def resolve_dashboard_selection(user) -> DashboardSelection:
    preference = get_dashboard_preference(user)
    institution = None
    preset = UserDashboardPreference.PRESET_MY_INSTITUTION
    compare_block = ""
    compare_floor = None
    weak_threshold = -80

    if preference:
        preset = preference.dashboard_preset or preset
        compare_block = preference.compare_block or ""
        compare_floor = preference.compare_floor
        weak_threshold = int(preference.weak_threshold or weak_threshold)
        if preference.selected_institution_id and user and user.is_superuser:
            institution = preference.selected_institution if preference.selected_institution and preference.selected_institution.is_active else None

    if institution is None:
        institution = institution_for_user(user)

    return DashboardSelection(
        institution=institution,
        preset=preset,
        compare_block=compare_block,
        compare_floor=compare_floor,
        weak_threshold=weak_threshold,
    )


def _registry_for_user(user):
    registry = get_floor_registry()
    if not user or not user.is_authenticated:
        return registry
    if user.is_superuser:
        return registry

    institution = institution_for_user(user)
    if not institution:
        return {"blocks": [], "block_floors": {}, "floor_configs": {}}
    allowed_blocks = set(
        Block.objects.filter(
            institution=institution,
            is_active=True,
        ).values_list("code", flat=True)
    )
    filtered_blocks = [code for code in registry["blocks"] if code in allowed_blocks]
    block_floors = {code: registry["block_floors"].get(code, []) for code in filtered_blocks}
    floor_configs = {
        key: value
        for key, value in registry["floor_configs"].items()
        if key.split(":", 1)[0] in allowed_blocks
    }
    return {
        "blocks": filtered_blocks,
        "block_floors": block_floors,
        "floor_configs": floor_configs,
    }


def viewer_context(user=None):
    registry = _registry_for_user(user)
    selection = resolve_dashboard_selection(user)

    blocks = registry["blocks"]
    block_floors = registry["block_floors"]
    floor_configs = registry["floor_configs"]

    preferred_blocks = []
    if selection.institution:
        preferred_blocks = list(
            Block.objects.filter(
                institution=selection.institution,
                is_active=True,
                code__in=blocks,
            )
            .order_by("code")
            .values_list("code", flat=True)
        )

    ordered_blocks = preferred_blocks + [code for code in blocks if code not in preferred_blocks]
    initial_block = ordered_blocks[0] if ordered_blocks else ""
    floors = block_floors.get(initial_block, [])
    initial_floor = floors[0] if floors else ""
    initial_cfg = floor_configs.get(f"{initial_block}:{initial_floor}", {})
    initial_floor_image = initial_cfg.get("image_url", "")

    approved = Institution.objects.none()
    access_status = "public"
    if user and user.is_authenticated:
        if user.is_superuser:
            approved = Institution.objects.filter(is_active=True)
            access_status = "approved"
        elif user.is_staff:
            approved = Institution.objects.filter(is_active=True)
            access_status = "approved"
        else:
            approved = institution_queryset_for_user(user)
            if approved.exists():
                access_status = "approved"
            elif InstitutionMembership.objects.filter(user=user, status=InstitutionMembership.PENDING).exists():
                access_status = "pending"
            else:
                access_status = "none"
        if not (user.is_staff or user.is_superuser) and not approved.exists() and InstitutionMembership.objects.filter(user=user, status=InstitutionMembership.PENDING).exists():
            access_status = "pending"

    if access_status == "approved" and not blocks:
        access_status = "no_blocks"

    return {
        "blocks": ordered_blocks,
        "floors": floors,
        "initial_block": initial_block,
        "initial_floor": initial_floor,
        "initial_floor_image": initial_floor_image if access_status == "approved" else "",
        "grid_rows": max(1, int(initial_cfg.get("rows") or 12)),
        "grid_cols": max(1, int(initial_cfg.get("cols") or 8)),
        "block_floors": block_floors,
        "floor_configs": floor_configs,
        "service_providers": get_service_providers(),
        "modes": Scan.MODE_CHOICES,
        "access_status": access_status,
        "selected_institution": selection.institution,
        "selected_preset": selection.preset,
        "compare_block": selection.compare_block,
        "compare_floor": selection.compare_floor,
        "weak_threshold": selection.weak_threshold,
        "approved_institutions": approved if user and user.is_authenticated else Institution.objects.none(),
    }


def _aggregate_queryset(floor_plan, mode: str | None = None, service_provider: str = ""):
    queryset = CellAggregate.objects.filter(floor_plan=floor_plan)
    if mode in {Scan.WIFI, Scan.MOBILE}:
        queryset = queryset.filter(mode=mode)

    service_provider = (service_provider or "").strip()
    if not service_provider or service_provider.lower() == "all":
        queryset = queryset.filter(is_all_providers=True)
    else:
        queryset = queryset.filter(is_all_providers=False, service_provider=service_provider)
    return queryset


def _floor_plan_for_user(user, block: str, floor: int):
    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return None
    if user and user.is_authenticated and not user.is_superuser:
        institution = institution_for_user(user)
        if not institution or floor_plan.block.institution_id != institution.id:
            return None
    return floor_plan


def floor_plan_for_user(user, block: str, floor: int):
    return _floor_plan_for_user(user, block, floor)


def registry_for_user(user):
    return _registry_for_user(user)


def _daily_metrics_for_scans(scans):
    buckets: dict[Any, list[float]] = defaultdict(list)
    for scan in scans:
        buckets[scan.created_at.date()].append(float(scan.signal_strength))
    return buckets


def build_trend_payload(*, block: str, floor: int, mode: str, service_provider: str = "", days: int = 14, user=None):
    floor_plan = _floor_plan_for_user(user, block, floor)
    if not floor_plan:
        return {"points": [], "summary": {}}

    since = timezone.now() - timedelta(days=days - 1)
    scans = Scan.objects.filter(floor_plan=floor_plan, created_at__gte=since)
    if mode in {Scan.WIFI, Scan.MOBILE}:
        scans = scans.filter(mode=mode)
    service_provider = (service_provider or "").strip()
    if service_provider and service_provider.lower() != "all":
        scans = scans.filter(service_provider=service_provider)

    buckets = _daily_metrics_for_scans(scans.order_by("created_at"))
    today = timezone.localdate()
    points = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        values = buckets.get(day, [])
        if values:
            avg_signal = round(sum(values) / len(values), 2)
            low_signal = sum(1 for value in values if value < -80)
            spread = round(float(pstdev(values)) if len(values) > 1 else 0.0, 2)
        else:
            avg_signal = None
            low_signal = 0
            spread = 0.0
        points.append(
            {
                "date": day.isoformat(),
                "avg_signal": avg_signal,
                "scan_count": len(values),
                "weak_scans": low_signal,
                "spread": spread,
            }
        )

    numeric = [point["avg_signal"] for point in points if point["avg_signal"] is not None]
    summary = {
        "avg_signal": round(mean(numeric), 2) if numeric else None,
        "min_signal": round(min(numeric), 2) if numeric else None,
        "max_signal": round(max(numeric), 2) if numeric else None,
        "total_scans": sum(point["scan_count"] for point in points),
    }
    return {"points": points, "summary": summary}


def _floor_snapshot_metrics(*, block: str, floor: int, mode: str, service_provider: str = "", weak_threshold: int = -80, user=None):
    floor_plan = _floor_plan_for_user(user, block, floor)
    if not floor_plan:
        return None

    queryset = _aggregate_queryset(floor_plan, mode=mode, service_provider=service_provider)
    if not queryset.exists():
        return {
            "avg_signal": None,
            "avg_confidence": None,
            "weak_cells": 0,
            "measured_cells": 0,
            "scan_count": 0,
            "weak_ratio": 0.0,
        }

    signals = []
    confidences = []
    weak_cells = 0
    scan_count = 0
    for row in queryset:
        signal = float(row.median_signal)
        signals.append(signal)
        scan_count += int(row.scan_count)
        confidences.append(
            compute_confidence(
                row.scan_count,
                getattr(row, "signal_variance", 0),
                row.updated_at,
            )
        )
        if signal < weak_threshold:
            weak_cells += 1

    measured_cells = len(signals)
    return {
        "avg_signal": round(mean(signals), 2) if signals else None,
        "avg_confidence": round(mean(confidences), 3) if confidences else None,
        "weak_cells": weak_cells,
        "measured_cells": measured_cells,
        "scan_count": scan_count,
        "weak_ratio": round(weak_cells / measured_cells, 3) if measured_cells else 0.0,
    }


def _period_metrics(signal_values: list[float]):
    if not signal_values:
        return {"avg_signal": None, "spread": None, "confidence": None}
    avg_signal = mean(signal_values)
    spread = pstdev(signal_values) if len(signal_values) > 1 else 0.0
    confidence = max(0.0, min(1.0, ((avg_signal + 100) / 40.0) - (spread / 20.0)))
    return {
        "avg_signal": round(avg_signal, 2),
        "spread": round(spread, 2),
        "confidence": round(confidence, 3),
    }


def build_alerts_payload(*, block: str, floor: int, mode: str, service_provider: str = "", weak_threshold: int = -80, user=None):
    floor_plan = _floor_plan_for_user(user, block, floor)
    if not floor_plan:
        return {"alerts": [], "summary": {}}

    now = timezone.now()
    recent_start = now - timedelta(days=7)
    prior_start = now - timedelta(days=14)

    recent_scans = list(
        Scan.objects.filter(floor_plan=floor_plan, created_at__gte=recent_start)
        .order_by("created_at")
        .values_list("signal_strength", flat=True)
    )
    prior_scans = list(
        Scan.objects.filter(
            floor_plan=floor_plan,
            created_at__gte=prior_start,
            created_at__lt=recent_start,
        )
        .order_by("created_at")
        .values_list("signal_strength", flat=True)
    )
    if mode in {Scan.WIFI, Scan.MOBILE}:
        recent_queryset = Scan.objects.filter(floor_plan=floor_plan, created_at__gte=recent_start, mode=mode)
        prior_queryset = Scan.objects.filter(
            floor_plan=floor_plan,
            created_at__gte=prior_start,
            created_at__lt=recent_start,
            mode=mode,
        )
        recent_scans = list(recent_queryset.order_by("created_at").values_list("signal_strength", flat=True))
        prior_scans = list(prior_queryset.order_by("created_at").values_list("signal_strength", flat=True))

    service_provider = (service_provider or "").strip()
    if service_provider and service_provider.lower() != "all":
        recent_scans = list(
            Scan.objects.filter(
                floor_plan=floor_plan,
                created_at__gte=recent_start,
                mode=mode if mode in {Scan.WIFI, Scan.MOBILE} else Scan.WIFI,
                service_provider=service_provider,
            ).values_list("signal_strength", flat=True)
        )
        prior_scans = list(
            Scan.objects.filter(
                floor_plan=floor_plan,
                created_at__gte=prior_start,
                created_at__lt=recent_start,
                mode=mode if mode in {Scan.WIFI, Scan.MOBILE} else Scan.WIFI,
                service_provider=service_provider,
            ).values_list("signal_strength", flat=True)
        )

    recent_metrics = _period_metrics(list(map(float, recent_scans)))
    prior_metrics = _period_metrics(list(map(float, prior_scans)))

    current_snapshot = _floor_snapshot_metrics(
        block=block,
        floor=floor,
        mode=mode,
        service_provider=service_provider,
        weak_threshold=weak_threshold,
        user=user,
    )

    alerts = []
    if recent_scans and prior_scans:
        recent_weak = sum(1 for value in recent_scans if value < weak_threshold)
        prior_weak = sum(1 for value in prior_scans if value < weak_threshold)
        if recent_weak >= prior_weak + 3 and recent_weak >= max(3, int(prior_weak * 1.25)):
            alerts.append(
                {
                    "type": "weak_zone_growth",
                    "tone": "warning",
                    "title": "Weak zones are expanding",
                    "message": f"Weak scans increased from {prior_weak} to {recent_weak} in the last 7 days.",
                }
            )

        if (
            recent_metrics["confidence"] is not None
            and prior_metrics["confidence"] is not None
            and recent_metrics["confidence"] < prior_metrics["confidence"] - 0.10
        ):
            alerts.append(
                {
                    "type": "confidence_drop",
                    "tone": "danger",
                    "title": "Confidence is dropping",
                    "message": (
                        f"Estimated confidence fell from {prior_metrics['confidence']:.3f} to "
                        f"{recent_metrics['confidence']:.3f} over the last 7 days."
                    ),
                }
            )

    if current_snapshot and current_snapshot["avg_confidence"] is not None and current_snapshot["avg_confidence"] < 0.55:
        alerts.append(
            {
                "type": "low_confidence",
                "tone": "warning",
                "title": "Current floor confidence is low",
                "message": f"Average cell confidence is {current_snapshot['avg_confidence']:.3f} right now.",
            }
        )

    if current_snapshot and current_snapshot["weak_ratio"] >= 0.2:
        alerts.append(
            {
                "type": "weak_cell_density",
                "tone": "warning",
                "title": "Weak-cell density is high",
                "message": f"{current_snapshot['weak_cells']} of {current_snapshot['measured_cells']} measured cells are below threshold.",
            }
        )

    summary = {
        "recent": recent_metrics,
        "prior": prior_metrics,
        "current": current_snapshot,
    }
    return {"alerts": alerts, "summary": summary}


def _target_floor(floor_plan, compare_block: str | None, compare_floor: int | None, institution_id: int | None = None):
    if compare_block and compare_floor is not None:
        target = get_floor_plan(compare_block, compare_floor)
        if institution_id and target and target.block.institution_id != institution_id:
            return None
        return target

    same_block_floor = get_floor_plan(floor_plan.block.code, floor_plan.number + 1)
    if institution_id and same_block_floor and same_block_floor.block.institution_id != institution_id:
        same_block_floor = None
    if same_block_floor:
        return same_block_floor

    prev_same_block_floor = get_floor_plan(floor_plan.block.code, max(1, floor_plan.number - 1))
    if institution_id and prev_same_block_floor and prev_same_block_floor.block.institution_id != institution_id:
        prev_same_block_floor = None
    if prev_same_block_floor and prev_same_block_floor.number != floor_plan.number:
        return prev_same_block_floor

    alt_blocks = Block.objects.filter(is_active=True)
    if institution_id:
        alt_blocks = alt_blocks.filter(institution_id=institution_id)
    alt_block = (
        alt_blocks.exclude(code=floor_plan.block.code)
        .order_by("code")
        .first()
    )
    if alt_block:
        return get_floor_plan(alt_block.code, floor_plan.number) or alt_block.floors.filter(is_active=True).order_by("number").first()
    return None


def build_comparison_payload(
    *,
    block: str,
    floor: int,
    mode: str,
    service_provider: str = "",
    compare_block: str | None = None,
    compare_floor: int | None = None,
    weak_threshold: int = -80,
    user=None,
):
    floor_plan = _floor_plan_for_user(user, block, floor)
    if not floor_plan:
        return {"current": None, "comparison": None}

    target_floor = _target_floor(
        floor_plan,
        compare_block,
        compare_floor,
        institution_id=floor_plan.block.institution_id,
    )
    if not target_floor:
        return {"current": None, "comparison": None}

    current = _floor_snapshot_metrics(
        block=floor_plan.block.code,
        floor=floor_plan.number,
        mode=mode,
        service_provider=service_provider,
        weak_threshold=weak_threshold,
        user=user,
    )
    comparison = _floor_snapshot_metrics(
        block=target_floor.block.code,
        floor=target_floor.number,
        mode=mode,
        service_provider=service_provider,
        weak_threshold=weak_threshold,
        user=user,
    )
    return {
        "current": {
            "block": floor_plan.block.code,
            "floor": floor_plan.number,
            **(current or {}),
        },
        "comparison": {
            "block": target_floor.block.code,
            "floor": target_floor.number,
            **(comparison or {}),
        },
    }

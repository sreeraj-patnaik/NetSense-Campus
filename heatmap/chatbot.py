from __future__ import annotations

import re
from collections import defaultdict
from datetime import timedelta
from statistics import mean, pstdev
from typing import Any

from django.urls import reverse
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from .models import Block, CellAggregate, FloorPlan, Scan
from .services import build_comparison_payload, build_trend_payload, floor_plan_for_user, registry_for_user
from .utils import cell_from_id, compute_confidence, find_weak_clusters, get_service_providers, score_cell

CHATBOT_STATE_KEY = "netsense_chatbot_pending"
ASSISTANT_NAME = "Spen Sense"

ANALYTICS_KEYWORDS = {
    "best provider",
    "worst provider",
    "average signal",
    "weak zone",
    "weak zones",
    "strong zone",
    "strong zones",
    "floor comparison",
    "block comparison",
    "compare",
    "trend",
    "scan count",
    "scan counts",
    "coverage quality",
    "missing scan",
    "recommendation",
    "recommendations",
    "signal variance",
    "variance",
    "coverage",
    "signal",
    "provider",
    "provider comparison",
    "network",
    "wifi",
    "mobile",
    "heatmap",
    "floor",
    "block",
    "scan",
    "cluster",
}

GENERAL_INTENTS = {
    "hi",
    "hello",
    "hey",
    "how are you",
    "joke",
    "explain python",
    "what is ai",
}

APP_INFO_PATTERNS = (
    r"\bwhat(?:'s| is) this app for\b",
    r"\bwhat does this app do\b",
    r"\bwhat can this app do\b",
    r"\bwhat is this for\b",
    r"\babout this app\b",
    r"\btell me about this app\b",
    r"\bwhat is netsense\b",
    r"\bwhat is spen sense\b",
    r"\bhelp me understand this app\b",
)

CURRENT_CONTEXT_HINTS = {
    "here",
    "this floor",
    "current floor",
    "this block",
    "current block",
    "current view",
    "this view",
    "here?",
}

WIFI_ALIASES = {"wifi", "wi-fi", "wireless"}
MOBILE_ALIASES = {"mobile", "cellular", "cell", "4g", "5g"}
INSTITUTION_HINTS = {
    "my institution",
    "institution-wide",
    "across my institution",
    "in my institution",
    "overall",
    "campus-wide",
}

AUTH_KEYWORDS = {
    "sign in",
    "login",
    "log in",
    "authenticate",
    "access",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _message_tokens(message: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalize_text(message))


def _extract_mode(message: str) -> str | None:
    lowered = _normalize_text(message)
    if any(alias in lowered for alias in WIFI_ALIASES):
        return Scan.WIFI
    if any(alias in lowered for alias in MOBILE_ALIASES):
        return Scan.MOBILE
    return None


def _extract_provider_name(message: str) -> str | None:
    providers = get_service_providers()
    ordered_names = list(providers.get("wifi", [])) + list(providers.get("mobile", []))
    ordered_names = sorted({name for name in ordered_names if name}, key=len, reverse=True)
    lowered = _normalize_text(message)
    for provider in ordered_names:
        if provider and provider.lower() in lowered:
            return provider
    return None


def _extract_provider_names(message: str) -> list[str]:
    providers = get_service_providers()
    ordered_names = list(providers.get("wifi", [])) + list(providers.get("mobile", []))
    ordered_names = sorted({name for name in ordered_names if name}, key=len, reverse=True)
    lowered = _normalize_text(message)
    matches = []
    for provider in ordered_names:
        if provider and provider.lower() in lowered and provider not in matches:
            matches.append(provider)
    return matches


def _extract_block(message: str, allowed_blocks: list[str]) -> str | None:
    lowered = _normalize_text(message)
    match = re.search(r"\bblock\s+([a-z0-9]+)\b", lowered)
    if match:
        candidate = match.group(1).upper()
        for block in allowed_blocks:
            if block.upper() == candidate:
                return block

    tokens = set(_message_tokens(message))
    for block in sorted(allowed_blocks, key=len, reverse=True):
        if block.lower() in tokens:
            return block
    return None


def _extract_floor(message: str) -> int | None:
    lowered = _normalize_text(message)
    match = re.search(r"\b(?:floor|f)\s*([0-9]+)\b", lowered)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _explicit_institution_scope(message: str) -> bool:
    lowered = _normalize_text(message)
    return any(hint in lowered for hint in INSTITUTION_HINTS)


def _context_hints(message: str) -> bool:
    lowered = _normalize_text(message)
    return any(hint in lowered for hint in CURRENT_CONTEXT_HINTS)


def _mentions_institution(message: str) -> bool:
    lowered = _normalize_text(message)
    if "institution" in lowered:
        return True
    tokens = set(_message_tokens(message))
    return any(token in tokens for token in {"inst", "instt", "inst."})


def _is_general_greeting(message: str) -> bool:
    lowered = _normalize_text(message)
    tokens = _message_tokens(message)
    if lowered in {"hi", "hello", "hey", "hello dear", "hi dear", "hey dear"}:
        return True
    return any(token in {"hi", "hello", "hey"} for token in tokens) and len(tokens) <= 3


def _looks_like_auth_request(message: str) -> bool:
    lowered = _normalize_text(message)
    return any(keyword in lowered for keyword in AUTH_KEYWORDS)


def _choice(label: str, message: str | None = None, href: str | None = None) -> dict[str, str]:
    choice = {"label": label}
    if message:
        choice["message"] = message
    if href:
        choice["href"] = href
    return choice


def _login_choice():
    return _choice("Sign in", href=reverse("login"))


def _quick_choices(*items: dict[str, str]) -> list[dict[str, str]]:
    return [item for item in items if item]


def _assistant_name() -> str:
    return ASSISTANT_NAME


def _analytics_intent(message: str) -> str | None:
    lowered = _normalize_text(message)
    if not lowered:
        return None

    tokens = set(_message_tokens(message))
    if lowered in {"hi", "hello", "hey", "thanks", "thank you"}:
        return None
    if "how are you" in lowered:
        return None
    if "joke" in tokens:
        return None
    if "python" in tokens and "explain" in tokens:
        return None
    if "ai" in tokens and "what" in tokens:
        return None
    if _mentions_institution(message) and any(word in tokens for word in {"my", "me", "name", "who", "what"}):
        return "institution_identity"

    if "best provider" in lowered or ("best" in lowered and "provider" in lowered):
        return "best_provider"
    if "worst provider" in lowered or ("worst" in lowered and "provider" in lowered):
        return "worst_provider"
    if "average signal" in lowered or ("average" in lowered and "signal" in lowered):
        return "average_signal"
    if "weak zone" in lowered or "weak zones" in lowered:
        return "weak_zones"
    if "strong zone" in lowered or "strong zones" in lowered:
        return "strong_zones"
    if "compare" in lowered or "comparison" in lowered:
        return "comparison"
    if "trend" in lowered or "over time" in lowered:
        return "trend"
    if "scan count" in lowered or "scan counts" in lowered or "how many scans" in lowered:
        return "scan_counts"
    if "coverage quality" in lowered or ("coverage" in lowered and "quality" in lowered):
        return "coverage_quality"
    if "missing scan" in lowered or "recommend" in lowered:
        return "missing_scan_recommendations"
    if "signal variance" in lowered or "variance" in lowered:
        return "signal_variance"
    if any(keyword in lowered for keyword in {"signal", "coverage", "provider", "wifi", "mobile", "heatmap", "floor", "block", "scan", "cluster"}):
        return "general_analytics"
    return None


def _is_app_info_question(message: str) -> bool:
    lowered = _normalize_text(message)
    if not lowered:
        return False
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in APP_INFO_PATTERNS)


def _auth_required_response(message: str) -> dict[str, Any]:
    return {
        "mode": "auth",
        "context_scope": "auth",
        "answer": (
            f"Please sign in so I can read your institution-specific NetSense data. "
            f"You can still ask general questions after that."
        ),
        "choices": [_login_choice()],
    }


def _institution_identity_response(user) -> dict[str, Any]:
    institution = None
    if user and getattr(user, "is_authenticated", False):
        from .services import institution_for_user

        institution = institution_for_user(user)

    if not institution:
        return _auth_required_response("institution")

    return {
        "mode": "analytics",
        "context_scope": "analytics",
        "answer": f"Your current institution is {institution.name}.",
        "choices": [
            _choice("Open coverage", message="Show my coverage dashboard"),
            _choice("Current signal", message="What are my current signal strengths?"),
        ],
    }


def _app_info_response(user) -> dict[str, Any]:
    is_authenticated = bool(user and getattr(user, "is_authenticated", False))
    answer = (
        "NetSense Campus helps you review institution-scoped network coverage, spot weak areas, compare blocks and floors, and track scan trends. "
        "I can also help you look up your institution, current signal, provider comparisons, and coverage quality."
    )
    choices = [
        _choice("Live coverage", message="What are my current signal strengths?"),
        _choice("Weak zones", message="Show weak signal areas."),
        _choice("Best provider", message="Which provider performs best in my institution?"),
    ]
    if is_authenticated:
        choices.insert(0, _choice("My institution", message="What is my institution name?"))
    else:
        choices.insert(0, _login_choice())
    return {
        "mode": "general",
        "context_scope": "general",
        "answer": answer,
        "choices": choices,
    }


def _build_pending_state(intent: str, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "intent": intent,
        "scope": scope,
    }


def _pending_state(request) -> dict[str, Any] | None:
    state = request.session.get(CHATBOT_STATE_KEY)
    return state if isinstance(state, dict) else None


def _store_pending_state(request, state: dict[str, Any]) -> None:
    request.session[CHATBOT_STATE_KEY] = state
    request.session.modified = True


def _clear_pending_state(request) -> None:
    if CHATBOT_STATE_KEY in request.session:
        request.session.pop(CHATBOT_STATE_KEY, None)
        request.session.modified = True


def _scope_from_payload(user, message: str, payload: dict[str, Any] | None, pending_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry_for_user(user)
    allowed_blocks = list(registry.get("blocks", []))
    heatmap = payload.get("heatmap") if isinstance(payload, dict) else None
    heatmap = heatmap if isinstance(heatmap, dict) else {}

    scope = {
        "institution": None,
        "block": None,
        "floor": None,
        "mode": None,
        "service_provider": None,
        "compare_block": None,
        "compare_floor": None,
        "scope_kind": "ambiguous",
    }

    institution = None
    if user and getattr(user, "is_authenticated", False):
        from .services import institution_for_user

        institution = institution_for_user(user)
    scope["institution"] = institution

    explicit_block = _extract_block(message, allowed_blocks)
    explicit_floor = _extract_floor(message)
    explicit_mode = _extract_mode(message)
    explicit_provider = _extract_provider_name(message)
    explicit_providers = _extract_provider_names(message)

    use_heatmap_context = bool(
        pending_scope
        or _context_hints(message)
        or explicit_block
        or explicit_floor
        or explicit_mode
        or explicit_provider
        or explicit_providers
    )

    if pending_scope:
        scope.update(
            {
                "block": pending_scope.get("block") or None,
                "floor": pending_scope.get("floor") or None,
                "mode": pending_scope.get("mode") or None,
                "service_provider": pending_scope.get("service_provider") or None,
                "compare_block": pending_scope.get("compare_block") or None,
                "compare_floor": pending_scope.get("compare_floor") or None,
                "scope_kind": pending_scope.get("scope_kind") or scope["scope_kind"],
            }
        )

    if use_heatmap_context:
        if not scope["block"]:
            scope["block"] = explicit_block or (heatmap.get("block") or "").strip() or None
        if not scope["floor"]:
            scope["floor"] = explicit_floor or heatmap.get("floor")
        if not scope["mode"]:
            scope["mode"] = explicit_mode or (heatmap.get("mode") or "").strip() or None
        if not scope["service_provider"]:
            provider = explicit_provider or (heatmap.get("service_provider") or "").strip() or None
            if provider and provider.lower() != "all":
                scope["service_provider"] = provider
        if explicit_providers:
            scope["provider_names"] = explicit_providers

    if explicit_block:
        scope["block"] = explicit_block
    if explicit_floor is not None:
        scope["floor"] = explicit_floor
    if explicit_mode:
        scope["mode"] = explicit_mode
    if explicit_provider:
        scope["service_provider"] = explicit_provider
    if explicit_providers:
        scope["provider_names"] = explicit_providers

    if _explicit_institution_scope(message):
        scope["scope_kind"] = "institution"
    elif scope["block"] or scope["floor"]:
        scope["scope_kind"] = "floor"

    return scope


def _floor_queryset_for_scope(user, scope: dict[str, Any]):
    block = scope.get("block")
    floor = scope.get("floor")
    if block is None or floor is None:
        return None
    return floor_plan_for_user(user, str(block), int(floor))


def _aggregate_queryset_for_floor(floor_plan: FloorPlan, mode: str | None = None, service_provider: str | None = None):
    queryset = CellAggregate.objects.filter(floor_plan=floor_plan)
    if mode in {Scan.WIFI, Scan.MOBILE}:
        queryset = queryset.filter(mode=mode)

    if service_provider and service_provider.lower() != "all":
        queryset = queryset.filter(is_all_providers=False, service_provider=service_provider)
    else:
        queryset = queryset.filter(is_all_providers=True)
    return queryset


def _aggregate_queryset_for_institution(user, mode: str | None = None, service_provider: str | None = None):
    registry = registry_for_user(user)
    blocks = registry.get("blocks", [])
    floors = []
    for block in blocks:
        for floor in registry.get("block_floors", {}).get(block, []):
            floor_plan = floor_plan_for_user(user, block, floor)
            if floor_plan:
                floors.append(floor_plan)

    queryset = CellAggregate.objects.filter(floor_plan__in=floors)
    if mode in {Scan.WIFI, Scan.MOBILE}:
        queryset = queryset.filter(mode=mode)
    if service_provider and service_provider.lower() != "all":
        queryset = queryset.filter(is_all_providers=False, service_provider=service_provider)
    else:
        queryset = queryset.filter(is_all_providers=True)
    return queryset


def _format_metric(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "--"
    return f"{value:.{digits}f}"


def _coverage_quality(avg_signal: float | None, weak_ratio: float | None, avg_confidence: float | None) -> str:
    if avg_signal is None:
        return "No measured data"
    if weak_ratio is not None and weak_ratio >= 0.25:
        return "Poor"
    if avg_signal >= -65 and (avg_confidence or 0) >= 0.7:
        return "Strong"
    if avg_signal >= -75 and (avg_confidence or 0) >= 0.5:
        return "Moderate"
    return "Needs attention"


def _cell_summary_from_queryset(queryset):
    rows = list(queryset.order_by("cell_y", "cell_x"))
    if not rows:
        return None

    signals = [float(row.median_signal) for row in rows]
    confidences = [
        compute_confidence(
            row.scan_count,
            getattr(row, "signal_variance", 0),
            row.updated_at,
        )
        for row in rows
    ]
    weak_cells = [row for row in rows if float(row.median_signal) < -80]
    strong_cells = [row for row in rows if float(row.median_signal) >= -65]

    return {
        "cells": rows,
        "avg_signal": round(mean(signals), 2),
        "min_signal": round(min(signals), 2),
        "max_signal": round(max(signals), 2),
        "avg_confidence": round(mean(confidences), 3) if confidences else None,
        "weak_cells": len(weak_cells),
        "strong_cells": len(strong_cells),
        "measured_cells": len(rows),
        "scan_count": sum(int(row.scan_count) for row in rows),
        "weak_ratio": round(len(weak_cells) / len(rows), 3) if rows else 0.0,
        "avg_variance": round(mean(float(row.signal_variance or 0) for row in rows), 2) if rows else 0.0,
    }


def _provider_summary(queryset):
    provider_rows = (
        queryset.exclude(service_provider="")
        .values("service_provider")
        .annotate(
            avg_signal=Avg("median_signal"),
            avg_variance=Avg("signal_variance"),
            total_scans=Sum("scan_count"),
            cells=Count("id"),
        )
        .order_by("-avg_signal", "service_provider")
    )
    rows = list(provider_rows)
    if not rows:
        return []
    return rows


def _provider_sentence(row: dict[str, Any]) -> str:
    return (
        f"{row['service_provider']} at {_format_metric(row.get('avg_signal'), 2)} dBm "
        f"across {row.get('cells', 0)} cells and {row.get('total_scans', 0) or 0} scans"
    )


def _floor_label(floor_plan: FloorPlan) -> str:
    return f"{floor_plan.block.code}-F{floor_plan.number}"


def _scope_requires_floor(intent: str) -> bool:
    return intent in {
        "average_signal",
        "weak_zones",
        "strong_zones",
        "comparison",
        "scan_counts",
        "coverage_quality",
        "missing_scan_recommendations",
        "signal_variance",
        "trend",
    }


def _scope_requires_provider_mode(intent: str) -> bool:
    return intent in {
        "best_provider",
        "worst_provider",
        "average_signal",
        "weak_zones",
        "strong_zones",
        "comparison",
        "coverage_quality",
        "signal_variance",
    }


def _missing_scope_fields(intent: str, scope: dict[str, Any]) -> list[str]:
    missing = []
    needs_floor = intent in {
        "best_provider",
        "worst_provider",
        "average_signal",
        "weak_zones",
        "strong_zones",
        "comparison",
        "scan_counts",
        "coverage_quality",
        "missing_scan_recommendations",
        "signal_variance",
        "trend",
        "general_analytics",
    }
    if needs_floor and scope.get("scope_kind") != "institution" and (scope.get("block") is None or scope.get("floor") is None):
        missing.extend(["block", "floor"])
    if _scope_requires_provider_mode(intent) and not scope.get("mode"):
        missing.append("mode")
    provider_names = scope.get("provider_names") or []
    if intent == "comparison" and len(provider_names) < 2:
        if scope.get("compare_block") is None:
            missing.append("compare_block")
        if scope.get("compare_floor") is None:
            missing.append("compare_floor")
    if intent == "comparison" and len(provider_names) >= 2:
        missing = [field for field in missing if field not in {"compare_block", "compare_floor"}]
    return missing


def _clarification_question(missing: list[str], intent: str) -> str:
    if intent == "comparison":
        return "Which other block and floor should I compare against?"
    if "mode" in missing and ("block" in missing or "floor" in missing):
        return "Which block, floor, and provider type should I use?"
    if "mode" in missing:
        return "Which provider type should I use, WiFi or Mobile?"
    if "block" in missing or "floor" in missing:
        return "Which block and floor should I use?"
    return "Could you share a little more detail?"


def _clarification_choices(user, scope: dict[str, Any], missing: list[str], intent: str) -> list[dict[str, str]]:
    registry = registry_for_user(user)
    blocks = registry.get("blocks", [])
    block_floors = registry.get("block_floors", {})

    if intent == "comparison" and len(scope.get("provider_names") or []) < 2 and "compare_block" in missing:
        return []

    if "block" in missing:
        return [
            _choice(f"Block {block}", message=f"block {block}") for block in blocks[:6]
        ]

    if "floor" in missing:
        block = scope.get("block")
        floors = block_floors.get(block, []) if block else []
        return [
            _choice(f"Floor {floor}", message=f"floor {floor}") for floor in floors[:6]
        ]

    if "mode" in missing:
        return [
            _choice("WiFi", message="wifi"),
            _choice("Mobile", message="mobile"),
        ]

    if "compare_block" in missing:
        return [
            _choice(f"Block {block}", message=f"compare block {block}") for block in blocks[:6]
        ]

    if "compare_floor" in missing:
        compare_block = scope.get("compare_block") or scope.get("block")
        floors = block_floors.get(compare_block, []) if compare_block else []
        return [
            _choice(f"Floor {floor}", message=f"compare floor {floor}") for floor in floors[:6]
        ]

    return []


def _clarification_response(user, scope: dict[str, Any], missing: list[str], intent: str) -> dict[str, Any]:
    choices = _clarification_choices(user, scope, missing, intent)
    return {
        "mode": "analytics",
        "context_scope": "analytics",
        "answer": _clarification_question(missing, intent),
        "choices": choices,
        "state": _build_pending_state(intent, scope),
    }


def _institution_name(scope: dict[str, Any]) -> str:
    institution = scope.get("institution")
    if institution:
        return institution.name
    return "all accessible institutions"


def _answer_best_or_worst_provider(user, scope: dict[str, Any], *, best: bool) -> str:
    mode = scope.get("mode")
    if not mode:
        return _clarification_question(["mode"], "best_provider" if best else "worst_provider")

    floor_plan = _floor_queryset_for_scope(user, scope)
    if floor_plan:
        queryset = CellAggregate.objects.filter(
            floor_plan=floor_plan,
            mode=mode,
            is_all_providers=False,
        )
        label = _floor_label(floor_plan)
        scope_desc = f"{label} {mode.upper()}"
    else:
        queryset = CellAggregate.objects.filter(mode=mode, is_all_providers=False)
        if scope.get("institution"):
            queryset = queryset.filter(floor_plan__block__institution=scope["institution"])
        scope_desc = f"{_institution_name(scope)} {mode.upper()}"

    rows = _provider_summary(queryset)
    if not rows:
        return f"I couldn't find live data for {scope_desc}."

    row = rows[0] if best else sorted(rows, key=lambda item: item.get("avg_signal") or -9999)[0]
    provider_line = _provider_sentence(row)
    qualifier = "best" if best else "weakest"
    return f"For {scope_desc}, the {qualifier} provider is {provider_line}."


def _answer_average_signal(user, scope: dict[str, Any]) -> str:
    mode = scope.get("mode")
    if not mode:
        return _clarification_question(["mode"], "average_signal")

    floor_plan = _floor_queryset_for_scope(user, scope)
    if floor_plan:
        queryset = _aggregate_queryset_for_floor(floor_plan, mode=mode, service_provider=scope.get("service_provider"))
        label = _floor_label(floor_plan)
        scope_desc = f"{label} {mode.upper()}"
    else:
        queryset = _aggregate_queryset_for_institution(user, mode=mode, service_provider=scope.get("service_provider"))
        scope_desc = f"{_institution_name(scope)} {mode.upper()}"

    summary = _cell_summary_from_queryset(queryset)
    if not summary:
        return f"I couldn't find live data for {scope_desc}."
    return f"Average signal for {scope_desc} is {_format_metric(summary['avg_signal'], 2)} dBm across {summary['scan_count']} scans."


def _answer_weak_or_strong_zones(user, scope: dict[str, Any], *, strong: bool) -> str:
    mode = scope.get("mode")
    if not mode:
        return _clarification_question(["mode"], "strong_zones" if strong else "weak_zones")

    floor_plan = _floor_queryset_for_scope(user, scope)
    if not floor_plan:
        return "Please choose a block and floor so I can identify specific zones."

    queryset = _aggregate_queryset_for_floor(floor_plan, mode=mode, service_provider=scope.get("service_provider"))
    summary = _cell_summary_from_queryset(queryset)
    if not summary:
        return f"I couldn't find live data for {_floor_label(floor_plan)} {mode.upper()}."

    cells = summary["cells"]
    ordered = sorted(cells, key=lambda row: float(row.median_signal), reverse=strong)
    top_cells = ordered[:5]
    label = "strongest" if strong else "weakest"
    descriptor = "strong" if strong else "weak"
    if not top_cells:
        return f"I couldn't find enough measured cells to describe {descriptor} zones."

    parts = [f"{_floor_label(floor_plan)} {mode.upper()} {label} cells:"]
    for row in top_cells:
        parts.append(
            f"{row.cell_x},{row.cell_y} at {_format_metric(float(row.median_signal), 2)} dBm"
        )
    return " | ".join(parts)


def _answer_comparison(user, scope: dict[str, Any]) -> str:
    mode = scope.get("mode")
    if not mode:
        return _clarification_question(["mode"], "comparison")

    provider_names = scope.get("provider_names") or []
    if len(provider_names) >= 2 and (scope.get("compare_block") is None or scope.get("compare_floor") is None):
        return _answer_provider_comparison(user, scope, provider_a=provider_names[0], provider_b=provider_names[1])

    floor = scope.get("floor")
    block = scope.get("block")
    compare_block = scope.get("compare_block")
    compare_floor = scope.get("compare_floor")
    if block is None or floor is None or compare_block is None or compare_floor is None:
        return _clarification_question(["block", "floor", "compare_block", "compare_floor"], "comparison")

    current_floor = floor_plan_for_user(user, str(block), int(floor))
    comparison_floor = floor_plan_for_user(user, str(compare_block), int(compare_floor))
    if not current_floor or not comparison_floor:
        return "I couldn't verify both floors inside your institution."

    comparison_payload = build_comparison_payload(
        block=current_floor.block.code,
        floor=current_floor.number,
        mode=mode,
        service_provider=scope.get("service_provider") or "",
        compare_block=comparison_floor.block.code,
        compare_floor=comparison_floor.number,
        user=user,
    )
    current = comparison_payload.get("current") or {}
    comparison = comparison_payload.get("comparison") or {}
    if not current or not comparison:
        return "I couldn't build that comparison from the live data."

    return (
        f"{_floor_label(current_floor)} averages {_format_metric(current.get('avg_signal'), 2)} dBm, "
        f"while {_floor_label(comparison_floor)} averages {_format_metric(comparison.get('avg_signal'), 2)} dBm. "
        f"Weak cells: {current.get('weak_cells', 0)} vs {comparison.get('weak_cells', 0)}."
    )


def _answer_provider_comparison(user, scope: dict[str, Any], *, provider_a: str, provider_b: str) -> str:
    mode = scope.get("mode")
    if not mode:
        return _clarification_question(["mode"], "comparison")

    floor_plan = _floor_queryset_for_scope(user, scope)
    if floor_plan:
        queryset = CellAggregate.objects.filter(
            floor_plan=floor_plan,
            mode=mode,
            is_all_providers=False,
            service_provider__in=[provider_a, provider_b],
        )
        scope_desc = _floor_label(floor_plan)
    else:
        queryset = CellAggregate.objects.filter(
            mode=mode,
            is_all_providers=False,
            service_provider__in=[provider_a, provider_b],
        )
        if scope.get("institution"):
            queryset = queryset.filter(floor_plan__block__institution=scope["institution"])
        scope_desc = _institution_name(scope)

    rows = list(
        queryset.values("service_provider")
        .annotate(
            avg_signal=Avg("median_signal"),
            total_scans=Sum("scan_count"),
            cells=Count("id"),
        )
        .order_by("-avg_signal", "service_provider")
    )
    if len(rows) < 2:
        return f"I couldn't find both providers in the live data for {scope_desc}."

    first, second = rows[0], rows[1]
    return (
        f"For {scope_desc} {mode.upper()}, {first['service_provider']} averages {_format_metric(first.get('avg_signal'), 2)} dBm "
        f"and {second['service_provider']} averages {_format_metric(second.get('avg_signal'), 2)} dBm. "
        f"Better coverage is currently with {first['service_provider']}."
    )


def _answer_scan_counts(user, scope: dict[str, Any]) -> str:
    floor_plan = _floor_queryset_for_scope(user, scope)
    if floor_plan:
        scans = Scan.objects.filter(floor_plan=floor_plan)
        if scope.get("mode") in {Scan.WIFI, Scan.MOBILE}:
            scans = scans.filter(mode=scope["mode"])
        if scope.get("service_provider") and scope["service_provider"].lower() != "all":
            scans = scans.filter(service_provider=scope["service_provider"])
        total = scans.count()
        return f"{_floor_label(floor_plan)} has {total} scans in the live database."

    registry = registry_for_user(user)
    floors = []
    for block in registry.get("blocks", []):
        for floor in registry.get("block_floors", {}).get(block, []):
            floor_plan = floor_plan_for_user(user, block, floor)
            if floor_plan:
                floors.append(floor_plan)

    scans = Scan.objects.filter(floor_plan__in=floors)
    if scope.get("mode") in {Scan.WIFI, Scan.MOBILE}:
        scans = scans.filter(mode=scope["mode"])
    if scope.get("service_provider") and scope["service_provider"].lower() != "all":
        scans = scans.filter(service_provider=scope["service_provider"])
    total = scans.count()
    return f"{_institution_name(scope)} has {total} scans in the live database."


def _answer_coverage_quality(user, scope: dict[str, Any]) -> str:
    mode = scope.get("mode")
    if not mode:
        return _clarification_question(["mode"], "coverage_quality")

    floor_plan = _floor_queryset_for_scope(user, scope)
    if floor_plan:
        queryset = _aggregate_queryset_for_floor(floor_plan, mode=mode, service_provider=scope.get("service_provider"))
        scope_desc = _floor_label(floor_plan)
    else:
        queryset = _aggregate_queryset_for_institution(user, mode=mode, service_provider=scope.get("service_provider"))
        scope_desc = _institution_name(scope)

    summary = _cell_summary_from_queryset(queryset)
    if not summary:
        return f"I couldn't find live data for {scope_desc}."

    quality = _coverage_quality(summary["avg_signal"], summary["weak_ratio"], summary["avg_confidence"])
    return (
        f"Coverage quality for {scope_desc} is {quality}. "
        f"Average signal is {_format_metric(summary['avg_signal'], 2)} dBm, weak-cell ratio is {summary['weak_ratio']:.3f}, "
        f"and confidence is {_format_metric(summary['avg_confidence'], 3)}."
    )


def _answer_missing_scan_recommendations(user, scope: dict[str, Any]) -> str:
    mode = scope.get("mode")
    floor_plan = _floor_queryset_for_scope(user, scope)
    if not floor_plan:
        return "Please choose a block and floor so I can recommend a scan target."
    if not mode:
        return _clarification_question(["mode"], "missing_scan_recommendations")

    queryset = _aggregate_queryset_for_floor(floor_plan, mode=mode, service_provider=scope.get("service_provider"))
    summary = _cell_summary_from_queryset(queryset)
    if not summary:
        return f"I couldn't find live data for {_floor_label(floor_plan)} {mode.upper()}."

    rows = summary["cells"]
    points = {(row.cell_x, row.cell_y): (float(row.median_signal), int(row.scan_count)) for row in rows}
    confidence_map = {
        (row.cell_x, row.cell_y): compute_confidence(row.scan_count, getattr(row, "signal_variance", 0), row.updated_at)
        for row in rows
    }
    blocked_cells = {(cell_from_id(cell_id, floor_plan.grid_cols)) for cell_id in floor_plan.blocked_cell_ids()}
    best_score = -2.0
    best_cell = None
    for cell_y in range(floor_plan.grid_rows):
        for cell_x in range(floor_plan.grid_cols):
            score = score_cell(cell_x, cell_y, points, confidence_map, blocked_cells)
            if score > best_score:
                best_score = score
                best_cell = (cell_x, cell_y)

    if not best_cell:
        return "I couldn't identify a scan target right now."

    return (
        f"Recommended next scan for {_floor_label(floor_plan)} {mode.upper()} is cell {best_cell[0]},{best_cell[1]}. "
        f"It looks like the lowest-confidence spot in the current grid."
    )


def _answer_signal_variance(user, scope: dict[str, Any]) -> str:
    mode = scope.get("mode")
    if not mode:
        return _clarification_question(["mode"], "signal_variance")

    floor_plan = _floor_queryset_for_scope(user, scope)
    if floor_plan:
        queryset = _aggregate_queryset_for_floor(floor_plan, mode=mode, service_provider=scope.get("service_provider"))
        scope_desc = _floor_label(floor_plan)
    else:
        queryset = _aggregate_queryset_for_institution(user, mode=mode, service_provider=scope.get("service_provider"))
        scope_desc = _institution_name(scope)

    summary = _cell_summary_from_queryset(queryset)
    if not summary:
        return f"I couldn't find live data for {scope_desc}."

    top_variance = sorted(summary["cells"], key=lambda row: float(row.signal_variance or 0), reverse=True)[:5]
    if not top_variance:
        return f"I couldn't find enough live data to analyse variance for {scope_desc}."

    parts = [f"Signal variance for {scope_desc} is {_format_metric(summary['avg_variance'], 2)} on average."]
    parts.append("Highest-variance cells: " + ", ".join(
        f"{row.cell_x},{row.cell_y} ({_format_metric(float(row.signal_variance or 0), 2)})"
        for row in top_variance
    ))
    return " ".join(parts)


def _answer_trend(user, scope: dict[str, Any]) -> str:
    mode = scope.get("mode")
    if not mode:
        return _clarification_question(["mode"], "trend")

    floor_plan = _floor_queryset_for_scope(user, scope)
    if floor_plan:
        payload = build_trend_payload(
            block=floor_plan.block.code,
            floor=floor_plan.number,
            mode=mode,
            service_provider=scope.get("service_provider") or "",
            user=user,
        )
        points = payload.get("points") or []
        if not points:
            return f"I couldn't find a live trend for {_floor_label(floor_plan)}."
        first = next((point for point in points if point.get("avg_signal") is not None), None)
        last = next((point for point in reversed(points) if point.get("avg_signal") is not None), None)
        summary = payload.get("summary") or {}
        return (
            f"Trend for {_floor_label(floor_plan)} {mode.upper()}: "
            f"first tracked average {_format_metric(first['avg_signal'], 2) if first else '--'} dBm, "
            f"latest {_format_metric(last['avg_signal'], 2) if last else '--'} dBm, "
            f"{summary.get('total_scans', 0)} total scans."
        )

    recent_days = 14
    since = timezone.now() - timedelta(days=recent_days - 1)
    scans = Scan.objects.filter(created_at__gte=since)
    if scope.get("mode") in {Scan.WIFI, Scan.MOBILE}:
        scans = scans.filter(mode=scope["mode"])
    if scope.get("service_provider") and scope["service_provider"].lower() != "all":
        scans = scans.filter(service_provider=scope["service_provider"])

    registry = registry_for_user(user)
    allowed_floorplans = []
    for block in registry.get("blocks", []):
        for floor in registry.get("block_floors", {}).get(block, []):
            floor_plan = floor_plan_for_user(user, block, floor)
            if floor_plan:
                allowed_floorplans.append(floor_plan)
    scans = scans.filter(floor_plan__in=allowed_floorplans)
    if not scans.exists():
        return f"I couldn't find live trend data for {_institution_name(scope)}."

    buckets: dict[Any, list[float]] = defaultdict(list)
    for scan in scans.order_by("created_at"):
        buckets[scan.created_at.date()].append(float(scan.signal_strength))
    dates = sorted(buckets)
    first = mean(buckets[dates[0]])
    last = mean(buckets[dates[-1]])
    return (
        f"Trend for {_institution_name(scope)} {mode.upper()} shows an average signal shift from "
        f"{_format_metric(first, 2)} dBm to {_format_metric(last, 2)} dBm over the last {recent_days} days."
    )


def _answer_general_analytics(user, scope: dict[str, Any]) -> str:
    mode = scope.get("mode")
    if scope.get("scope_kind") == "institution":
        queryset = _aggregate_queryset_for_institution(user, mode=mode, service_provider=scope.get("service_provider"))
        scope_desc = _institution_name(scope)
    else:
        floor_plan = _floor_queryset_for_scope(user, scope)
        if not floor_plan:
            return "Please choose a block and floor so I can look that up."
        queryset = _aggregate_queryset_for_floor(floor_plan, mode=mode, service_provider=scope.get("service_provider"))
        scope_desc = _floor_label(floor_plan)

    summary = _cell_summary_from_queryset(queryset)
    if not summary:
        return f"I couldn't find live data for {scope_desc}."

    return (
        f"{scope_desc}: average signal {_format_metric(summary['avg_signal'], 2)} dBm, "
        f"{summary['weak_cells']} weak cells, {summary['strong_cells']} strong cells, "
        f"and {summary['scan_count']} scans."
    )


def _resolve_analytics_answer(request, message: str, history: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    if _is_general_greeting(message):
        _clear_pending_state(request)
        return {"mode": "general", "reset_state": True}

    if _is_app_info_question(message):
        _clear_pending_state(request)
        return _app_info_response(request.user)

    if not getattr(request.user, "is_authenticated", False):
        if _mentions_institution(message) or _analytics_intent(message):
            return _auth_required_response(message)

    pending = _pending_state(request)
    scope = _scope_from_payload(request.user, message, payload, pending_scope=pending.get("scope") if pending else None)
    intent = pending.get("intent") if pending else _analytics_intent(message)
    if not intent:
        _clear_pending_state(request)
        return {"mode": "general"}

    if intent == "institution_identity":
        return _institution_identity_response(request.user)

    if pending and pending.get("intent") and intent == pending.get("intent"):
        scope = _scope_from_payload(request.user, message, payload, pending_scope=pending.get("scope"))

    missing = _missing_scope_fields(intent, scope)
    if missing:
        response = _clarification_response(request.user, scope, missing, intent)
        _store_pending_state(request, response["state"])
        return response

    if intent in {"best_provider", "worst_provider"}:
        answer = _answer_best_or_worst_provider(request.user, scope, best=intent == "best_provider")
    elif intent == "average_signal":
        answer = _answer_average_signal(request.user, scope)
    elif intent == "weak_zones":
        answer = _answer_weak_or_strong_zones(request.user, scope, strong=False)
    elif intent == "strong_zones":
        answer = _answer_weak_or_strong_zones(request.user, scope, strong=True)
    elif intent == "comparison":
        answer = _answer_comparison(request.user, scope)
    elif intent == "scan_counts":
        answer = _answer_scan_counts(request.user, scope)
    elif intent == "coverage_quality":
        answer = _answer_coverage_quality(request.user, scope)
    elif intent == "missing_scan_recommendations":
        answer = _answer_missing_scan_recommendations(request.user, scope)
    elif intent == "signal_variance":
        answer = _answer_signal_variance(request.user, scope)
    elif intent == "trend":
        answer = _answer_trend(request.user, scope)
    else:
        answer = _answer_general_analytics(request.user, scope)

    _clear_pending_state(request)
    return {
        "mode": "analytics",
        "context_scope": "analytics",
        "answer": answer,
        "choices": [],
        "state": None,
    }


def route_chatbot_request(request, message: str, history: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    if not message:
        return {"mode": "general"}

    analytics = _resolve_analytics_answer(request, message, history, payload)
    return analytics

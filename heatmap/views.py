from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import html
import json
import re
import unicodedata
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import models
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from .aggregation import rebuild_aggregates_for_floor, refresh_cell_aggregates
from .chatbot import route_chatbot_request
from .models import CellAggregate, Scan, Block, Institution, InstitutionMembership, UserDashboardPreference
from .forms import SignupForm
from .services import (
    build_alerts_payload,
    build_comparison_payload,
    build_trend_payload,
    current_institution as service_current_institution,
    current_membership as service_current_membership,
    institution_for_user,
    institution_queryset_for_user,
    is_institution_admin as service_is_institution_admin,
    resolve_dashboard_selection,
    save_dashboard_preference,
    viewer_context as service_viewer_context,
    user_can_scan as service_user_can_scan,
    user_can_view_heatmap as service_user_can_view_heatmap,
)
from .utils import (
    compute_confidence,
    ensure_service_provider,
    cell_from_id,
    find_weak_clusters,
    get_floor_dimensions,
    get_floor_plan,
    get_floor_registry,
    get_service_providers,
    interpolate_missing_cells,
    is_blocked_cell,
    score_cell,
)

MAX_DOC_CONTEXT_CHARS = 12000
MAX_FLOOR_CONTEXT_CHARS = 8000
AI_RESPONSE_MAX_CHARS = 12000
SUPPORTED_MODES = {Scan.WIFI, Scan.MOBILE}
BRAND_WITH_NAME_PATH = Path(settings.BASE_DIR) / "logo-with-name.png"
BRAND_WITHOUT_NAME_PATH = Path(settings.BASE_DIR) / "logo-without-name.png"
GENERAL_ASSISTANT_SYSTEM_PROMPT = (
    "You are Spen Sense, a helpful general-purpose assistant for this website. "
    "Respond naturally and concisely. "
    "Do not claim to know project background, documentation, user accounts, or institution data unless the user explicitly provides that context. "
    "Never invent app details, institutional context, or live analytics. "
    "If the question depends on NetSense data, ask for the missing block, floor, mode, or provider details, or ask the user to sign in."
)
GENERAL_ASSISTANT_FALLBACK = (
    "I’m here to help with general questions. "
    "If you want NetSense analytics, sign in and share the block and floor."
)
_PROJECT_HALLUCINATION_PATTERNS = (
    r"netsense campus",
    r"project assistant",
    r"helps?\s+students\s+manage\s+their\s+time",
    r"study\s+or\s+take\s+breaks",
    r"schedules?\s+and\s+preferences",
    r"personal assistant for your productivity",
    r"working on helps? students",
)
_GREETING_MESSAGE_RE = re.compile(
    r"^(hi|hello|hey|hiya|hello there|hi there|hey there|hello dear)[\s!.?]*$",
    re.IGNORECASE,
)

STRICT_GENERAL_CHAT_PROMPT = (
    "You are Spen Sense, a general-purpose assistant for the NetSense Campus site. "
    "Answer naturally, clearly, and briefly. "
    "Never invent project background, documentation, institution details, user identity, or live analytics. "
    "If the user asks about NetSense data, rely only on explicit database-backed context provided by the application. "
    "If the answer is not available, ask for the missing block, floor, mode, provider, or sign-in instead of guessing. "
    "Do not mention being a documentation assistant."
)
STRICT_GENERAL_CHAT_HINTS = (
    "Use only the information in the conversation.",
    "Do not invent product, app, or institution details.",
    "Do not mention project documentation unless the user explicitly asks for it.",
    "If the user asks what this app does, keep the answer limited to the approved NetSense analytics summary provided by the application.",
    "If the user asks about NetSense data without enough context, ask a clarifying question.",
)
SAFE_GENERAL_FALLBACK = (
    "I'm here to help with general questions. "
    "If you want NetSense analytics, sign in and share the block and floor."
)

STRICT_GENERAL_CHAT_PROMPT = (
    "You are Spen Sense, a general-purpose assistant for the NetSense Campus site. "
    "Answer naturally, clearly, and briefly. "
    "Never invent project background, documentation, institution details, user identity, or live analytics. "
    "If the user asks about NetSense data, rely only on explicit database-backed context provided by the application. "
    "If the answer is not available, ask for the missing block, floor, mode, provider, or sign-in instead of guessing. "
    "Do not mention being a documentation assistant."
)
STRICT_GENERAL_CHAT_HINTS = (
    "Use only the information in the conversation.",
    "Do not invent product, app, or institution details.",
    "Do not mention project documentation unless the user explicitly asks for it.",
    "If the user asks what this app does, keep the answer limited to the approved NetSense analytics summary provided by the application.",
    "If the user asks about NetSense data without enough context, ask a clarifying question.",
)
SAFE_GENERAL_FALLBACK = (
    "I'm here to help with general questions. "
    "If you want NetSense analytics, sign in and share the block and floor."
)


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------


def _coerce_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\ufeff", "")

    replacements = {
        "â€‘": "-",
        "â€”": "-",
        "â€“": "-",
        "â†’": "->",
        "â€œ": '"',
        "â€": '"',
        "â€˜": "'",
        "â€™": "'",
        "Â": "",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # Remove control characters except common whitespace.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit("\n", 1)[0].strip() or text[:limit]


def _format_ai_answer(text: str) -> str:
    text = _normalize_text(text)
    if not text:
        return "No answer available."

    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        # Normalize excessive bullet styles into a consistent shape.
        line = re.sub(r"^[-*•]+\s*", "- ", line)
        line = re.sub(r"^(\d+)\)\s*", r"\1. ", line)

        # Promote simple labels into compact section headers.
        if line.endswith(":") and len(line) <= 80 and not line.startswith("-"):
            line = f"## {line[:-1]}"

        lines.append(line)

    formatted = "\n".join(lines).strip()
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)
    return _trim(formatted, AI_RESPONSE_MAX_CHARS)


def _looks_like_project_hallucination(text: str) -> bool:
    lowered = _normalize_text(text).lower()
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _PROJECT_HALLUCINATION_PATTERNS)


def _sanitize_general_assistant_answer(answer: str, message: str) -> str:
    cleaned = _format_ai_answer(answer)
    if not cleaned:
        return GENERAL_ASSISTANT_FALLBACK

    if _looks_like_project_hallucination(cleaned):
        if _GREETING_MESSAGE_RE.match(_normalize_text(message)):
            return "Hi! I’m Spen Sense. How can I help?"
        return GENERAL_ASSISTANT_FALLBACK

    return cleaned


def _safe_general_chat_answer(answer: str, message: str) -> str:
    cleaned = _format_ai_answer(answer)
    if not cleaned:
        return SAFE_GENERAL_FALLBACK

    if _looks_like_project_hallucination(cleaned):
        if _GREETING_MESSAGE_RE.match(_normalize_text(message)):
            return "Hi! I'm Spen Sense. How can I help?"
        return SAFE_GENERAL_FALLBACK

    return cleaned


def _build_general_chat_messages(message: str, history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": "\n".join((STRICT_GENERAL_CHAT_PROMPT, *STRICT_GENERAL_CHAT_HINTS)),
        }
    ]

    for item in (history or [])[-8:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role", "user")
        if role not in {"user", "assistant"}:
            role = "user"

        text = _normalize_text(str(item.get("text") or "")).strip()
        if not text:
            continue

        messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": _normalize_text(message).strip()})
    return messages


# -----------------------------------------------------------------------------
# Page context
# -----------------------------------------------------------------------------


def _viewer_context(user=None):
    return service_viewer_context(user)


def _approved_institutions(user):
    return institution_queryset_for_user(user)


def _current_membership(user):
    return service_current_membership(user)


def _current_institution(user):
    return service_current_institution(user)


def _is_institution_admin(user):
    return service_is_institution_admin(user)


def _user_can_scan(user):
    return service_user_can_scan(user)


def _user_can_view_heatmap(user):
    return service_user_can_view_heatmap(user)


def _filter_registry_for_user(user, registry):
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


def _user_can_access_floor(user, floor_plan):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if not floor_plan or not floor_plan.block_id:
        return False
    institution = institution_for_user(user)
    return bool(institution and floor_plan.block.institution_id == institution.id)


# -----------------------------------------------------------------------------
# Scan ingestion and validation
# -----------------------------------------------------------------------------


def _parse_scan_payload(request):
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST


def _validate_scan_payload(data, user=None):
    registry = get_floor_registry()
    registry = _filter_registry_for_user(user, registry)

    block = (data.get("block") or "").strip()
    floor = _coerce_int(data.get("floor"))
    cell_x = _coerce_int(data.get("cell_x"))
    cell_y = _coerce_int(data.get("cell_y"))
    signal_strength = _coerce_int(data.get("signal_strength"))
    mode = (data.get("mode") or Scan.WIFI).strip()
    service_provider = (data.get("service_provider") or "").strip() or "Unknown"
    network_name = (data.get("network_name") or "").strip()

    if floor is None or cell_x is None or cell_y is None or signal_strength is None:
        return None, "Invalid input. Ensure floor, cell and signal values are numeric."

    if block not in registry["blocks"]:
        return None, "Invalid block."

    if floor not in registry["block_floors"].get(block, []):
        return None, "Invalid floor."

    if mode not in SUPPORTED_MODES:
        return None, "Invalid mode."

    floor_dims = get_floor_dimensions(block, floor)
    rows = max(1, _coerce_int(floor_dims.get("rows"), 1) or 1)
    cols = max(1, _coerce_int(floor_dims.get("cols"), 1) or 1)

    if not (0 <= cell_x < cols):
        return None, "Cell X is out of range."

    if not (0 <= cell_y < rows):
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
        "cell_id": cell_y * cols + cell_x,
    }, None


# -----------------------------------------------------------------------------
# Page views
# -----------------------------------------------------------------------------


def home_view(request):
    return render(request, "heatmap/landing.html", _viewer_context(request.user))


@login_required
def heatmap_view(request):
    if not _user_can_view_heatmap(request.user):
        return HttpResponseForbidden("Approved institution access required.")
    return render(request, "heatmap/home.html", _viewer_context(request.user))


def dti_view(request):
    return render(request, "heatmap/dti.html", _viewer_context(request.user))


def project_structure_view(request):
    return render(request, "heatmap/project_structure.html", _viewer_context(request.user))


def data_models_view(request):
    return render(request, "heatmap/data_models.html", _viewer_context(request.user))


def workflow_view(request):
    return render(request, "heatmap/workflow.html", _viewer_context(request.user))


@login_required
def scan_view(request):
    if not _user_can_scan(request.user):
        return HttpResponseForbidden("Scan access required.")

    context = _viewer_context(request.user)
    if request.method == "POST":
        payload, error = _validate_scan_payload(request.POST, request.user)
        if error:
            messages.error(request, error)
            return redirect("scan")

        scan = Scan.objects.create(**payload)
        ensure_service_provider(scan.mode, scan.service_provider)
        refresh_cell_aggregates(scan)
        messages.success(request, "Scan saved.")
        return redirect("scan")

    return render(request, "heatmap/scan.html", context)


@login_required
def dashboard_preferences_view(request):
    if request.method != "POST":
        return HttpResponseForbidden("POST required.")

    selection = resolve_dashboard_selection(request.user)
    preset = (request.POST.get("dashboard_preset") or selection.preset or UserDashboardPreference.PRESET_MY_INSTITUTION).strip()
    selected_institution_id = request.POST.get("selected_institution")
    compare_block = (request.POST.get("compare_block") or "").strip()
    compare_floor = _coerce_int(request.POST.get("compare_floor"))
    weak_threshold = _coerce_int(request.POST.get("weak_threshold"), selection.weak_threshold)

    if preset == UserDashboardPreference.PRESET_MY_INSTITUTION and not selected_institution_id:
        current = service_current_institution(request.user)
        selected_institution_id = current.id if current else None

    save_dashboard_preference(
        request.user,
        selected_institution_id=selected_institution_id,
        dashboard_preset=preset,
        compare_block=compare_block,
        compare_floor=compare_floor,
        weak_threshold=weak_threshold,
    )

    if hasattr(request, "_messages"):
        messages.success(request, "Dashboard preferences updated.")
    return redirect("heatmap_view")


@login_required
def dashboard_insights_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)

    block = (request.GET.get("block") or "").strip()
    floor = _coerce_int(request.GET.get("floor"))
    mode = (request.GET.get("mode") or Scan.WIFI).strip()
    service_provider = (request.GET.get("service_provider") or "").strip()
    compare_block = (request.GET.get("compare_block") or "").strip()
    compare_floor = _coerce_int(request.GET.get("compare_floor"))
    weak_threshold = _coerce_int(request.GET.get("weak_threshold"), -80)

    if not block or floor is None:
        return JsonResponse({"error": "block and floor are required query params"}, status=400)

    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return JsonResponse({"error": "floor not configured"}, status=404)
    if not _user_can_access_floor(request.user, floor_plan):
        return JsonResponse({"error": "access denied"}, status=403)
    if compare_block and compare_floor is not None:
        compare_floor_plan = get_floor_plan(compare_block, compare_floor)
        if not compare_floor_plan:
            return JsonResponse({"error": "comparison floor not configured"}, status=404)
        if not _user_can_access_floor(request.user, compare_floor_plan):
            return JsonResponse({"error": "access denied"}, status=403)

    trend = build_trend_payload(
        block=block,
        floor=floor,
        mode=mode,
        service_provider=service_provider,
        user=request.user,
    )
    alerts = build_alerts_payload(
        block=block,
        floor=floor,
        mode=mode,
        service_provider=service_provider,
        weak_threshold=weak_threshold if weak_threshold is not None else -80,
        user=request.user,
    )
    comparison = build_comparison_payload(
        block=block,
        floor=floor,
        mode=mode,
        service_provider=service_provider,
        compare_block=compare_block or None,
        compare_floor=compare_floor,
        weak_threshold=weak_threshold if weak_threshold is not None else -80,
        user=request.user,
    )

    selection = resolve_dashboard_selection(request.user)
    return JsonResponse(
        {
            "trend": trend,
            "alerts": alerts,
            "comparison": comparison,
            "preset": selection.preset,
            "selected_institution": {
                "id": selection.institution.id if selection.institution else None,
                "name": selection.institution.name if selection.institution else "",
                "code": selection.institution.code if selection.institution else "",
            },
        }
    )


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("heatmap_view")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data.get("email", "")
            user.save()
            institution = form.cleaned_data["institution"]
            InstitutionMembership.objects.create(
                user=user,
                institution=institution,
                status=InstitutionMembership.PENDING,
                role=InstitutionMembership.MEMBER,
            )
            messages.success(request, "Account created. Await institution approval.")
            return redirect("login")
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})


@login_required
def institution_requests_view(request):
    if not _is_institution_admin(request.user):
        return HttpResponseForbidden("Institution admin access required.")

    if request.user.is_staff or request.user.is_superuser:
        admin_institutions = Institution.objects.filter(is_active=True)
    else:
        institution = _current_institution(request.user)
        admin_institutions = Institution.objects.filter(is_active=True, id=institution.id) if institution else Institution.objects.none()

    if request.method == "POST":
        membership_id = request.POST.get("membership_id")
        action = request.POST.get("action")
        membership = (
            InstitutionMembership.objects.select_related("institution", "user")
            .filter(id=membership_id, institution__in=admin_institutions)
            .first()
        )
        if not membership:
            messages.error(request, "Request not found.")
            return redirect("institution_requests")

        if action == "approve" or action == "approve_scan":
            already_approved = InstitutionMembership.objects.filter(
                user=membership.user,
                status=InstitutionMembership.APPROVED,
            ).exclude(id=membership.id)
            if already_approved.exists():
                messages.error(
                    request,
                    f"{membership.user.username} already belongs to another approved institution.",
                )
                return redirect("institution_requests")
            membership.status = InstitutionMembership.APPROVED
            membership.approved_at = timezone.now()
            if action == "approve_scan":
                membership.can_scan = True
                membership.save(update_fields=["status", "approved_at", "can_scan"])
            else:
                membership.save(update_fields=["status", "approved_at"])
            messages.success(request, f"Approved {membership.user.username}.")
        elif action == "reject":
            membership.status = InstitutionMembership.REJECTED
            membership.approved_at = None
            membership.save(update_fields=["status", "approved_at"])
            messages.success(request, f"Rejected {membership.user.username}.")
        else:
            messages.error(request, "Invalid action.")
        return redirect("institution_requests")

    pending = InstitutionMembership.objects.filter(
        status=InstitutionMembership.PENDING,
        institution__in=admin_institutions,
    ).select_related("user", "institution")

    return render(
        request,
        "heatmap/institution_requests.html",
        {
            "pending": pending,
        },
    )


# -----------------------------------------------------------------------------
# Heatmap query helpers
# -----------------------------------------------------------------------------


def _aggregate_queryset(floor_plan, mode: str | None = None, service_provider: str = ""):
    queryset = CellAggregate.objects.filter(floor_plan=floor_plan)
    if mode in SUPPORTED_MODES:
        queryset = queryset.filter(mode=mode)

    service_provider = (service_provider or "").strip()
    if not service_provider or service_provider.lower() == "all":
        queryset = queryset.filter(is_all_providers=True)
    else:
        queryset = queryset.filter(is_all_providers=False, service_provider=service_provider)

    return queryset


def _build_matrix_context(
    *,
    block: str,
    floor: int,
    mode: str,
    service_provider: str,
    include_matrix: bool = True,
):
    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return ""

    registry = get_floor_registry()
    floor_cfg = registry["floor_configs"].get(f"{block}:{floor}", {})
    rows = max(1, _coerce_int(floor_cfg.get("rows"), floor_plan.grid_rows) or floor_plan.grid_rows)
    cols = max(1, _coerce_int(floor_cfg.get("cols"), floor_plan.grid_cols) or floor_plan.grid_cols)
    blocked_cells = floor_cfg.get("blocked_cells") or []

    queryset = _aggregate_queryset(floor_plan, mode=mode, service_provider=service_provider)
    rows_data = list(queryset.order_by("cell_y", "cell_x"))

    if not rows_data:
        return (
            f"Selection:\n"
            f"- block: {block}\n"
            f"- floor: {floor}\n"
            f"- mode: {mode}\n"
            f"- provider: {(service_provider or 'all')}\n"
            f"- rows: {rows}\n"
            f"- cols: {cols}\n"
            f"No measured heatmap data is available for this selection."
        )

    signal_grid = [[None for _ in range(cols)] for _ in range(rows)]
    count_grid = [[0 for _ in range(cols)] for _ in range(rows)]
    measured_points = []

    signals = []
    counts = []
    for row in rows_data:
        if 0 <= row.cell_y < rows and 0 <= row.cell_x < cols:
            signal_grid[row.cell_y][row.cell_x] = round(float(row.median_signal), 2)
            count_grid[row.cell_y][row.cell_x] = int(row.scan_count)
        signals.append(float(row.median_signal))
        counts.append(int(row.scan_count))
        measured_points.append(
            {
                "cell_x": row.cell_x,
                "cell_y": row.cell_y,
                "signal": round(float(row.median_signal), 2),
                "count": int(row.scan_count),
            }
        )

    strong = [p for p in measured_points if p["signal"] >= -65]
    medium = [p for p in measured_points if -80 <= p["signal"] < -65]
    weak = [p for p in measured_points if p["signal"] < -80]
    weakest = sorted(measured_points, key=lambda p: p["signal"])[:6]
    strongest = sorted(measured_points, key=lambda p: p["signal"], reverse=True)[:6]

    matrix_lines = []
    if include_matrix:
        for y in range(rows):
            row_cells = []
            for x in range(cols):
                value = signal_grid[y][x]
                if value is None:
                    row_cells.append(".")
                else:
                    row_cells.append(f"{value:.1f}({count_grid[y][x]})")
            matrix_lines.append(f"R{y}: " + " | ".join(row_cells))

    summary = [
        "Selection:",
        f"- block: {block}",
        f"- floor: {floor}",
        f"- mode: {mode}",
        f"- provider: {(service_provider or 'all')}",
        f"- rows: {rows}",
        f"- cols: {cols}",
        "",
        "Summary:",
        f"- measured cells: {len(rows_data)}",
        f"- total scans: {sum(counts)}",
        f"- avg signal: {sum(signals) / len(signals):.2f} dBm",
        f"- min signal: {min(signals):.2f} dBm",
        f"- max signal: {max(signals):.2f} dBm",
        f"- strong cells (>= -65): {len(strong)}",
        f"- medium cells (-80 to -65): {len(medium)}",
        f"- weak cells (< -80): {len(weak)}",
        f"- blocked cells: {blocked_cells}",
        "",
        "Weakest cells:",
    ]

    for cell in weakest:
        summary.append(
            f"- ({cell['cell_x']}, {cell['cell_y']}) -> {cell['signal']:.2f} dBm, count {cell['count']}"
        )

    summary.extend([
        "",
        "Strongest cells:",
    ])
    for cell in strongest:
        summary.append(
            f"- ({cell['cell_x']}, {cell['cell_y']}) -> {cell['signal']:.2f} dBm, count {cell['count']}"
        )

    if include_matrix and matrix_lines:
        summary.extend(["", "Signal matrix (signal(count)):"])
        summary.extend(matrix_lines)

    return _trim("\n".join(summary), MAX_FLOOR_CONTEXT_CHARS)


# -----------------------------------------------------------------------------
# Heatmap API
# -----------------------------------------------------------------------------


def heatmap_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)

    block = (request.GET.get("block") or "").strip()
    floor = _coerce_int(request.GET.get("floor"))
    mode = (request.GET.get("mode") or Scan.WIFI).strip()
    service_provider = (request.GET.get("service_provider") or "").strip()
    interpolate = (request.GET.get("interpolate", "1") or "1").strip() != "0"

    if not block or floor is None:
        return JsonResponse({"error": "block and floor are required query params"}, status=400)

    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return JsonResponse({"error": "floor not configured"}, status=404)
    if not _user_can_access_floor(request.user, floor_plan):
        return JsonResponse({"error": "access denied"}, status=403)

    queryset = _aggregate_queryset(floor_plan, mode=mode, service_provider=service_provider)

    if not queryset.exists():
        rebuild_aggregates_for_floor(floor_plan, mode=mode if mode in SUPPORTED_MODES else None)
        queryset = _aggregate_queryset(floor_plan, mode=mode, service_provider=service_provider)

    payload = [
        {
            "cell_x": row.cell_x,
            "cell_y": row.cell_y,
            "signal": round(float(row.median_signal), 2),
            "count": int(row.scan_count),
            "confidence": compute_confidence(
                row.scan_count,
                getattr(row, "signal_variance", 0),
                row.updated_at,
            ),
            "interpolated": False,
        }
        for row in queryset.order_by("cell_y", "cell_x")
    ]

    if interpolate:
        registry = get_floor_registry()
        floor_cfg = registry["floor_configs"].get(f"{block}:{floor}", {})
        rows = max(1, _coerce_int(floor_cfg.get("rows"), floor_plan.grid_rows) or floor_plan.grid_rows)
        cols = max(1, _coerce_int(floor_cfg.get("cols"), floor_plan.grid_cols) or floor_plan.grid_cols)
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


def weak_clusters_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)

    block = (request.GET.get("block") or "").strip()
    floor = _coerce_int(request.GET.get("floor"))
    mode = (request.GET.get("mode") or Scan.WIFI).strip()
    service_provider = (request.GET.get("service_provider") or "").strip()
    threshold = _coerce_int(request.GET.get("threshold"), -80)

    if not block or floor is None:
        return JsonResponse({"error": "block and floor are required query params"}, status=400)

    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return JsonResponse({"error": "floor not configured"}, status=404)
    if not _user_can_access_floor(request.user, floor_plan):
        return JsonResponse({"error": "access denied"}, status=403)

    queryset = _aggregate_queryset(floor_plan, mode=mode, service_provider=service_provider)
    if not queryset.exists():
        rebuild_aggregates_for_floor(floor_plan, mode=mode if mode in SUPPORTED_MODES else None)
        queryset = _aggregate_queryset(floor_plan, mode=mode, service_provider=service_provider)

    points = {}
    for row in queryset:
        points[(row.cell_x, row.cell_y)] = (float(row.median_signal), int(row.scan_count))

    clusters = []
    for cluster in find_weak_clusters(points, threshold=threshold):
        signals = [points[(x, y)][0] for x, y in cluster if (x, y) in points]
        avg_signal = sum(signals) / len(signals) if signals else 0
        clusters.append(
            {
                "size": len(cluster),
                "avg_signal": round(float(avg_signal), 2),
                "cells": [[x, y] for x, y in cluster],
            }
        )

    return JsonResponse({"clusters": clusters})


def best_provider_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)

    block = (request.GET.get("block") or "").strip()
    floor = _coerce_int(request.GET.get("floor"))
    mode = (request.GET.get("mode") or Scan.WIFI).strip()

    if not block or floor is None:
        return JsonResponse({"error": "block and floor are required query params"}, status=400)

    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return JsonResponse({"error": "floor not configured"}, status=404)
    if not _user_can_access_floor(request.user, floor_plan):
        return JsonResponse({"error": "access denied"}, status=403)

    queryset = CellAggregate.objects.filter(
        floor_plan=floor_plan,
        mode=mode if mode in SUPPORTED_MODES else Scan.WIFI,
        is_all_providers=False,
    )

    if not queryset.exists():
        rebuild_aggregates_for_floor(floor_plan, mode=mode if mode in SUPPORTED_MODES else None)
        queryset = CellAggregate.objects.filter(
            floor_plan=floor_plan,
            mode=mode if mode in SUPPORTED_MODES else Scan.WIFI,
            is_all_providers=False,
        )

    best_by_cell = {}
    for row in queryset:
        key = (row.cell_x, row.cell_y)
        existing = best_by_cell.get(key)
        if not existing or row.median_signal > existing["signal"]:
            best_by_cell[key] = {
                "cell_x": row.cell_x,
                "cell_y": row.cell_y,
                "best_provider": row.service_provider or "Unknown",
                "signal": round(float(row.median_signal), 2),
            }

    return JsonResponse({"cells": list(best_by_cell.values())})




def next_scan_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)

    block = (request.GET.get("block") or "").strip()
    floor = _coerce_int(request.GET.get("floor"))
    mode = (request.GET.get("mode") or Scan.WIFI).strip()
    service_provider = (request.GET.get("service_provider") or "").strip()

    if not block or floor is None:
        return JsonResponse({"error": "block and floor are required query params"}, status=400)

    floor_plan = get_floor_plan(block, floor)
    if not floor_plan:
        return JsonResponse({"error": "floor not configured"}, status=404)
    if not _user_can_access_floor(request.user, floor_plan):
        return JsonResponse({"error": "access denied"}, status=403)

    registry = get_floor_registry()
    floor_cfg = registry["floor_configs"].get(f"{block}:{floor}", {})
    rows = max(1, _coerce_int(floor_cfg.get("rows"), floor_plan.grid_rows) or floor_plan.grid_rows)
    cols = max(1, _coerce_int(floor_cfg.get("cols"), floor_plan.grid_cols) or floor_plan.grid_cols)
    blocked_cells = floor_cfg.get("blocked_cells") or []
    blocked = set()
    for item in blocked_cells:
        if isinstance(item, (int, str)):
            try:
                blocked.add(cell_from_id(int(item), cols))
            except (TypeError, ValueError):
                continue
            continue
        if isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                blocked.add((int(item[0]), int(item[1])))
            except (TypeError, ValueError):
                continue
            continue
        if isinstance(item, dict):
            if "cell_x" in item and "cell_y" in item:
                try:
                    blocked.add((int(item["cell_x"]), int(item["cell_y"])))
                except (TypeError, ValueError):
                    continue
            elif "cell_id" in item:
                try:
                    blocked.add(cell_from_id(int(item["cell_id"]), cols))
                except (TypeError, ValueError):
                    continue

    queryset = _aggregate_queryset(floor_plan, mode=mode, service_provider=service_provider)
    if not queryset.exists():
        rebuild_aggregates_for_floor(floor_plan, mode=mode if mode in SUPPORTED_MODES else None)
        queryset = _aggregate_queryset(floor_plan, mode=mode, service_provider=service_provider)

    points = {}
    confidence_map = {}
    for row in queryset:
        key = (row.cell_x, row.cell_y)
        points[key] = (row.median_signal, row.scan_count)
        confidence_map[key] = compute_confidence(
            row.scan_count,
            getattr(row, "signal_variance", 0),
            row.updated_at,
        )

    best_score = -2.0
    best_cell = None
    for cell_y in range(rows):
        for cell_x in range(cols):
            score = score_cell(cell_x, cell_y, points, confidence_map, blocked)
            if score > best_score:
                best_score = score
                best_cell = (cell_x, cell_y)

    if not best_cell:
        return JsonResponse({"error": "no available cells"}, status=404)

    return JsonResponse({"cell_x": best_cell[0], "cell_y": best_cell[1]})


# -----------------------------------------------------------------------------
# Config API
# -----------------------------------------------------------------------------


def config_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)

    registry = _filter_registry_for_user(request.user, get_floor_registry())
    return JsonResponse(
        {
            "blocks": registry["blocks"],
            "block_floors": registry["block_floors"],
            "floor_configs": registry["floor_configs"],
            "service_providers": get_service_providers(),
        }
    )


# -----------------------------------------------------------------------------
# Scan API
# -----------------------------------------------------------------------------


@csrf_exempt
def scan_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)
    if not _user_can_scan(request.user):
        return JsonResponse({"error": "scan access required"}, status=403)

    data = _parse_scan_payload(request)
    payload, error = _validate_scan_payload(data, request.user)
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


# -----------------------------------------------------------------------------
# PWA endpoints
# -----------------------------------------------------------------------------


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
    response = HttpResponse(content, content_type="application/javascript; charset=utf-8")
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
      "src": "/brand/logo-without-name.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/brand/logo-without-name.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    }
  ]
}
"""
    response = HttpResponse(content, content_type="application/manifest+json; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response


def _brand_file_response(path: Path, content_type: str = "image/png"):
    if not path.exists():
        return HttpResponse(status=404)
    response = FileResponse(path.open("rb"), content_type=content_type)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


def brand_logo_with_name(_request):
    return _brand_file_response(BRAND_WITH_NAME_PATH)


def brand_logo_without_name(_request):
    return _brand_file_response(BRAND_WITHOUT_NAME_PATH)


# -----------------------------------------------------------------------------
# AI context loading
# -----------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _docs_context():
    root = Path(settings.BASE_DIR)
    candidate_files = [
        root / "README.md",
        root / "PROJECT_MANUAL.md",
        root / "PROJECT_DOCUMENTATION.md",
        root / "PROJECT_STRUCTURE.md",
        root / "DATA_MODELS_AND_APIS.md",
        root / "WORKFLOW_STEPS.md",
        root / "DTI_ARCHITECTURE.md",
    ]

    chunks = []
    for path in candidate_files:
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        content = _normalize_text(content)
        if content:
            chunks.append(f"# {path.name}\n{content}")

    if not chunks:
        return "No internal documentation context was found."

    return _trim("\n\n".join(chunks), MAX_DOC_CONTEXT_CHARS)


def _extract_floor_scope(payload: dict[str, Any] | None):
    if not isinstance(payload, dict):
        return None

    heatmap = payload.get("heatmap") or {}
    if not isinstance(heatmap, dict):
        return None

    block = (heatmap.get("block") or "").strip()
    floor = _coerce_int(heatmap.get("floor"))
    mode = (heatmap.get("mode") or Scan.WIFI).strip()
    service_provider = (heatmap.get("service_provider") or "").strip()

    if not block or floor is None:
        return None
    if mode not in SUPPORTED_MODES:
        mode = Scan.WIFI

    return {
        "block": block,
        "floor": floor,
        "mode": mode,
        "service_provider": service_provider,
    }


def _floor_context_for_ai(scope: dict[str, Any] | None) -> str:
    if not scope:
        return ""

    block = scope.get("block")
    floor = scope.get("floor")
    mode = scope.get("mode", Scan.WIFI)
    service_provider = scope.get("service_provider", "")

    if block is None or floor is None:
        return ""

    context = _build_matrix_context(
        block=block,
        floor=floor,
        mode=mode,
        service_provider=service_provider,
        include_matrix=True,
    )
    return context


# -----------------------------------------------------------------------------
# LLM calls
# -----------------------------------------------------------------------------


def _require_groq_key():
    key = getattr(settings, "GROQ_API_KEY", "") or ""
    if not key:
        raise ImproperlyConfigured("GROQ_API_KEY is not configured.")
    return key


def _post_json(url, headers, body):
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    print("\n========== API REQUEST ==========")
    print("URL:", url)
    print("Headers:", {k: ("***" if k.lower() == "authorization" else v) for k, v in headers.items()})
    print("=================================\n")

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read()
            text = raw.decode("utf-8")

            print("\n========== API SUCCESS ==========")
            print(text[:2000])
            print("=================================\n")

            return json.loads(text), None

    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            error_body = "Unable to read error body."

        print("\n========== HTTP ERROR ==========")
        print("Status:", exc.code)
        print("Reason:", exc.reason)
        print("Body:", error_body)
        print("================================\n")

        return None, error_body

    except urllib.error.URLError as exc:
        print("\n========== URL ERROR ==========")
        print(repr(exc))
        print("================================\n")

        return None, f"Unable to reach upstream API: {exc}"

    except Exception as exc:
        print("\n========== UNKNOWN ERROR ==========")
        print(repr(exc))
        print("===================================\n")

        return None, str(exc)

def _build_chat_prompt(
    message: str,
    docs_context: str,
    floor_context: str,
    history: list[dict[str, Any]] | None,
):
    history_lines = []

    for item in (history or [])[-6:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role", "user")

        text = _normalize_text(
            str(item.get("text") or "")
        ).strip()

        if not text:
            continue

        history_lines.append(
            f"{role}: {text}"
        )

    sections = [
        GENERAL_ASSISTANT_SYSTEM_PROMPT,
        "",
        "Answer naturally and conversationally.",
        "Keep answers concise unless asked otherwise.",
        "",
    ]

    if docs_context:
        sections.extend([
            "PROJECT DOCUMENTATION:",
            docs_context,
            "",
        ])

    if floor_context:
        sections.extend([
            "FLOOR DATA:",
            floor_context,
            "",
        ])

    if history_lines:
        sections.extend([
            "CHAT HISTORY:",
            "\n".join(history_lines),
            "",
        ])

    sections.extend([
        f"USER: {message}",
        "",
        "ASSISTANT:",
    ])

    return "\n".join(sections)


def _call_ollama(message: str, history: list[dict[str, Any]] | None):
    base_url = (getattr(settings, "OLLAMA_BASE_URL", "") or "").strip()
    model = (getattr(settings, "OLLAMA_MODEL", "") or "").strip()

    if not base_url or not model:
        return None, "Ollama not configured."

    print("\n========== OLLAMA MODEL ==========")
    print(model)
    print("==================================\n")

    url = f"{base_url.rstrip('/')}/api/chat"
    messages = _build_general_chat_messages(message, history)

    payload = {
        "model": model,
        "messages": messages,
        "options": {
            "temperature": 0.0,
            "top_p": 0.1,
            "repeat_penalty": 1.05,
            "num_predict": 256,
        },
        "stream": False,
    }

    print("\n========== OLLAMA PROMPT ==========")
    print(json.dumps(messages, ensure_ascii=False)[:3000])
    print("===================================\n")

    data, error = _post_json(
        url,
        {"Content-Type": "application/json"},
        payload,
    )

    if error:
        return None, error

    try:
        response = (
            data.get("message", {})
            .get("content", "")
        )

        response = _normalize_text(str(response))

        if not response:
            return None, "Empty Ollama response."

        return response, None

    except Exception as exc:
        return None, str(exc)


def _call_groq(message: str, history: list[dict[str, Any]] | None):
    api_key = _require_groq_key()

    api_url = getattr(
        settings,
        "GROQ_API_URL",
        "https://api.groq.com/openai/v1/chat/completions",
    )

    model = getattr(
        settings,
        "GROQ_MODEL",
        "llama-3.1-8b-instant",
    )

    print("\n========== GROQ CONFIG ==========")
    print("API KEY EXISTS:", bool(api_key))
    print("API KEY PREFIX:", api_key[:10] if api_key else "NONE")
    print("MODEL:", model)
    print("URL:", api_url)
    print("=================================\n")

    messages_payload = _build_general_chat_messages(message, history)

    payload = {
        "model": model,
        "messages": messages_payload,
        "temperature": 0.0,
        "top_p": 0.1,
        "max_tokens": 512,
    }

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")

        print("\n========== GROQ RAW RESPONSE ==========")
        print(raw[:2000])
        print("=======================================\n")

        data = json.loads(raw)

        response_text = data["choices"][0]["message"]["content"]
        response_text = _normalize_text(str(response_text))

        if not response_text:
            return None, "Empty Groq response."

        return response_text, None

    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            body = "Unable to read error body"

        print("\n========== GROQ HTTP ERROR ==========")
        print("STATUS:", exc.code)
        print("BODY:", body)
        print("=====================================\n")

        return None, body

    except urllib.error.URLError as exc:
        print("\n========== GROQ URL ERROR ==========")
        print(repr(exc))
        print("====================================\n")

        return None, str(exc)

    except Exception as exc:
        print("\n========== GROQ UNKNOWN ERROR ==========")
        print(repr(exc))
        print("========================================\n")

        return None, str(exc)# -----------------------------------------------------------------------------
# Chatbot API
# -----------------------------------------------------------------------------


def chatbot_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    content_type = request.headers.get("Content-Type", "")
    if "application/json" not in content_type:
        return JsonResponse(
            {"error": "Content-Type must be application/json"},
            status=415,
        )

    try:
        payload = json.loads(
            request.body.decode("utf-8") or "{}"
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "invalid JSON"},
            status=400,
        )

    if not isinstance(payload, dict):
        payload = {}

    message = _normalize_text(
        str(payload.get("message") or "")
    ).strip()

    history = (
        payload.get("history")
        if isinstance(payload.get("history"), list)
        else []
    )

    if not message:
        return JsonResponse(
            {"error": "message required"},
            status=400,
        )

    try:
        routed = route_chatbot_request(request, message, history, payload)
    except Exception:
        routed = {
            "mode": "general",
            "context_scope": "general",
            "answer": "I'm having trouble connecting right now. Please try again.",
            "choices": [{"label": "Help me get started", "message": "What is this app for?"}],
        }

    if not isinstance(routed, dict):
        routed = {"mode": "general", "context_scope": "general"}

    if routed.get("reset_state"):
        return JsonResponse(
            {
                "answer": "Hi! I'm Spen Sense. Ask me a question anytime.",
                "context_scope": "general",
                "choices": routed.get("choices") or [],
            }
        )
    if routed.get("mode") in {"analytics", "auth"}:
        answer = routed.get("answer") or ""
        if answer:
            return JsonResponse(
                {
                    "answer": _format_ai_answer(str(answer)),
                    "choices": routed.get("choices") or [],
                    "context_scope": routed.get("context_scope") or routed.get("mode") or "analytics",
                }
            )

    try:
        answer, error = _call_ollama(message, history)
    except Exception as exc:
        answer, error = None, str(exc)

    if not answer:
        try:
            answer, error = _call_groq(
                message,
                history,
            )

        except ImproperlyConfigured as exc:
            return JsonResponse(
                {"error": str(exc)},
                status=500,
            )

        except Exception as exc:
            return JsonResponse(
                {"error": str(exc)},
                status=502,
            )

    if not answer:
        return JsonResponse(
            {
                "answer": SAFE_GENERAL_FALLBACK,
                "context_scope": "general",
            }
        )

    answer = _safe_general_chat_answer(answer, message)

    return JsonResponse(
        {
            "answer": answer,
            "context_scope": "general",
        }
    )


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
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from .aggregation import rebuild_aggregates_for_floor, refresh_cell_aggregates
from .models import CellAggregate, Scan
from .utils import (
    ensure_service_provider,
    get_floor_dimensions,
    get_floor_plan,
    get_floor_registry,
    get_service_providers,
    interpolate_missing_cells,
    is_blocked_cell,
)

MAX_DOC_CONTEXT_CHARS = 12000
MAX_FLOOR_CONTEXT_CHARS = 8000
AI_RESPONSE_MAX_CHARS = 12000
SUPPORTED_MODES = {Scan.WIFI, Scan.MOBILE}


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


# -----------------------------------------------------------------------------
# Page context
# -----------------------------------------------------------------------------


def _viewer_context():
    registry = get_floor_registry()
    blocks = registry["blocks"]
    block_floors = registry["block_floors"]
    floor_configs = registry["floor_configs"]

    initial_block = blocks[0] if blocks else ""
    floors = block_floors.get(initial_block, [])
    initial_floor = floors[0] if floors else ""
    initial_cfg = floor_configs.get(f"{initial_block}:{initial_floor}", {})

    return {
        "blocks": blocks,
        "floors": floors,
        "initial_block": initial_block,
        "initial_floor": initial_floor,
        "grid_rows": max(1, _coerce_int(initial_cfg.get("rows"), settings.HEATMAP_GRID_ROWS) or settings.HEATMAP_GRID_ROWS),
        "grid_cols": max(1, _coerce_int(initial_cfg.get("cols"), settings.HEATMAP_GRID_COLS) or settings.HEATMAP_GRID_COLS),
        "block_floors": block_floors,
        "floor_configs": floor_configs,
        "service_providers": get_service_providers(),
        "modes": Scan.MODE_CHOICES,
    }


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


def _validate_scan_payload(data):
    registry = get_floor_registry()

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
    return render(request, "heatmap/landing.html", _viewer_context())


@login_required
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
    if not request.user.is_staff:
        return HttpResponseForbidden("Admin access required.")

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


# -----------------------------------------------------------------------------
# Config API
# -----------------------------------------------------------------------------


def config_api(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)

    registry = get_floor_registry()
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
    response = HttpResponse(content, content_type="application/manifest+json; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    return response


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
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8")
        except Exception:
            error_body = "Upstream API error."
        return None, error_body
    except urllib.error.URLError:
        return None, "Unable to reach upstream API."
    except json.JSONDecodeError:
        return None, "Invalid upstream response."


def _build_chat_prompt(message: str, docs_context: str, floor_context: str, history: list[dict[str, Any]] | None):
    instructions = [
        "You are NetSense Campus AI.",
        "Answer only from the provided internal documentation and the current floor context.",
        "Do not invent schema, fields, endpoints, or data structures.",
        "If a floor context is present, use only that floor's matrix and summary data for operational interpretation.",
        "If the answer is not present in the provided material, say that it is not available in the current context.",
        "Keep the output neat, concise, and structured.",
        "Use short headings and bullet points when helpful.",
        "Do not emit mojibake, stray symbols, or random unicode artifacts.",
    ]

    history_lines = []
    for item in (history or [])[-6:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user")
        text = _normalize_text(str(item.get("text") or "")).strip()
        if not text:
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        history_lines.append(f"{role.title()}: {text}")

    sections = [
        "\n".join(instructions),
        "",
        "Internal documentation:",
        docs_context,
        "",
        "Current floor context:",
        floor_context or "No floor context selected.",
        "",
        "Recent conversation:",
        "\n".join(history_lines) if history_lines else "No prior conversation.",
        "",
        f"User message: {message}",
        "",
        "Answer:",
    ]
    return "\n".join(sections)


def _call_ollama(prompt: str):
    base_url = (getattr(settings, "OLLAMA_BASE_URL", "") or "").strip()
    model = (getattr(settings, "OLLAMA_MODEL", "") or "").strip()
    if not base_url or not model:
        return None, "Ollama not configured."

    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    data, error = _post_json(url, {"Content-Type": "application/json"}, payload)
    if error:
        return None, error

    response = data.get("response", "") if isinstance(data, dict) else ""
    response = _normalize_text(str(response))
    if not response:
        return None, "Empty Ollama response."
    return response, None


def _call_groq(prompt: str, history: list[dict[str, Any]] | None):
    api_key = _require_groq_key()
    api_url = getattr(settings, "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
    model = getattr(settings, "GROQ_MODEL", "llama-3.1-70b-versatile")

    messages_payload = [
        {
            "role": "system",
            "content": (
                "You are NetSense Campus AI. Use only the provided documentation and floor context. "
                "Do not invent data structures. Keep the answer neat and grounded in the actual system."
            ),
        }
    ]

    for item in (history or [])[-6:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user")
        text = _normalize_text(str(item.get("text") or "")).strip()
        if not text:
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        messages_payload.append({"role": role, "content": text})

    messages_payload.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages_payload,
        "temperature": 0.2,
    }
    data, error = _post_json(
        api_url,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        payload,
    )
    if error:
        return None, error

    try:
        response = data["choices"][0]["message"]["content"]
        response = _normalize_text(str(response))
        if not response:
            return None, "Empty Groq response."
        return response, None
    except (KeyError, IndexError, AttributeError, TypeError):
        return None, "Invalid Groq response."


# -----------------------------------------------------------------------------
# Chatbot API
# -----------------------------------------------------------------------------


@csrf_exempt
def chatbot_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    message = _normalize_text(str(payload.get("message") or "")).strip()
    history = payload.get("history") or []

    if not message:
        return JsonResponse({"error": "message required"}, status=400)

    docs_context = _docs_context()
    floor_scope = _extract_floor_scope(payload)
    floor_context = _floor_context_for_ai(floor_scope)

    # Floor context is only attached when the caller is actually working with a floor.
    # Otherwise, the AI stays on documentation-only context.
    prompt = _build_chat_prompt(message, docs_context, floor_context, history)

    answer, error = _call_ollama(prompt)
    if not answer:
        try:
            answer, error = _call_groq(prompt, history)
        except ImproperlyConfigured as exc:
            return JsonResponse({"error": str(exc)}, status=500)

    if not answer:
        return JsonResponse({"error": error or "Unable to generate response."}, status=502)

    answer = _format_ai_answer(answer)
    return JsonResponse(
        {
            "answer": answer,
            "context_scope": "floor" if floor_context else "docs_only",
        }
    )

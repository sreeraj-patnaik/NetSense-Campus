






# NetSense Campus (NSC) - Documentation

**Document purpose:** Single authoritative, implementation-level reference for the **nsc** repository: architecture, directory layout, Django modules, HTTP APIs, data model, every aggregation/interpolation/rendering formula, client behavior, management commands, and operational notes.

**Last updated:** 2026-04-06
**Stack:** Django 5.x, SQLite or PostgreSQL (via `DATABASE_URL`), WhiteNoise, Gunicorn (production), optional Cloudinary media storage, PWA shell.

---

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [Repository layout](#2-repository-layout)
3. [Runtime architecture](#3-runtime-architecture)
4. [URL routing (project + app)](#4-url-routing-project--app)
5. [Configuration (`netsense/settings.py`)](#5-configuration-netsensesettingspy)
6. [Data model (authoritative)](#6-data-model-authoritative)
7. [Grid indexing and blocked cells](#7-grid-indexing-and-blocked-cells)
8. [Registry and floor resolution (`heatmap/utils.py`)](#8-registry-and-floor-resolution-heatmaputilspy)
9. [Scan ingestion (web + API)](#9-scan-ingestion-web--api)
10. [Aggregation (`heatmap/aggregation.py`)](#10-aggregation-heatmapaggregationpy)
11. [Interpolation (`interpolate_missing_cells`)](#11-interpolation-interpolate_missing_cells)
12. [Heatmap API (`heatmap_api`)](#12-heatmap-api-heatmap_api)
13. [Config API](#13-config-api)
14. [Frontend: heatmap viewer (`static/heatmap/js/home.js`)](#14-frontend-heatmap-viewer-staticheatmapjshomejs)
15. [Frontend: scan UI (`static/heatmap/js/scan.js`)](#15-frontend-scan-ui-staticheatmapjsscanjs)
16. [Templates and injected config](#16-templates-and-injected-config)
17. [Django admin](#17-django-admin)
18. [Management commands](#18-management-commands)
19. [Security and auth](#19-security-and-auth)
20. [Edge cases and behavioral notes](#20-edge-cases-and-behavioral-notes)
21. [Deployment (Render + media)](#21-deployment-render--media)
22. [Migration history (conceptual)](#22-migration-history-conceptual)
23. [End-to-end walkthrough](#23-end-to-end-walkthrough)

---

## 1. Executive summary

**NetSense Campus** is a minimal Django application that:

- Accepts **Wiâ€‘Fi** and **mobile** signal samples on a **per-floor grid** (`cell_x`, `cell_y`).
- Persists raw rows as **`Scan`** records.
- Maintains **`CellAggregate`** rows: **median** signal strength and **scan count** per cell, per mode, for (a) a specific **service provider** and (b) an **â€œall providersâ€** bucket.
- Serves **`GET /api/heatmap/`** with optional **distance-weighted interpolation** for empty, non-blocked cells.
- Renders a **browser heatmap** (radial blend or contour bands) with **dynamic min/max scaling**, optional **confidence overlay**, and distinct coloring for **interpolated** vs **measured** cells.

---

## 2. Repository layout

Project root (conceptual; excludes `.venv`, `__pycache__`, collected static):

```
nsc/
  manage.py
  requirements.txt
  render.yaml
  README.md
  expdoc.md
  db.sqlite3                    # local default DB if no DATABASE_URL
  media/                        # user uploads (floor images); see SERVE_MEDIA_FILES
    floor_maps/
  static/
    manifest.webmanifest
    heatmap/
      css/style.css
      js/home.js
      js/scan.js
      js/pwa.js
      js/landing.js
      images/                     # e.g. Floor 1.jpeg, floor-placeholder.svg
      icons/                      # PWA icons (svg)
  templates/
    base.html
    heatmap/home.html
    heatmap/scan.html
    heatmap/landing.html
    registration/login.html
  netsense/                     # Django project package
    settings.py
    urls.py
    wsgi.py
    asgi.py
  heatmap/                      # Main application
    models.py
    views.py
    urls.py
    utils.py
    aggregation.py
    admin.py
    migrations/
      0007_service_provider.py
    management/commands/
      seed_demo_data.py
      rebuild_aggregates.py
```

---

## 3. Runtime architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”     POST /api/scan/      â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Android / HTTP      â”‚ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–º â”‚ Scan row         â”‚
â”‚ client              â”‚                          â”‚ refresh_cell_*     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                          â”‚ CellAggregate    â”‚
         â”‚                                         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚ GET /api/heatmap/                                 â–²
         â–¼                                                 â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   optional interpolate    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Browser (home.js)â”‚ â—„â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ â”‚ heatmap_api            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                           â”‚ + interpolate_missing â”‚
                                              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

- **Authoritative grid dimensions** and **blocked cell IDs** for each block/floor come from **`FloorPlan`** when present; otherwise **`HEATMAP_*`** settings in `settings.py` supply fallback blocks/floors/dimensions/blocked lists.

---

## 4. URL routing (project + app)

**`netsense/urls.py`**

| Path | View | Notes |
|------|------|--------|
| `admin/` | Django admin | |
| `` (empty) | `include("heatmap.urls")` | App mounted at site root |
| `login/` | `LoginView` | Template: `registration/login.html` |
| `logout/` | `LogoutView` | |
| `MEDIA_URL` | `static()` when `SERVE_MEDIA_FILES` | Local media in dev / when enabled |

**`heatmap/urls.py`**

| Path | Name | View | Auth |
|------|------|------|------|
| `` | `home` | `home_view` | Public |
| `sw.js` | `service_worker` | `service_worker` | Public |
| `heatmap/` | `heatmap_view` | `heatmap_view` | Public |
| `scan/` | `scan` | `scan_view` | **`@login_required`** |
| `api/heatmap/` | `heatmap_api` | `heatmap_api` | Public (JSON) |
| `api/scan/` | `scan_api` | `scan_api` | Public; **`@csrf_exempt`** |
| `api/config/` | `config_api` | `config_api` | Public (JSON) |

**Resolved URLs (typical dev):**

- Landing: `http://127.0.0.1:8000/`
- Heatmap UI: `http://127.0.0.1:8000/heatmap/`
- Scan UI: `http://127.0.0.1:8000/scan/` (login required)
- APIs: `/api/heatmap/`, `/api/scan/`, `/api/config/`

---

## 5. Configuration (`netsense/settings.py`)

### 5.1 Environment helpers

- **`env_bool(name, default=False)`** â€” treats `"1"`, `"true"`, `"yes"`, `"on"` (case-insensitive) as true.

### 5.2 Core Django

| Variable | Source | Role |
|----------|--------|------|
| `SECRET_KEY` | `DJANGO_SECRET_KEY` or dev default | Cryptographic signing |
| `DEBUG` | `DJANGO_DEBUG` (default true) | Debug mode |
| `ALLOWED_HOSTS` | **Hardcoded list** in file | Includes `127.0.0.1`, `localhost`, `.onrender.com`, `netsense.sreeraj.me` |
| `CSRF_TRUSTED_ORIGINS` | Hardcoded | HTTPS Render + custom domain |
| `DATABASES` | `DATABASE_URL` â†’ `dj_database_url` if set; else SQLite at `BASE_DIR / "db.sqlite3"` | |
| `STATIC_URL`, `STATICFILES_DIRS`, `STATIC_ROOT` | | WhiteNoise manifest storage |
| `MEDIA_URL`, `MEDIA_ROOT` | | Uploads under `media/` |
| `SERVE_MEDIA_FILES` | `DJANGO_SERVE_MEDIA` (default follows `DEBUG`) | Whether `urls.py` serves media |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | env | Enables Cloudinary media storage |
| `STORAGES["default"]` | code | Cloudinary storage when env vars set, filesystem otherwise |

### 5.3 Auth redirects

- `LOGIN_URL = "/login/"`
- `LOGIN_REDIRECT_URL = "/scan/"`
- `LOGOUT_REDIRECT_URL = "/"`

### 5.4 NetSense heatmap defaults (`HEATMAP_*`)

Used when **no active `FloorPlan` rows** exist (see `get_floor_registry()`), and as numeric fallbacks elsewhere.

| Setting | Default (as in repo) | Meaning |
|---------|----------------------|---------|
| `HEATMAP_BLOCKS` | `["A", "B", "C"]` | Block codes in fallback registry |
| `HEATMAP_FLOORS` | `[1, 2, 3, 4]` | Floor numbers per block in fallback |
| `HEATMAP_GRID_ROWS` | `12` | Default rows |
| `HEATMAP_GRID_COLS` | `8` | Default cols |
| `HEATMAP_FLOOR_DIMENSIONS` | Per-floor `{rows, cols}` | Overrides rows/cols per floor number in fallback |
| `HEATMAP_SERVICE_PROVIDERS` | `wifi` / `mobile` lists | Validation + UI dropdowns |
| `HEATMAP_BLOCKED_CELLS` | `{}` | Optional `{"A:1": [...]}` or `{"1": [...]}` cell ID lists |

### 5.5 Production HTTPS (when `DEBUG` is false)

- `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, HSTS, secure session/CSRF cookies.

**Note:** `README.md` / `render.yaml` mention env vars like `DJANGO_ALLOWED_HOSTS`; **`settings.py` does not read them** â€” hosts are edited in code unless extended.

---

## 6. Data model (authoritative)

All in **`heatmap/models.py`**.

### 6.1 `Block`

| Field | Type | Notes |
|-------|------|--------|
| `code` | `CharField(max_length=20, unique=True)` | Short identifier, e.g. `A` |
| `name` | `CharField(max_length=120, blank=True)` | |
| `is_active` | `BooleanField(default=True)` | Inactive blocks excluded from registry |

**Ordering:** `code`.

### 6.2 `ServiceProvider`

| Field | Type | Notes |
|-------|------|--------|
| `name` | `CharField(max_length=60)` | Provider label |
| `mode` | `CharField(choices WIFI/MOBILE)` | `wifi` or `mobile` |
| `is_active` | `BooleanField(default=True)` | Filters default lists |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**Constraint:** `UniqueConstraint(mode, name)` - no duplicates per mode.

### 6.3 `FloorPlan`

| Field | Type | Notes |
|-------|------|--------|
| `block` | `ForeignKey(Block)` | CASCADE |
| `number` | `PositiveIntegerField` | Floor number |
| `name` | `CharField(blank=True)` | Display |
| `grid_rows`, `grid_cols` | `PositiveIntegerField` | Default 12 / 8 |
| `blocked_cells` | `JSONField(default=list)` | See Â§7 |
| `image` | `ImageField(upload_to="floor_maps/", blank=True)` | Stored under `MEDIA_ROOT` |
| `is_active` | `BooleanField(default=True)` | |

**Constraint:** `UniqueConstraint(block, number)` â€” one plan per block floor.

### 6.4 `Scan` (raw sample)

| Field | Type | Notes |
|-------|------|--------|
| `floor_plan` | `FK(FloorPlan)` | Replaces legacy block/floor strings |
| `cell_x`, `cell_y` | `IntegerField` | 0-based grid indices |
| `cell_id` | `IntegerField` | **Auto-set in `save()`** from `cell_y * grid_cols + cell_x` |
| `mode` | `CharField(choices WIFI/MOBILE)` | `wifi` or `mobile` |
| `service_provider` | `CharField(max_length=60, blank=True)` | Empty treated as **Unknown** in aggregation |
| `network_name` | `CharField(blank=True)` | SSID / label |
| `signal_strength` | `IntegerField` | **dBm** (typically negative) |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**Indexes:** `(floor_plan, mode)`, `(cell_x, cell_y)`, `(cell_id)`.

**`save()` override:** If `floor_plan_id` is set, `cell_id = cell_y * floor_plan.grid_cols + cell_x` (all cast to `int`).

### 6.5 `CellAggregate`

| Field | Type | Notes |
|-------|------|--------|
| `floor_plan` | FK | |
| `cell_x`, `cell_y`, `cell_id` | ints | `cell_id` from `cell_to_id()` in aggregation |
| `mode` | WIFI/MOBILE | |
| `service_provider` | string | **Empty string** when `is_all_providers=True` |
| `is_all_providers` | bool | **True** = bucket over all providers for that cell/mode |
| `median_signal` | `FloatField` | Python `statistics.median` |
| `scan_count` | `PositiveIntegerField` | Number of scans in that bucket |
| `updated_at` | `auto_now` | |

**Unique constraint:** `(floor_plan, cell_x, cell_y, mode, service_provider, is_all_providers)`.

**Indexes:** `(floor_plan, mode, is_all_providers)`, `(cell_x, cell_y)`, `(cell_id)`.

---

## 7. Grid indexing and blocked cells

### 7.1 `cell_id` formula

For grid width `cols` (`grid_cols`):

```
cell_id = cell_y * cols + cell_x
```

**Inverse** (`cell_from_id`):

```
cell_x = cell_id % cols
cell_y = cell_id // cols
```

### 7.2 `FloorPlan.blocked_cell_ids()`

Iterates `blocked_cells` JSON and normalizes each entry to an integer `cell_id`:

| Entry shape | Handling |
|-------------|----------|
| `int` | Used as-is |
| `str` | `int()` if possible; else skipped |
| `[x, y]` length 2 | `cell_y * cols + cell_x` |
| `dict` with `cell_id` | `int(cell_id)` |
| `dict` with `cell_x`, `cell_y` | `cell_y * cols + cell_x` |

**Note:** `cols = int(self.grid_cols or 1)` to avoid division issues.

### 7.3 `is_blocked_cell(block, floor, cell_x, cell_y)`

- Loads `floor_configs[f"{block}:{floor}"]["blocked_cells"]` from registry.
- Builds `cell_id = cell_y * cols + cell_x` with `cols` from that floor config.
- Returns whether `cell_id` is in the `set` of blocked IDs.

---

## 8. Registry and floor resolution (`heatmap/utils.py`)

### 8.1 `get_floor_registry()`

**When `FloorPlan` rows exist** (`is_active=True`, `block__is_active=True`), ordered by `block__code`, `number`:

- **`blocks`:** ordered list of distinct block codes.
- **`block_floors[block]`:** list of floor **numbers** for that block.
- **`floor_configs[f"{block_code}:{floor.number}"]`:**
  - `rows` = `max(1, grid_rows)`
  - `cols` = `max(1, grid_cols)`
  - `image_url` = `floor.image.url` or `""`
  - `floor_name` = `name` or `"Floor {number}"`
  - **`blocked_cells`** = `floor.blocked_cell_ids()` (list of ints)

**When no active floors exist**, fallback from settings:

- For each `HEATMAP_BLOCKS` Ã— `HEATMAP_FLOORS`, same key structure with `_settings_floor_dims(floor_number)` and `HEATMAP_BLOCKED_CELLS` lookups (`"block:floor"` or `str(floor)`).

### 8.2 `get_floor_dimensions(block, floor)`

Returns `{rows, cols}` from registry or `_settings_floor_dims`.

### 8.3 `get_floor_plan(block_code, floor_number)`

Returns first **`FloorPlan`** with `block__code`, `number`, `is_active`, `block__is_active`, with `select_related("block")`, else `None`.

### 8.4 `ensure_floor_plan(block_code, floor_number)` (commands)

- `get_or_create(Block)` by `code`.
- If no `FloorPlan`, creates one using `get_floor_dimensions` and `HEATMAP_BLOCKED_CELLS` for initial `blocked_cells`.

### 8.5 `get_service_providers()`

Returns `{ "wifi": [...], "mobile": [...] }` from **ServiceProvider** rows when available, with `HEATMAP_SERVICE_PROVIDERS` as a fallback/seed list.

### 8.6 `ensure_service_provider(mode, name)`

On successful scan save, creates the provider if it does not exist yet. This keeps the provider lists fresh without manual admin entry.

---

## 9. Scan ingestion (web + API)

### 9.1 Payload parsing (`_parse_scan_payload`)

- If `Content-Type` starts with `application/json`, body is `json.loads`; invalid JSON â†’ `{}`.
- Else uses `request.POST` (form).

### 9.2 Validation (`_validate_scan_payload`)

Steps in order:

1. Read: `block`, `floor`, `mode`, `service_provider`, `network_name`, `signal_strength`, `cell_x`, `cell_y`.
2. **Coerce to int:** `floor`, `signal_strength`, `cell_x`, `cell_y`. Failure â†’ *"Invalid input. Ensure floor, cell and signal values are numeric."*
3. **`block`** must be in `registry["blocks"]` â†’ *"Invalid block."*
4. **`floor`** must be in `registry["block_floors"][block]` â†’ *"Invalid floor."*
5. **`mode`** must be `wifi` or `mobile` â†’ *"Invalid mode."*
6. **Service provider:** if empty/whitespace -> **`"Unknown"`**. No strict list validation; provider names are created on save.
7. **Bounds:** `0 <= cell_x < cols`, `0 <= cell_y < rows` using `get_floor_dimensions`.
8. **`is_blocked_cell`** â†’ *"Selected cell is blocked."*
9. **`get_floor_plan(block, floor)`** must exist â†’ *"Floor plan is not configured."*

**Success payload** (used for `Scan.objects.create`):

- `floor_plan`, `mode`, `service_provider`, `network_name`, `signal_strength`, `cell_x`, `cell_y`, `cell_id` (precomputed as `cell_y * cols + cell_x`).

**Note:** `Scan.save()` recomputes `cell_id` from `floor_plan.grid_cols` anyway; the validated `cell_id` should match.

### 9.3 Web: `scan_view`

- GET: render `heatmap/scan.html` with `_viewer_context()`.
- POST: validate `request.POST` (not JSON), create `Scan`, ensure provider exists, `refresh_cell_aggregates(scan)`, flash success, redirect to `scan`.

### 9.4 API: `scan_api`

- **405** if not POST.
- Uses `_parse_scan_payload` (supports JSON).
- **400** JSON `{"error": "<message>"}` on validation failure.
- **200** on success:

```json
{
  "status": "ok",
  "scan_id": <int>,
  "block": "<block_code>",
  "floor": <floor_number>,
  "cell_x": <int>,
  "cell_y": <int>
}
```

---

## 10. Aggregation (`heatmap/aggregation.py`)

### 10.1 `_median(values)`

- Uses `statistics.median` from the Python standard library.
- Empty list â†’ `None` (callers only pass non-empty lists in current code).
- Return type cast to **`float`**.

**Even count behavior:** median is the **mean of the two middle values** (per Python 3 `statistics.median`).

### 10.2 `_upsert_aggregate(...)`

Parameters: `floor_plan`, `cell_x`, `cell_y`, `mode`, `service_provider`, `is_all_providers`, `signal_values` (non-empty list).

- `cell_id = cell_to_id(cell_x, cell_y, floor_plan.grid_cols)`.
- `CellAggregate.objects.update_or_create(...)` with unique fields + `defaults`: `median_signal`, `scan_count=len(signal_values)`, `cell_id`.

### 10.3 `refresh_cell_aggregates(scan)` â€” **atomic transaction**

After one new `Scan`:

1. **Provider bucket:** all `Scan` rows for same `floor_plan`, `mode`, **`service_provider` or `"Unknown"`** (normalized: `scan.service_provider or "Unknown"`), same `cell_x`, `cell_y`. Collect `signal_strength` values â†’ upsert with `is_all_providers=False`, `service_provider=<that string>`.

2. **All-providers bucket:** all `Scan` rows for same `floor_plan`, `mode`, same cell, **any** `service_provider` â†’ upsert with `is_all_providers=True`, `service_provider=""`.

So each ingest updates **two** aggregates per cell/mode (if both buckets have data).

### 10.4 `rebuild_aggregates_for_floor(floor_plan, mode=None)`

- Filters scans to `floor_plan`; optionally to `wifi` or `mobile`.
- **Deletes** existing `CellAggregate` for that floor (optionally filtered by `mode`).
- Single pass over scans: builds `grouped` dict:
  - Key `(cell_x, cell_y, mode, provider, False)` â€” `provider = scan.service_provider or "Unknown"` â€” appends signal.
  - Key `(cell_x, cell_y, mode, "", True)` â€” appends signal for **all-providers** bucket.
- For each group, `_upsert_aggregate`.

**Use:** repair after bulk imports, `seed_demo_data`, or when API finds no aggregates.

---

## 11. Interpolation (`interpolate_missing_cells`)

**Location:** `heatmap/utils.py`.

**Signature:** `interpolate_missing_cells(*, points, rows, cols, blocked_cells, max_distance=2)`.

### 11.1 Inputs

- **`points`:** `dict` mapping `(cell_x, cell_y)` â†’ `(signal, count)` for **measured** cells (typically from aggregates).
- **`rows`, `cols`:** grid size for the nested loops.
- **`blocked_cells`:** iterable of **cell_id** integers (must match registry normalization).
- **`max_distance`:** Chebyshev window radius default **2** (loops `dx, dy âˆˆ [-2,2]` excluding `(0,0)`).

### 11.2 Early exit

If `points` is empty â†’ return `[]` (no interpolation).

### 11.3 Per-cell algorithm

For each `(cell_x, cell_y)` in `range(rows) Ã— range(cols)`:

1. Skip if `cell_id = cell_y * cols + cell_x` is in **`blocked`** (from `blocked_cells`).
2. Skip if `(cell_x, cell_y)` **already in `points`**.
3. Collect **neighbors** within the Manhattan/square window: for each offset `(dx,dy)` not `(0,0)`, if in bounds and `(nx,ny)` exists in `points`:
   - `distance_sq = dx*dx + dy*dy` (Euclidean squared distance in grid steps).
   - `signal, count = points[(nx,ny)]`
   - **Weight:**

```
weight = (1 / distance_sq) * max(1.0, (count or 1) ** 0.5)
```

So: **inverse-square** in grid space, times **at least 1**, times **âˆš(count)** when count â‰¥ 1 (since `max(1, sqrt(count))` for count â‰¥ 1).

4. If no neighbors â†’ skip cell (no fill).
5. Else:

```
interpolated_signal = sum(signal_i * weight_i) / sum(weight_i)
```

Rounded to **2 decimal places** in output.

6. Append `{ cell_x, cell_y, signal, count: 0, interpolated: true }`.

**Important:** Interpolated cells do **not** enter `points` during the same run (single pass); chained interpolation through newly filled cells is **not** performed.

---

## 12. Heatmap API (`heatmap_api`)

**Method:** GET only (implicit).

### 12.1 Query parameters

| Param | Required | Default | Behavior |
|-------|----------|---------|----------|
| `block` | Yes | â€” | Block code |
| `floor` | Yes | â€” | Integer floor number |
| `mode` | No | `wifi` | If `wifi` or `mobile`, filter aggregates |
| `service_provider` | No | `""` | Empty or **`all`** (case-insensitive) â†’ **`is_all_providers=True`**; else specific provider, `is_all_providers=False` |
| `interpolate` | No | **on** | Any value **â‰ ** trimmed `"0"` enables interpolation |

### 12.2 Errors

| Condition | Status | Body |
|-----------|--------|------|
| Missing `block` or `floor` | 400 | `{"error": "block and floor are required query params"}` |
| `floor` not int | 400 | `{"error": "floor must be an integer"}` |
| No `FloorPlan` | 404 | `{"error": "floor not configured"}` |

### 12.3 Aggregate query and auto-rebuild

1. Filter `CellAggregate` by `floor_plan` and `mode` (if valid).
2. Filter by provider bucket (all vs specific).
3. If **`.exists()` is False**, call **`rebuild_aggregates_for_floor(floor_plan, mode=mode)`**, then **re-run the same filters** (repair path).

### 12.4 Response shape (JSON array)

Each element:

```json
{
  "cell_x": <int>,
  "cell_y": <int>,
  "signal": <float rounded 2dp>,
  "count": <int>,
  "interpolated": false
}
```

Order: `order_by("cell_y", "cell_x")`.

`median_signal` is **`round(row.median_signal, 2)`** in Python.

### 12.5 Interpolation branch

If `interpolate` is true:

- `rows`, `cols` from `floor_configs[f"{block}:{floor}"]` with fallback to `floor_plan.grid_rows/grid_cols`.
- `blocked_cells` from same floor config (or `[]`).
- Build `points` dict from **current payload only** (measured cells).
- **`extend`** list with `interpolate_missing_cells(..., max_distance=2)`.

**Result:** JSON array = **measured cells first**, then **interpolated** entries (each with `interpolated: true`). Client may dedupe by cell if needed; typically measured wins if both existed â€” server does not duplicate measured cells in interpolation.

### 12.6 Mode filter edge case

If `mode` is **not** `wifi` or `mobile`, the queryset **does not** filter by mode (string mismatch). Clients should only send valid modes.

---

## 13. Config API

**`GET /api/config/`** returns JSON:

```json
{
  "blocks": [...],
  "block_floors": { "<block>": [<floor numbers>] },
  "floor_configs": { "<block>:<floor>": { "rows", "cols", "image_url", "floor_name", "blocked_cells" } },
  "service_providers": { "wifi": [...], "mobile": [...] }
}
```

Same structure as used by server-rendered templates for the heatmap/scan pages.

---

## 14. Frontend: heatmap viewer (`static/heatmap/js/home.js`)

### 14.1 Config (`window.NETSENSE_CONFIG`)

Injected in `heatmap/home.html`: `rows`, `cols`, `defaultFloorImage`, `heatmapApiUrl`, `blockFloors`, `floorConfigs`, `serviceProviders`.

### 14.2 Data fetch

- URL: `heatmapApiUrl` + `URLSearchParams`: `block`, `floor`, `mode`, `interpolate` (`1` or `0`), optional `service_provider` (only if provider dropdown has a value â€” **All** uses `all` value which triggers server-side all-providers bucket).

### 14.3 Scaling

- `realPoints = points.filter(p => !p.interpolated)`
- `scalePoints = realPoints.length ? realPoints : points` (if only interpolated exists, scale from them)
- `minSignal = min(signals)`, `maxSignal = max(signals)`
- `range = max(1, maxSignal - minSignal)` â€” **avoids division by zero**
- Normalized: `normalized = clamp01((point.signal - minSignal) / range)` where `clamp01` = [0,1]

Legend shows **one decimal**: `minSignal.toFixed(1)`, `maxSignal.toFixed(1)`.

### 14.4 Render modes

- **`smooth` (Blended):** radial gradient from center to `radius`, alpha falloff to 0 at edge.
- **`contour`:** `banded = round(normalized * 6) / 6` â€” **7 bands** (0, 1/6, â€¦, 1). Filled **circle** (not gradient) with radius `max(cellWidth, cellHeight) * 0.9`.

### 14.5 Colors

- **Measured:** `colorRamp(t)` â€” red `[209,52,52]` â†’ yellow `[240,196,33]` â†’ green `[34,163,74]` at t=0, 0.5, 1.
- **Interpolated:** `colorRampInterpolated(t)` â€” blue/cyan palette.

### 14.6 Alpha and â€œspreadâ€

- Base alpha: **0.2** interpolated, **0.6** measured.
- `countBoost = min(1, sqrt(point.count || 1) / 6)` â†’ `alpha = clamp01(alphaBase + countBoost * 0.2)`.

**Auto smooth:**

```
density = realPoints.length / max(1, rows * cols)
autoSpread = 2.2 - min(1, density * 2.2) * 1.1
```

Capped behavior: higher density â†’ lower spread multiplier. Manual spread: range input **0.8â€“2.4**, step **0.1**, default **1.6**; `max(0.6, value)`.

**Radius:** `max(cellWidth, cellHeight) * spreadMultiplier` (smooth) or `* 0.9` (contour).

### 14.7 Confidence overlay

When enabled: `maxCount = max(1, ...realPoints counts)`; per real point, `confidence = clamp01(count / maxCount)`, fill rect for cell with `rgba(17,24,39, 0.35 * confidence)`.

### 14.8 Layout

- Canvas sized to `mapWrap` bounding rect; resize listener refetches draw.
- Grid lines via CSS `repeating-linear-gradient` on `#gridLayer`.

---

## 15. Frontend: scan UI (`static/heatmap/js/scan.js`)

- Click map -> computes `cellX`, `cellY` from click position / cell size; rejects blocked cells using **`floorCfg.blocked_cells` as Set of cell_ids** (same `cell_y * cols + cell_x` formula).
- Hidden inputs `cell_x`, `cell_y` submitted with form; **required** in HTML.
- Provider input uses a **datalist** sourced from provider registry; free text allowed.
- **Auto Scan** (mobile-only UI): attempts to infer **Wi-Fi vs Mobile** using `navigator.connection` and updates mode + provider input.
- Resize redraws selection marker.

---

## 16. Templates and injected config

| Template | Script | Purpose |
|----------|--------|---------|
| `heatmap/landing.html` | `landing.js` | IntersectionObserver reveal animations |
| `heatmap/home.html` | `home.js` | Heatmap viewer + `NETSENSE_CONFIG` |
| `heatmap/scan.html` | `scan.js` | Admin scan + `NETSENSE_SCAN_CONFIG` |
| `registration/login.html` | (Django auth) | Login form |

**`_viewer_context()`** (in `views.py`) supplies: `blocks`, `floors` (for initial block), `initial_block`, `initial_floor`, `grid_rows`, `grid_cols`, `block_floors`, `floor_configs`, `service_providers`, `modes`.

---

## 17. Django admin

**`heatmap/admin.py`**

- **BlockAdmin:** inlines `FloorPlan`; list/filter/search on code/name/active.
- **FloorPlanAdmin:** grid, blocked JSON, image + preview.
- **ScanAdmin**, **CellAggregateAdmin:** list/filter for debugging and data cleanup.
- **ServiceProviderAdmin:** manage provider preferences (wifi/mobile lists).

---

## 18. Management commands

### 18.1 `seed_demo_data`

| Argument | Default | Effect |
|----------|---------|--------|
| `--per-floor` | **500** | Random scans per block/floor (help text in code may say 24; **code default is 500**) |
| `--clear` | false | `Scan.objects.all().delete()` first |

Logic: for each block/floor, `ensure_floor_plan`, random `mode`, provider from settings or Unknown, random cell skipping blocked, `signal_strength` uniform **-95..-35**, then `bulk_create`, then **`rebuild_aggregates_for_floor`** per floor.

### 18.2 `rebuild_aggregates`

Iterates registry blocks/floors, `ensure_floor_plan`, `rebuild_aggregates_for_floor` for each.

---

## 19. Security and auth

| Surface | CSRF | Auth |
|---------|------|------|
| `/scan/` POST | **Required** (form token) | Login required |
| `/api/scan/` | **Exempt** | None (any client can POST) |
| `/api/heatmap/`, `/api/config/` | GET only | Public |

**Operational implication:** Protect `/api/scan/` at the network layer (API keys, firewall, reverse proxy) if exposed on the public internet.

---

## 20. Edge cases and behavioral notes

1. **Single measured point:** `minSignal == maxSignal` â†’ `range` forced to **1** â†’ normalized 0.5 mid-ramp unless exactly at bounds.
2. **No aggregates until first scan:** API rebuilds from `Scan` if queryset empty.
3. **Provider "Unknown":** Explicit string used in per-provider aggregates; empty `service_provider` on scan becomes **Unknown** in aggregation filters.
4. **Interpolation:** Does not fill blocked cells; does not use cells without neighbors within `max_distance`.
5. **Invalid `mode` on API:** May return aggregates for both modes or unintended filter behavior â€” always send `wifi` or `mobile`.
6. **`cell_id` consistency:** Must use same `cols` as floor for indexing; `Scan.save()` overwrites `cell_id` using `floor_plan.grid_cols`.

---

## 21. Deployment (Render + media)

- **`render.yaml`:** Python 3.12.8, `collectstatic`, migrate + gunicorn, `DJANGO_DEBUG=false`, `DJANGO_SERVE_MEDIA=true`, generated secret.
- **Static:** WhiteNoise `CompressedManifestStaticFilesStorage`.
- **Media:** Cloudinary is supported via env vars (`CLOUDINARY_*`) and is recommended for production persistence.
- **PWA:** `manifest.webmanifest` and `/sw.js` enable installable mobile app shell (online-only).

---

## 22. Migration history (conceptual)

Early migrations introduced `Scan` with inline block/floor; later migrations added **`Block`**, **`FloorPlan`**, **`CellAggregate`**, **`service_provider`**, and **`floor_plan` FK** on `Scan` (replacing denormalized block/floor). See `heatmap/migrations/` for exact operations.

---

## 23. End-to-end walkthrough

1. Admin creates **Block** `A` and **FloorPlan** for floor **1** with `grid_rows=12`, `grid_cols=8`, optional image and `blocked_cells`.
2. Client **POST** `/api/scan/` with JSON body: `block=A`, `floor=1`, `cell_x=3`, `cell_y=2`, `mode=wifi`, `service_provider=CampusNet`, `network_name=SSID`, `signal_strength=-72`.
3. Server validates, creates **Scan**; `cell_id = 2*8+3 = 19`; `refresh_cell_aggregates` updates **CampusNet** bucket and **all-providers** bucket for that cell.
4. **GET** `/api/heatmap/?block=A&floor=1&mode=wifi&service_provider=all&interpolate=1` returns measured cells plus interpolated empty cells (excluding blocked), signals rounded to 2 decimals.
5. Browser **home.js** fetches array, computes min/max, draws radial gradients; interpolated points use blue ramp and lower base alpha.

---

*End of ExpDoc.*



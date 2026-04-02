NetSense Campus (NSC)

Full Project Manual and Technical Reference

Version: 1.0  
Document date: 2026-04-01  
Software stack: Django 5.x, SQLite or PostgreSQL, WhiteNoise, Gunicorn

---

## How to use this document in Microsoft Word

This file is **Markdown** (`.md`). Word opens it cleanly in recent versions:

1. In Word: **File → Open**, choose `PROJECT_MANUAL.md`, confirm conversion if prompted.
2. Or use **Pandoc** (optional): `pandoc PROJECT_MANUAL.md -o PROJECT_MANUAL.docx` then open the `.docx`.
3. After import, apply **Heading 1 / Heading 2** styles if your converter did not map `#` and `##` automatically.
4. Tables and code blocks are preserved; widen table columns in Word if needed.

Conventions: **Bold** highlights terms; `monospace` is code, paths, or API names. This manual is self-contained for reviewers who may not read the source tree.

---

## Table of contents

1. [Abstract](#1-abstract)  
2. [Introduction](#2-introduction)  
3. [Problem, solution, and scope](#3-problem-solution-and-scope)  
4. [Glossary](#4-glossary)  
5. [System architecture](#5-system-architecture)  
6. [Repository structure](#6-repository-structure)  
7. [Configuration and environment](#7-configuration-and-environment)  
8. [Data model and design rationale](#8-data-model-and-design-rationale)  
9. [Grid indexing and blocked cells](#9-grid-indexing-and-blocked-cells)  
10. [Floor registry and utilities](#10-floor-registry-and-utilities)  
11. [Scan ingestion](#11-scan-ingestion)  
12. [Aggregation logic](#12-aggregation-logic)  
13. [Interpolation](#13-interpolation)  
14. [Heatmap API](#14-heatmap-api)  
15. [Config API](#15-config-api)  
16. [Web user interfaces](#16-web-user-interfaces)  
17. [Django administration](#17-django-administration)  
18. [Management commands](#18-management-commands)  
19. [Security and authentication](#19-security-and-authentication)  
20. [Edge cases and limitations](#20-edge-cases-and-limitations)  
21. [Installation and local development](#21-installation-and-local-development)  
22. [Demonstration workflow](#22-demonstration-workflow)  
23. [Deployment](#23-deployment)  
24. [Database migration history (conceptual)](#24-database-migration-history-conceptual)  
25. [End-to-end scenario](#25-end-to-end-scenario)  
26. [Appendices](#26-appendices)  

---

## 1. Abstract

**NetSense Campus (NSC)** is a web application that makes **indoor radio signal quality** visible on a **floor plan**. The system collects **Wi‑Fi** and **cellular (mobile)** signal samples aligned to a **discrete grid** over each building floor. Raw measurements are stored as **Scan** records. For each grid cell, the application maintains **CellAggregate** rows that store the **median** signal strength (in dBm) and a **scan count**, both for a specific **service provider** and for an **all providers** combined view.

The server exposes a **heatmap API** that returns per-cell values and, optionally, **interpolated** estimates for cells that have no direct measurements. Interpolation uses **inverse distance weighting** on the grid, respects **blocked** cells (walls, voids), and does not chain through synthetic values in a single pass. A **browser-based viewer** renders the data with **dynamic scaling**, optional **confidence shading**, and two visual modes: **blended** (radial gradients) and **contour** (quantized bands). A separate **authenticated scan page** and a **machine-facing scan API** support data entry from staff or external clients (for example, Android scanners).

The implementation is intentionally **small and maintainable**: one primary Django app (`heatmap`), minimal URL surface, configuration through Django **settings** with **database-backed overrides** for blocks, floors, grids, and floor images. This manual explains **what** each part does and **why** design choices were made, then documents **APIs**, **algorithms**, **deployment**, and **operations** in detail suitable for academic or industry handover.

---

## 2. Introduction

### 2.1 Background

Indoor wireless performance is difficult to reason about from a single number at the router or tower. **Dead zones**, **interference**, and **building materials** create spatial patterns that vary by floor and room. A **spatially indexed** measurement model (grid cells over a map) allows facilities and IT teams to **see** where signal is weak, compare **Wi‑Fi** versus **mobile**, and compare **carriers** or **SSIDs** consistently.

### 2.2 Objectives

- Capture **repeatable** samples tied to **building block**, **floor**, and **grid cell**.  
- Reduce noise in displayed values by using **median** aggregation rather than a single last sample.  
- Support **provider-specific** and **combined** views without duplicating raw data beyond aggregates.  
- Offer **gap filling** via interpolation while **visually distinguishing** estimated cells from measured ones.  
- Keep deployment **simple** (single Django project, standard SQL database, static assets via WhiteNoise).

### 2.3 Audience

This document serves **developers**, **operators**, and **technical reviewers** who need enough detail to extend the system, deploy it, or evaluate its behavior without reading every source file line by line.

---

## 3. Problem, solution, and scope

### 3.1 Problem

Stakeholders need answers to: *Where is coverage weak?* *Does mobile or Wi‑Fi fail first?* *Which carrier is usable in this lab?* Raw spreadsheets of dBm readings are hard to map to physical space. A **heatmap on a floor image** answers these questions quickly.

### 3.2 Solution approach

1. **Discretize** the floor into a **rows × cols** grid.  
2. **Record** signal strength (dBm) when a user or device marks a cell.  
3. **Aggregate** multiple readings per cell with a **robust statistic** (median).  
4. **Serve** JSON for clients and draw **color-mapped** overlays in the browser.  
5. **Estimate** missing cells only where **nearby** evidence exists, and label estimates clearly.

### 3.3 In scope

- Django models, views, URLs, aggregation, interpolation, and front-end rendering behavior described in this repository.  
- Local development, Render-oriented deployment notes, and environment variables **actually read** by `netsense/settings.py`.

### 3.4 Out of scope (current MVP)

- Real-time push updates (the heatmap **polls** via fetch on user actions and resize).  
- User accounts per scanner (only **staff login** for the web scan page; API scan is unauthenticated by design but should be protected externally if exposed).  
- Automatic calibration of floor images to real-world coordinates (grid is **abstract** relative to the image).  
- 3D or multi-floor interpolation across vertical space.

---

## 4. Glossary

| Term | Meaning |
|------|---------|
| **Block** | A building or wing identifier (for example `A`, `B`). |
| **Floor plan** | Database row linking a block to a floor number, grid size, optional image, and blocked cells. |
| **Cell** | One element of the grid, addressed by `cell_x`, `cell_y` (origin typically top-left in UI math). |
| **cell_id** | Single integer index `cell_y * cols + cell_x` for compact storage and blocked-cell lists. |
| **Mode** | `wifi` or `mobile` scan type. |
| **dBm** | Decibel-milliwatts; common unit for signal strength (often negative for Wi‑Fi/RSSI-like values). |
| **Aggregate** | Per-cell summary: median signal and count of contributing scans. |
| **Interpolation** | Estimated value for an empty cell from weighted neighbors (not a new physical measurement). |
| **Registry** | In-memory structure from `get_floor_registry()`: which blocks/floors exist and per-floor config. |

---

## 5. System architecture

### 5.1 Logical flow

Data enters through either the **web scan form** (authenticated) or **`POST /api/scan/`** (CSRF-exempt JSON or form). Each accepted sample creates a **Scan** row and triggers **`refresh_cell_aggregates`**, which updates **CellAggregate** for that cell.

Consumers call **`GET /api/heatmap/`** with block, floor, mode, and optional provider. The view reads aggregates, optionally **rebuilds** them if missing, optionally **appends interpolated** points, and returns JSON. The **heatmap page** JavaScript fetches that JSON and paints to a **canvas** layered on the floor image.

### 5.2 Why this shape

- **Separation of raw and summary data** allows reprocessing (rebuild) if aggregation rules change.  
- **Median** limits impact of one bad reading.  
- **Two aggregate buckets** (per provider and all providers) avoid expensive joins at read time for the common “show everything” case.

### 5.3 Diagram (text)

```
Clients (browser, Android) --> POST /api/scan/ --> Scan
                                      |
                                      v
                            refresh_cell_aggregates
                                      |
                                      v
                              CellAggregate

Browser heatmap --> GET /api/heatmap/ --> CellAggregate + interpolate_missing_cells --> JSON --> Canvas draw
```

---

## 6. Repository structure

Why it matters: new contributors locate **settings** in `netsense/`, **domain logic** in `heatmap/`, and **assets** in `static/` and `templates/`.

```
nsc/
  manage.py
  requirements.txt
  render.yaml
  README.md                    (may contain condensed or full technical notes)
  expdoc.md                    (may contain quick-start style notes; filenames vary by project)
  PROJECT_MANUAL.md            (this document)
  db.sqlite3                   (default local DB if DATABASE_URL unset)
  media/floor_maps/            (uploaded floor images when using default storage)
  static/heatmap/              (CSS, JS, placeholder images)
  templates/                   (Django HTML)
  netsense/                    (project package: settings, root urls, WSGI)
  heatmap/                     (main application: models, views, utils, aggregation)
```

---

## 7. Configuration and environment

### 7.1 Core Django settings (summary)

| Item | Purpose |
|------|---------|
| `SECRET_KEY` | From `DJANGO_SECRET_KEY` or development default. Must be secret in production. |
| `DEBUG` | `DJANGO_DEBUG` (default true). False enables HTTPS hardening in this project. |
| `ALLOWED_HOSTS` | **Hardcoded** in `settings.py` in the reference repository (not loaded from `DJANGO_ALLOWED_HOSTS`). Change the file or extend code to read the environment when deploying to new hosts. |
| `DATABASES` | PostgreSQL via `DATABASE_URL` when set; otherwise SQLite at `db.sqlite3`. |
| `STATIC_*` / WhiteNoise | Compressed manifest storage for production static files. |
| `MEDIA_URL`, `MEDIA_ROOT` | Default upload location under `media/`. |
| `SERVE_MEDIA_FILES` | `DJANGO_SERVE_MEDIA`; when true, `urls.py` serves media (use cautiously in production). |

### 7.2 Heatmap defaults (`HEATMAP_*`)

These exist so the app can run **before** any `FloorPlan` rows exist, and as numeric fallbacks inside utilities.

| Setting | Role |
|---------|------|
| `HEATMAP_BLOCKS`, `HEATMAP_FLOORS` | Synthetic registry when no DB floor plans. |
| `HEATMAP_GRID_ROWS`, `HEATMAP_GRID_COLS` | Default grid dimensions. |
| `HEATMAP_FLOOR_DIMENSIONS` | Per-floor row/column overrides in fallback mode. |
| `HEATMAP_SERVICE_PROVIDERS` | Whitelists for validation and dropdowns (`wifi` and `mobile` lists). |
| `HEATMAP_BLOCKED_CELLS` | Optional mapping of `"block:floor"` or floor string keys to lists of blocked **cell_id** values. |

**Why both DB and settings:** Operators configure real campuses in **Django admin** (`FloorPlan`). Settings remain a **bootstrap** and **fallback** for empty databases and for commands that create rows programmatically.

---

## 8. Data model and design rationale

### 8.1 Block

Represents a **building code**. `is_active` excludes stale blocks from the registry without deleting history.

### 8.2 FloorPlan

One row per **(block, floor number)**. Holds **authoritative** `grid_rows` and `grid_cols`, **blocked_cells** JSON, optional **image**, and **is_active**.

**Why JSON for blocked cells:** Flexible admin entry (IDs, coordinates, or mixed legacy shapes) normalized by `blocked_cell_ids()` in Python.

### 8.3 Scan

A single **raw** observation: foreign key to `FloorPlan`, cell coordinates, `mode`, optional `service_provider`, `network_name`, integer `signal_strength` (dBm), timestamp.

**Why `cell_id` on save:** Fast indexing and consistency checks; recomputed whenever the scan is saved from `cell_y * grid_cols + cell_x`.

### 8.4 CellAggregate

Summaries for fast heatmap queries. Unique on `(floor_plan, cell_x, cell_y, mode, service_provider, is_all_providers)`.

**Why `is_all_providers` flag:** Distinguishes the combined bucket (`True`, empty `service_provider`) from a real provider name without overloading NULL semantics across databases.

---

## 9. Grid indexing and blocked cells

### 9.1 Formulas

Forward:

```
cell_id = cell_y * cols + cell_x
```

Inverse:

```
cell_x = cell_id % cols
cell_y = cell_id // cols
```

**Why row-major indexing:** Matches common 2D flattening conventions and keeps blocked lists as simple integer arrays.

### 9.2 Normalization of blocked_cells entries

The admin can store human-friendly forms. `FloorPlan.blocked_cell_ids()` converts integers, numeric strings, `[x,y]` pairs, and small dicts into a single list of **cell_id** integers using the floor’s column count.

### 9.3 Validation at scan time

`is_blocked_cell` recomputes the candidate cell’s `cell_id` and rejects scans there. **Why:** prevents data in non-walkable or non-modeled regions.

---

## 10. Floor registry and utilities

### 10.1 `get_floor_registry()`

If active `FloorPlan` rows exist, builds:

- **blocks**: ordered codes.  
- **block_floors**: map block → list of floor numbers.  
- **floor_configs**: key `"block:floor"` → `rows`, `cols`, `image_url`, `floor_name`, `blocked_cells` (normalized list).

If **no** active floor plans, builds the same keys from `HEATMAP_*` settings.

**Why a registry:** One function powers HTML dropdowns, Android config API, and server-side validation with identical numbers.

### 10.2 Other helpers

- `get_floor_dimensions`, `get_floor_plan`, `ensure_floor_plan` (used by commands to create missing rows).  
- `get_service_providers` surfaces settings to Python and JSON.

---

## 11. Scan ingestion

### 11.1 Payload handling

`_parse_scan_payload` reads JSON bodies when `Content-Type` is `application/json`; otherwise form data. Malformed JSON yields `{}` and will likely fail numeric validation—**why:** fail safe for bad clients without crashing.

### 11.2 Validation order and rationale

1. Parse integers for floor, signal, and cell indices—**reject early** on bad types.  
2. Validate block and floor against the registry—**prevents orphan data**.  
3. Validate mode—keeps aggregates partitioned.  
4. Normalize provider to `"Unknown"` if blank; if settings define a list for that mode, require membership or Unknown—**why:** controlled vocabulary for demos and reporting.  
5. Enforce grid bounds—**prevents out-of-range indices**.  
6. Blocked cell check—**spatial integrity**.  
7. Require a real `FloorPlan` row—**why:** scans must attach to an uploadable floor configuration.

### 11.3 Web versus API

- **Web `/scan/`** uses POST form data, CSRF token, login required—suitable for trusted staff browsers.  
- **`/api/scan/`** is POST-only, CSRF-exempt—**why:** simple integration for non-browser clients; **trade-off:** must be protected externally (VPN, API gateway, firewall) if public.

---

## 12. Aggregation logic

### 12.1 Why median

The **median** is less sensitive than the mean to outliers (brief spikes or drops). For indoor RSSI-style readings, that usually yields a **stabler** per-cell value.

### 12.2 `refresh_cell_aggregates`

Within a database transaction, for the affected cell:

1. **Provider-specific bucket:** all scans with the same normalized provider string (`""` becomes `"Unknown"` for grouping in filters—see code paths).  
2. **All-providers bucket:** all scans in that cell and mode regardless of provider; stored with `is_all_providers=True` and empty `service_provider`.

**Why two passes:** Heatmap can show **CampusNet only** or **all carriers combined** without scanning the entire `Scan` table at request time.

### 12.3 `rebuild_aggregates_for_floor`

Deletes aggregates (optionally for one mode), scans all `Scan` rows for the floor, groups by composite key, and upserts. **When used:** demo seeding, repair after imports, or API auto-repair when aggregates are missing.

---

## 13. Interpolation

### 13.1 Purpose

Operators still want a **continuous-looking** map when only part of the grid was measured. Interpolation provides **hints**, not ground truth.

### 13.2 Algorithm (implemented)

Parameters include `max_distance=2` (grid steps). For each empty, non-blocked cell, collect neighbors within the square window that **already exist in `points`**. Weight:

```
weight = (1 / distance_sq) * max(1.0, (count or 1) ** 0.5)
```

Then **weighted average** of neighbor signals. Output rounds **signal** to two decimals; `count` is **0** and `interpolated` is **true**.

**Why inverse square distance:** Nearby cells matter more; smooth falloff. **Why sqrt(count):** cells with more scans are slightly more trusted as anchors. **Why no chaining:** avoids propagating estimates across the whole floor from one corner in a single request.

### 13.3 Empty points dict

If there are no measured cells, interpolation returns nothing—**why:** no evidence to extrapolate from.

---

## 14. Heatmap API

### 14.1 Request

`GET /api/heatmap/?block=...&floor=...` with optional `mode`, `service_provider`, `interpolate`.

- **`service_provider` empty or `all`:** selects `is_all_providers=True` aggregates.  
- **Specific provider:** selects that provider’s bucket.  
- **`interpolate`:** disabled only when the parameter trims to `"0"`; any other value (including default) enables interpolation.

### 14.2 Auto-rebuild

If no aggregate rows match the query, the server calls **`rebuild_aggregates_for_floor`** for that floor/mode and retries—**why:** recovers from partial failures or manual aggregate deletion without manual commands.

### 14.3 Response

JSON **array** of objects: `cell_x`, `cell_y`, `signal` (two decimal places), `count`, `interpolated` boolean. Measured rows come first in natural cell order; interpolated rows are **appended**.

---

## 15. Config API

`GET /api/config/` returns the same registry structure the web UI embeds: blocks, floors per block, per-floor config (dimensions, image URL, name, blocked cells), and provider lists. **Why:** Android or other clients stay in sync without scraping HTML.

---

## 16. Web user interfaces

### 16.1 Landing page (`/`)

Marketing-style content and navigation to the live heatmap. **landing.js** adds scroll-reveal styling. **Why:** separates public storytelling from tools.

### 16.2 Heatmap viewer (`/heatmap/`)

**home.js** loads floor image and grid, fetches `/api/heatmap/`, computes **color scale** from measured points when possible, and draws:

- **Blended mode:** radial gradients; stronger alpha when more scans support a cell (heuristic).  
- **Contour mode:** discrete bands via `round(normalized * 6) / 6`.  
- **Auto smooth:** adjusts spread from **density** of real measurements—**why:** sparse data needs wider blending; dense data needs less overlap.  
- **Confidence overlay:** darkens cells with higher relative scan counts.

**Color choice:** warm ramp (red–yellow–green) for measured cells matches intuitive “bad to good”; cool ramp for interpolated cells signals **lower trust**.

### 16.3 Scan page (`/scan/`)

**scan.js** maps clicks to grid indices, blocks selection on blocked `cell_id`s, and posts a form with hidden `cell_x`/`cell_y`. **Why:** no manual coordinate entry errors for operators.

---

## 17. Django administration

Admin registers **Block** (with **FloorPlan** inline), **FloorPlan**, **Scan**, and **CellAggregate**. Operators manage grids, upload maps, and inspect raw or aggregated data. **Why:** production configuration without code changes.

---

## 18. Management commands

### 18.1 `seed_demo_data`

Options: `--per-floor` (default **500** in code—verify help text in your checkout), `--clear` to wipe scans first. Creates random plausible data and rebuilds aggregates.

**Why:** demos and UI testing without manual clicking.

### 18.2 `rebuild_aggregates`

Rebuilds aggregates for every block/floor in the registry. **Why:** maintenance after bulk edits to `Scan`.

---

## 19. Security and authentication

| Route | Notes |
|-------|-------|
| `/scan/` | Login required; CSRF on POST. |
| `/api/scan/` | No login; CSRF exempt—**treat as sensitive**. |
| `/api/heatmap/`, `/api/config/` | Read-only JSON; public. |

Session and CSRF cookies become **secure** when `DEBUG` is false, alongside HTTPS headers.

---

## 20. Edge cases and limitations

- **Single unique signal value:** UI forces a minimum color range so division by zero does not occur.  
- **Invalid `mode` query:** may not filter as intended—clients should send only `wifi` or `mobile`.  
- **Interpolation gaps:** large empty regions without neighbors within `max_distance` stay unfilled—this is intentional.  
- **Media on PaaS:** default file storage is local; ephemeral disks lose uploads unless you add persistent storage or object storage (and typically adjust `MEDIA_ROOT` or storage backend in code).

---

## 21. Installation and local development

### 21.1 Virtual environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

### 21.2 Dependencies

```bash
pip install -r requirements.txt
```

### 21.3 Database

```bash
python manage.py migrate
```

### 21.4 Admin user

```bash
python manage.py createsuperuser
```

### 21.5 Configure campus data

Open `http://127.0.0.1:8000/admin/`, create **Block** rows (for example `A`, `B`, `C`), add **FloorPlan** rows with `number`, `grid_rows`, `grid_cols`, and optional **image**.

### 21.6 Optional demo data

```bash
python manage.py seed_demo_data --clear
```

### 21.7 Run server

```bash
python manage.py runserver
```

**Why SQLite locally:** zero setup; production uses PostgreSQL via `DATABASE_URL`.

---

## 22. Demonstration workflow

1. Open `http://127.0.0.1:8000/` for the landing page.  
2. Open `http://127.0.0.1:8000/heatmap/` for the public heatmap.  
3. Log in at `http://127.0.0.1:8000/login/`, then capture scans at `http://127.0.0.1:8000/scan/`.  
4. Inspect JSON, for example:

`http://127.0.0.1:8000/api/heatmap/?block=A&floor=1&mode=wifi`

Provider-specific:

`http://127.0.0.1:8000/api/heatmap/?block=A&floor=1&mode=mobile&service_provider=Jio`

Interpolation on (default):

`http://127.0.0.1:8000/api/heatmap/?block=A&floor=1&mode=wifi&interpolate=1`

Interpolation off:

`http://127.0.0.1:8000/api/heatmap/?block=A&floor=1&mode=wifi&interpolate=0`

---

## 23. Deployment

### 23.1 Render blueprint (`render.yaml`)

The repository includes a blueprint that installs dependencies, runs **collectstatic**, runs **migrations** at start, and serves with **Gunicorn**. Environment variables include `DJANGO_DEBUG=false` and a generated secret.

### 23.2 Manual Render-style settings

Typical build:

`pip install -r requirements.txt && python manage.py collectstatic --noinput`

Pre-deploy migrations:

`python manage.py migrate --noinput`

Start:

`gunicorn netsense.wsgi:application`

Set at minimum:

- `DJANGO_DEBUG=false`  
- `DJANGO_SECRET_KEY` (strong random)  
- `DATABASE_URL` (PostgreSQL)

**Note:** Example README snippets may mention `DJANGO_ALLOWED_HOSTS` or `DJANGO_CSRF_TRUSTED_ORIGINS`; the reference `settings.py` uses **hardcoded** `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`. **Update `settings.py`** (or extend it) when your production domain differs.

### 23.3 Media durability

Uploaded floor images go to `MEDIA_ROOT` (default project `media/`). On typical cloud platforms the filesystem is **ephemeral**. For durability, attach **persistent disk** and point media root there in settings, or use **S3-compatible** or **Cloudinary** storage via Django’s storage backends (requires code changes not included in the minimal MVP).

---

## 24. Database migration history (conceptual)

Early schema stored block/floor on `Scan` directly. Later migrations introduce **`Block`**, **`FloorPlan`**, **`CellAggregate`**, **`service_provider`**, and a **`floor_plan`** foreign key—normalizing configuration and enabling admin-managed maps. See `heatmap/migrations/` for exact operations.

---

## 25. End-to-end scenario

1. Administrator creates **Block A** and **Floor 1** with a **12×8** grid and uploads a PNG map.  
2. Field staff logs in, selects Wi‑Fi, chooses **CampusNet**, clicks cell (3,2), enters **-72** dBm, submits.  
3. Server stores **Scan**; aggregates now show median and count for **CampusNet** and for **all providers** at that cell.  
4. Heatmap viewer calls the API with **All** providers and interpolation enabled; empty neighbors may receive **blue-tinted** estimated values.  
5. Facilities identifies persistent red zones and plans access point or repeater placement.

---

## 26. Appendices

### Appendix A. URL quick reference

| URL | Purpose |
|-----|---------|
| `/` | Landing |
| `/heatmap/` | Public heatmap |
| `/scan/` | Authenticated scan capture |
| `/login/`, `/logout/` | Auth |
| `/admin/` | Django admin |
| `/api/scan/` | Create scan (POST) |
| `/api/heatmap/` | Heatmap JSON (GET) |
| `/api/config/` | Client config (GET) |

### Appendix B. Environment variables read by code

| Variable | Effect |
|----------|--------|
| `DJANGO_SECRET_KEY` | Secret key |
| `DJANGO_DEBUG` | Debug flag |
| `DJANGO_SERVE_MEDIA` | Serve `/media/` via Django |
| `DATABASE_URL` | PostgreSQL connection string |

### Appendix C. Dependencies (high level)

- Django 5.x  
- Pillow (images)  
- dj-database-url  
- gunicorn  
- psycopg (PostgreSQL)  
- whitenoise  

### Appendix D. Troubleshooting

| Symptom | Likely cause | Direction |
|---------|----------------|-----------|
| Empty heatmap | No scans or wrong block/floor params | Add scans; check registry via `/api/config/` |
| 404 floor not configured | No `FloorPlan` for block/floor | Create in admin |
| Interpolation always empty | No measured cells in range | Measure more cells or disable interpolate to see raw only |
| Uploads disappear after redeploy | Ephemeral disk | Persistent storage or object storage |

---

*End of NetSense Campus Project Manual.*

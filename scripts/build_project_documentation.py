"""One-off builder: merges README ExpDoc verbatim into PROJECT_DOCUMENTATION.md."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
OUT = ROOT / "PROJECT_DOCUMENTATION.md"

readme_raw = README.read_text(encoding="utf-8")
lines = readme_raw.splitlines()
start = 0
for i, line in enumerate(lines):
    if line.startswith("# NetSense Campus"):
        start = i
        break
readme_body = "\n".join(lines[start:])
if readme_raw.endswith("\n") and not readme_body.endswith("\n"):
    readme_body += "\n"

HEADER = r'''# NetSense Campus — Full Project Documentation

**Upgraded structure document.** This file contains: (1) title page, abstract, executive summary, refined table of contents, problem definition, design thinking, innovation, conceptual model, and extended sections on performance, security, deployment, limitations, future work, conclusion, and references; (2) **Section 9 — the complete Expert Documentation (ExpDoc) reproduced verbatim from `README.md`** (nothing omitted), with a category map (A–H); (3) additional chapters 10–16 that extend beyond the README.

**How to use in Microsoft Word:** Open this `.md` in Word, or run `pandoc PROJECT_DOCUMENTATION.md -o PROJECT_DOCUMENTATION.docx`.

---

## 1. Title page (fill institutional details as needed)

| Field | Content |
|-------|---------|
| **Project title** | NetSense Campus (NSC) |
| **Tagline / value proposition** | Make invisible indoor connectivity visible — grid-based Wi‑Fi and mobile signal intelligence with median aggregation, interpolation-aware heatmaps, and a minimal Django API surface. |
| **Author** | Sreeraj Patnaik *(update if required)* |
| **Institution / organization** | *(add your institution)* |
| **Date** | 2026-04-01 |

---

## 2. Abstract

**Problem statement (2–3 lines).** Indoor wireless quality is spatially uneven; stakeholders cannot see *where* coverage fails across floors. Raw dBm lists do not map intuitively to physical space, and single measurements are noisy.

**Approach.** This project implements a **Django** web application that stores signal samples on a **per-floor grid**, aggregates them with the **median** per cell (plus an **all-providers** bucket), optionally **interpolates** empty cells using **inverse distance–weighted** estimates, and renders **heatmaps** in the browser with dynamic scaling and optional confidence overlay.

**Key technologies.** Django 5.x, SQLite or PostgreSQL (`DATABASE_URL`), WhiteNoise, Gunicorn, vanilla JavaScript canvas rendering, Pillow for images.

**Outcome / impact.** A deployable MVP for **campus IT**, **facilities**, and **field teams** to capture scans (web or API), configure floors in **Django admin**, and visualize **Wi‑Fi** vs **mobile** coverage with clear separation between **measured** and **interpolated** cells.

---

## 3. Executive summary (from repository ExpDoc)

**NetSense Campus** is a minimal Django application that:

- Accepts **Wi‑Fi** and **mobile** signal samples on a **per-floor grid** (`cell_x`, `cell_y`).
- Persists raw rows as **`Scan`** records.
- Maintains **`CellAggregate`** rows: **median** signal strength and **scan count** per cell, per mode, for (a) a specific **service provider** and (b) an **“all providers”** bucket.
- Serves **`GET /api/heatmap/`** with optional **distance-weighted interpolation** for empty, non-blocked cells.
- Renders a **browser heatmap** (radial blend or contour bands) with **dynamic min/max scaling**, optional **confidence overlay**, and distinct coloring for **interpolated** vs **measured** cells.

**What problem it solves.** It turns scattered signal readings into a **shared, map-aligned picture** of coverage, with **robust** per-cell values and optional **gap filling** where no sample exists.

**Why it matters.** Planning access points, explaining user complaints, and comparing **carriers** or **SSIDs** requires **spatial** evidence; this system provides that evidence with low operational overhead.

---

## 4. Table of contents (refined)

### Part I — Narrative and framing

1. Title page *(§ above)*  
2. Abstract *(§ 2)*  
3. Executive summary *(§ 3)*  
4. Problem definition *(§ 5)*  
5. Design thinking process *(§ 6)*  
6. Innovation and differentiation *(§ 7)*  
7. System overview diagram *(§ 8)*  
8. Conceptual model — narrative overview *(under § 8 above)*  

### Part II — Complete technical reference (verbatim README / ExpDoc)

9. **Detailed technical documentation** — full `README.md` ExpDoc, **uncut**, with category map A–H *(§ 9)*  

### Part III — Extended analysis (beyond README; chapters 10–16)

10. Performance and scalability *(Part III, § 10)*  
11. Security considerations *(Part III, § 11)*  
12. Deployment strategy *(Part III, § 12)*  
13. Limitations *(Part III, § 13)*  
14. Future enhancements *(Part III, § 14)*  
15. Conclusion *(Part III, § 15)*  
16. References and credits *(Part III, § 16)*  

---

## 5. Problem definition

### 5.1 Real-world problem

Universities and enterprises struggle to **localize** poor Wi‑Fi or mobile coverage indoors. Users report “no signal” without coordinates; teams lack a **single map** that combines **multiple measurements** and **multiple networks** in one view.

### 5.2 Existing solutions (brief critique)

- **Drive-test tools** are powerful but often **desktop-centric** or **vendor-locked**.  
- **Spreadsheets** of readings lack **spatial grounding** on a floor plan.  
- **Full RF planning suites** are heavy for an **MVP** and may not expose a simple **HTTP API** for custom scanners.

### 5.3 Gap identified

A **lightweight**, **web-first** pipeline: **grid cells** + **median aggregation** + **optional interpolation** + **clear API** for mobile clients, with **admin-configurable** floors and **blocked** regions — without requiring proprietary hardware.

---

## 6. Design thinking process

### 6.1 Empathize

**Users:** campus IT staff, network engineers, facilities, teaching staff, and (indirectly) students affected by dead zones.

**Pain points:** invisible coverage patterns, noisy single readings, need to compare **Wi‑Fi vs mobile** and **provider A vs B** on the **same floor layout**.

### 6.2 Define

**Problem framed:** Capture **repeatable**, **validated** signal samples tied to **block / floor / cell**, summarize them **robustly**, and **visualize** them on an uploaded map — with **honest** labeling of **estimated** vs **measured** cells.

### 6.3 Ideate

**Alternatives considered:** mean instead of median (more sensitive to outliers); full Kriging or graph Laplacian interpolation (more complex); storing only aggregates (loses raw audit trail — rejected; **Scan** rows kept).

**Why this approach:** **Median** resists outliers; **two aggregate buckets** avoid expensive runtime joins for “all providers”; **IDW-style** weights on the grid are **simple to explain** and **fast enough** for campus-sized grids.

### 6.4 Prototype

Early versions used denormalized block/floor on **Scan**; the schema **evolved** to **`FloorPlan`** with images and JSON **blocked cells**. The UI moved from tables to **click-to-cell** on a floor image.

**Key iterations:** admin-managed dimensions; **CSRF-safe** web scan vs **CSRF-exempt** API scan for device integration; **interpolated** styling distinct from **measured**.

### 6.5 Test

**What worked:** median aggregates, dual buckets, heatmap **auto spread** from sample density, **config API** for clients.

**What to watch:** public **`/api/scan/`** without auth — must be **network-protected** in production; **ephemeral media** on PaaS without persistent disk.

---

## 7. Innovation and differentiation

| Aspect | Distinction |
|--------|-------------|
| **Grid + cell_id** | Single index for blocked lists and validation; consistent across Python and JS. |
| **Dual aggregates** | Per-provider and **all-providers** precomputed for fast heatmap queries. |
| **Interpolation** | Inverse-square grid distance × √(count) weight; **no chaining** in one request — avoids fake confidence propagation. |
| **Visualization** | Dynamic min/max, **confidence overlay**, separate color ramps for **interpolated** vs **measured**. |

**Comparison with standard approaches:** Simpler than GIS-heavy RF tools; more **transparent** than black-box ML interpolation for an MVP.

---

## 8. System overview diagram (recommended)

```
                    +------------------+
                    |  Browser / App   |
                    +--------+---------+
                             |
              +--------------+---------------+
              |                              |
       POST /api/scan/                 GET /api/heatmap/
              |                              |
              v                              v
     +----------------+            +------------------+
     | Django views   |            | heatmap_api      |
     | scan_api       |            | + interpolate_*  |
     +--------+-------+            +--------+---------+
              |                              |
              v                              v
     +----------------+            +------------------+
     | Scan rows      |            | CellAggregate  |
     | refresh_*      |----------->| (read/filter)  |
     +----------------+            +------------------+
              |
              v
     +----------------+
     | PostgreSQL /   |
     | SQLite         |
     +----------------+
```

**Data flow summary:** Writes go **Scan → aggregates**; reads go **aggregates → optional interpolation → JSON → canvas**.

### Conceptual model (narrative overview)

At the **conceptual** level, the system is a **directed pipeline**: **Campus configuration** (blocks, floors, grids, blocked cells, images) defines *where* sampling is meaningful; **Scans** are *evidence* in that space; **CellAggregate** is a *compressed view* optimized for queries; **Interpolation** is an *explicitly labeled inference layer* for empty cells; the **heatmap UI** is a *human interpretation layer* with color, scale, and confidence. This separation keeps **measured** and **estimated** values distinguishable in both JSON and pixels.

---

'''

FOOTER = r'''

---

## Part III: Extended analysis (beyond README ExpDoc)

The following chapters **extend** the verbatim technical reference above. They are numbered **10–16** to match the upgraded documentation outline; they do **not** replace or repeat ExpDoc sections **§10–§23** inside Section 9.

### 10. Performance and scalability

#### 10.1 Time complexity (as implemented)

| Operation | Order (typical) | Notes |
|-----------|-----------------|-------|
| **Registry** `get_floor_registry()` | O(F) | F = number of active floor plans. |
| **Per-scan refresh** | O(S_c) | S_c = scans in same cell/mode/provider for that bucket; usually small. |
| **Rebuild floor** | O(S) | S = all scans for floor; single pass grouping. |
| **Interpolation** | O(rows × cols × N_w) | N_w = neighbors checked per cell; window size fixed by `max_distance=2` (constant factor). |
| **Heatmap API** | O(A + I) | A = aggregate rows returned; I = interpolated points generated. |

#### 10.2 Large datasets

- **Scans** grow linearly with field sampling; indexes on `(floor_plan, mode)`, `(cell_id)` support filtering.  
- **Aggregates** are one row per **cell × mode × bucket** — bounded by grid size × modes × providers.  
- **Interpolation** cost scales with **grid area**, not total scans (uses **aggregated** points only).

#### 10.3 Optimization techniques (current and possible)

- **Present:** `update_or_create` for aggregates; optional full **rebuild** only when query empty.  
- **Future:** cache `get_floor_registry()` if called very frequently; paginate heatmap API only if product requires **partial** floor fetch (not in MVP).

---

### 11. Security considerations (extended)

#### 11.1 Authentication model

- **Staff-style** access via Django **session login** for `/scan/` (redirect from `/login/`).  
- **No authentication** on **`POST /api/scan/`** by design for device integration — **treat as privileged**; place behind VPN, API gateway, IP allowlist, or add tokens in a fork.

#### 11.2 Data protection

- **Signal readings** are not personally identifying by themselves; still follow organizational policy for **location data**.  
- **SECRET_KEY** and **DATABASE_URL** must be **secret** in production (`DEBUG=false`, HTTPS enforced in settings when not debugging).

#### 11.3 API security

- **CSRF** enforced on browser form POST to `/scan/`; **CSRF exempt** on `/api/scan/` — clients must not expose this endpoint publicly without other controls.  
- **Read APIs** (`/api/heatmap/`, `/api/config/`) are **public** — acceptable for open dashboards; restrict if floor layouts are sensitive.

---

### 12. Deployment strategy (expanded)

#### 12.1 Environment setup

- **Local:** Python 3.12 compatible, `venv`, `pip install -r requirements.txt`, `migrate`, optional `createsuperuser`.  
- **Production:** Set `DATABASE_URL` to PostgreSQL; `DJANGO_DEBUG=false`; strong `DJANGO_SECRET_KEY`; **edit `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` in `settings.py`** for your domain (env vars for hosts are **not** wired in the reference `settings.py`).

#### 12.2 CI/CD

- The repository includes **`render.yaml`** for **Render** blueprint deploy (build + migrate + gunicorn).  
- **No bundled GitHub Actions** in the described tree — add pipelines (lint, test, migrate) as needed.

#### 12.3 Production considerations

- **Static files:** WhiteNoise + `collectstatic`.  
- **Media:** default local `media/` is **ephemeral** on many hosts — use **persistent disk** or **object storage** for durable floor images.  
- **SSL:** `SECURE_SSL_REDIRECT` and HSTS when `DEBUG` is false.

---

### 13. Limitations

#### 13.1 Current constraints

- Grid is **2D per floor** — no vertical coupling between floors.  
- Interpolation is **heuristic**, not physics-based RF simulation.  
- **Single-pass** interpolation does not fill large voids without neighbors within **`max_distance`**.  
- **Mode** query must be exactly `wifi` or `mobile` for correct filtering (see ExpDoc edge cases).

#### 13.2 Edge cases not fully handled

- Invalid **`mode`** strings may yield **unfiltered** aggregate queries.  
- Very large **grid dimensions** increase interpolation CPU time quadratically with rows×cols.

---

### 14. Future enhancements

- **Auth tokens** for `/api/scan/` (DRF JWT or API keys).  
- **WebSocket** or **SSE** for live refresh without manual reload.  
- **S3** or **Cloudinary** storage backend for `FloorPlan.image`.  
- **Export** PNG/PDF of heatmap; **CSV** export of aggregates.  
- **Research:** calibrated path-loss surfaces or **Gaussian processes** for interpolation — trade complexity for accuracy.

---

### 15. Conclusion

**What was achieved:** A **coherent** end-to-end system — from **sample capture** through **median aggregation**, **optional interpolation**, to **browser visualization** and **mobile-friendly JSON APIs**.

**Impact:** Faster **communication** of coverage quality between technical teams and stakeholders; **transparent** behavior documented in the ExpDoc sections above.

**Learning:** Balancing **MVP simplicity** (Django monolith, few endpoints) with **real-world** needs (blocked cells, dual provider views, honest interpolation labeling).

---

### 16. References and credits

- **Django** — https://www.djangoproject.com/  
- **WhiteNoise** — http://whitenoise.evans.io/  
- **dj-database-url** — database URL parsing for Django  
- **Python `statistics.median`** — robust central tendency for aggregate values  
- **Render** — platform referenced by `render.yaml` in this repository  

*(Add academic papers, internal reports, or team acknowledgments as appropriate.)*

---

*End of NetSense Campus — Full Project Documentation.*

'''

OUT.write_text(HEADER + "\n## 9. Detailed technical documentation (complete README / ExpDoc, verbatim)\n\n"
    "The following block is copied **in full** from `README.md` (Expert Documentation). "
    "**Nothing has been removed or shortened.** A **category map** aligns ExpDoc section numbers with Parts A–H.\n\n"
    "### Category map (ExpDoc sections → Parts A–H)\n\n"
    "| Part | ExpDoc §§ | Topics |\n"
    "|------|-----------|--------|\n"
    "| **A. Foundation** | §1–§5 | Executive summary, repository layout, runtime architecture, URL routing, configuration |\n"
    "| **B. Core system design** | §6–§9 | Data model, grid/blocked cells, registry, scan ingestion (web + API) |\n"
    "| **C. Backend services** | §10–§13 | Aggregation engine, interpolation engine, heatmap API, config API |\n"
    "| **D. Frontend systems** | §14–§16 | Heatmap viewer, scan UI, templates and injected config |\n"
    "| **E. Operations and tooling** | §17–§18 | Django admin, management commands |\n"
    "| **F. Security and behavior** | §19–§20 | Security and auth, edge cases and behavioral notes |\n"
    "| **G. Deployment and evolution** | §21–§22 | Deployment (Render + media), migration history |\n"
    "| **H. Conceptual understanding** | §23 | End-to-end walkthrough (see also **Conceptual model (narrative overview)** under Part I § 8) |\n\n"
    "---\n\n" + readme_body + "\n\n---\n" + FOOTER, encoding="utf-8")
print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")

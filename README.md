# NetSense Campus (MVP)

Minimal Django application to capture Wi-Fi/mobile signal samples and render floor-wise heatmaps.

## Features

- Public heatmap viewer at `/`
- Admin scan capture page at `/scan` (login required)
- Aggregated API at `/api/heatmap/?block=A&floor=2&mode=wifi&service_provider=CampusNet`
- Django admin for managing blocks/floors, floor images, grid dimensions, and scan cleanup at `/admin`

## Quick Start

1. Create and activate a virtual environment:

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

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run migrations:

```bash
python manage.py migrate
```

4. Create admin user:

```bash
python manage.py createsuperuser
```

5. Configure blocks/floors in admin:

- Open `http://127.0.0.1:8000/admin/`
- Create `Block` records (example: `A`, `B`, `C`)
- Add `FloorPlan` rows for each block with:
  - `number` (floor number)
  - `grid_rows`, `grid_cols`
  - `image` (floor map upload)

6. Seed demo data:

```bash
python manage.py seed_demo_data --clear
```

7. Start server:

```bash
python manage.py runserver
```

## Demo Flow

- Open viewer at `http://127.0.0.1:8000/`
- Login at `http://127.0.0.1:8000/login/`
- Add scans at `http://127.0.0.1:8000/scan/`
- Inspect aggregated API:

```text
http://127.0.0.1:8000/api/heatmap/?block=A&floor=1&mode=wifi
```

Provider-specific example:

```text
http://127.0.0.1:8000/api/heatmap/?block=A&floor=1&mode=mobile&service_provider=Jio
```

## Notes

- Uploaded floor images are stored in `media/floor_maps/` and served at `/media/...` in `DEBUG=True`.
- Blocks/floors/images/grid dimensions are now managed via admin (`Block` and `FloorPlan`).
- `HEATMAP_*` block/floor/grid settings are fallback defaults used only when no `FloorPlan` rows exist.
- Service provider options for WiFi and mobile are configurable via `HEATMAP_SERVICE_PROVIDERS` in `netsense/settings.py`.
- Placeholder image remains `static/heatmap/images/floor-placeholder.svg` for floors without uploaded images.

## Deploy On Render

This project is ready for Render using the included [`render.yaml`](./render.yaml).

### Option A: Blueprint Deploy (recommended)

1. Push this repo to GitHub/GitLab.
2. In Render, click **New +** -> **Blueprint**.
3. Select the repository.
4. Render reads `render.yaml`, creates:
   - Web service (`netsense-campus`)
   - PostgreSQL database (`netsense-db`)
5. Deploy.

### Option B: Manual Web Service Setup

Create a **Web Service** in Render with:

- Build Command:
  `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Pre-Deploy Command:
  `python manage.py migrate --noinput`
- Start Command:
  `gunicorn netsense.wsgi:application`

Set environment variables:

- `DJANGO_DEBUG=false`
- `DJANGO_SECRET_KEY=<strong-random-secret>`
- `DJANGO_ALLOWED_HOSTS=.onrender.com,<your-custom-domain>`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://*.onrender.com,https://<your-custom-domain>`
- `DATABASE_URL=<Render PostgreSQL connection string>`

### Media Uploads On Render

Floor image uploads currently use local filesystem storage (`media/`).
On Render, local filesystem is ephemeral unless you attach persistent storage.
For production durability, use either:

- Render persistent disk (and set `DJANGO_MEDIA_ROOT` to that mount path), or
- External object storage (S3/Cloudinary).

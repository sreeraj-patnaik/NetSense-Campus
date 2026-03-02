# NetSense Campus (MVP)

Minimal Django application to capture Wi-Fi/mobile signal samples and render floor-wise heatmaps.

## Features

- Public heatmap viewer at `/`
- Admin scan capture page at `/scan` (login required)
- Aggregated API at `/api/heatmap/?block=A&floor=2&mode=wifi`
- Django admin support for scan cleanup at `/admin`

## Quick Start

1. Create and activate a virtual environment.
2. Install Django:

```bash
pip install django
```

3. Run migrations:

```bash
python manage.py migrate
```

4. Create admin user:

```bash
python manage.py createsuperuser
```

5. Start server:

```bash
python manage.py runserver
```

## Notes

- Grid size defaults to 12 rows x 8 cols (`HEATMAP_GRID_ROWS` and `HEATMAP_GRID_COLS` in settings).
- Blocks and floors are configurable in `netsense/settings.py`.
- Replace `static/heatmap/images/floor-placeholder.svg` with real floor maps when available.

# Project Structure

This page summarizes the repository layout and the responsibilities of each module.

## Root Layout

```
manage.py
requirements.txt
render.yaml
README.md
expdoc.md
PROJECT_DOCUMENTATION.md
PROJECT_MANUAL.md
static/
templates/
media/
netsense/
heatmap/
```

## Django Project Package

- `netsense/settings.py`: configuration, database, static and media settings.
- `netsense/urls.py`: project URL routing.
- `netsense/wsgi.py` and `netsense/asgi.py`: deployment entrypoints.

## Main App: `heatmap/`

- `models.py`: Block, FloorPlan, Scan, CellAggregate.
- `views.py`: page views and JSON APIs.
- `urls.py`: app routes for landing, heatmap, scan, and APIs.
- `utils.py`: floor registry, blocked cell helpers, interpolation.
- `aggregation.py`: median aggregation and rebuild logic.
- `admin.py`: admin dashboards for blocks, floors, scans, aggregates.
- `management/commands/`: seed and rebuild commands.

## Frontend Assets

- `templates/heatmap/landing.html`: landing page.
- `templates/heatmap/home.html`: heatmap viewer.
- `templates/heatmap/scan.html`: scan UI.
- `static/heatmap/js/home.js`: heatmap rendering.
- `static/heatmap/js/scan.js`: scan UI interactions.
- `static/heatmap/js/landing.js`: landing animations.
- `static/heatmap/css/style.css`: shared styling.

## Media

- `media/floor_maps/`: uploaded floor plan images.

## Config And Ops

- `render.yaml`: Render deployment blueprint.
- `requirements.txt`: Python dependencies.

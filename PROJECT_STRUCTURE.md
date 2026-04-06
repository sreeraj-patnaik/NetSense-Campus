# Project Structure

This page reflects the repository layout and responsibilities for a production-ready delivery.

## Root Layout

```
nsc/
  manage.py
  requirements.txt
  render.yaml
  README.md
  expdoc.md
  db.sqlite3
  media/
    floor_maps/
  static/
    heatmap/
      css/style.css
      js/home.js
      js/scan.js
      js/landing.js
      images/
  templates/
    base.html
    heatmap/home.html
    heatmap/scan.html
    heatmap/landing.html
    registration/login.html
  netsense/
    settings.py
    urls.py
    wsgi.py
    asgi.py
  heatmap/
    models.py
    views.py
    urls.py
    utils.py
    aggregation.py
    admin.py
    migrations/
    management/commands/
      seed_demo_data.py
      rebuild_aggregates.py
```

## Django Project Package (`netsense/`)

- `settings.py`: configuration, DB wiring, static/media setup.
- `urls.py`: project-level routing.
- `wsgi.py` / `asgi.py`: deployment entrypoints.

## Main App (`heatmap/`)

- `models.py`: Block, FloorPlan, Scan, CellAggregate.
- `views.py`: page views + JSON APIs.
- `urls.py`: app routes.
- `utils.py`: floor registry, blocked cell logic, interpolation.
- `aggregation.py`: median aggregation and rebuild logic.
- `admin.py`: admin UI configuration.
- `management/commands/`: seed data and rebuild aggregates.

## Frontend

- Templates in `templates/` define landing, heatmap, scan, and login pages.
- Scripts in `static/heatmap/js/` power rendering and scan UI.
- Styles in `static/heatmap/css/style.css`.

## Deployment

- `render.yaml` defines Render pipeline (build, migrate, gunicorn).

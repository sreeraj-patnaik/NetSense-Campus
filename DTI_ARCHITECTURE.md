# DTI Architecture

This page presents the DTI architecture for NetSense Campus. DTI is treated here as Data, Transform, Interface.

## DTI Layers

### Data

- Models: `Block`, `FloorPlan`, `Scan`, `CellAggregate` in `heatmap/models.py`.
- Storage: SQLite by default or PostgreSQL via `DATABASE_URL`.
- Source of truth for grids, blocked cells, and floor images: `FloorPlan`.

### Transform

- Scan validation and normalization: `_validate_scan_payload` in `heatmap/views.py`.
- Aggregation: `refresh_cell_aggregates` and `rebuild_aggregates_for_floor` in `heatmap/aggregation.py`.
- Interpolation: `interpolate_missing_cells` in `heatmap/utils.py`.

### Interface

- APIs: `/api/scan/`, `/api/heatmap/`, `/api/config/` in `heatmap/views.py`.
- Web pages: landing `/`, heatmap `/heatmap/`, scan UI `/scan/`.
- Client rendering: `static/heatmap/js/home.js` and `static/heatmap/js/scan.js`.

## Data Flow

```
Scan (web or API)
  -> Validate payload
  -> Create Scan row
  -> Refresh CellAggregate (median, count)
  -> Heatmap API read
  -> Optional interpolation for empty cells
  -> Heatmap UI render
```

## Interfaces By Audience

- Staff scan UI: authenticated `/scan/`.
- Public heatmap viewer: `/heatmap/`.
- Device ingest: `POST /api/scan/`.
- Read-only integration: `GET /api/heatmap/`, `GET /api/config/`.

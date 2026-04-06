# Workflow Steps

This page captures the end-to-end operational workflow from setup to visualization.

## End-to-End Flow

1. Admin creates a `Block` and a `FloorPlan` with grid rows/cols and optional blocked cells.
2. Client posts a scan to `/api/scan/` or uses the authenticated `/scan/` UI.
3. Server validates payload and saves a `Scan` with a computed `cell_id`.
4. `refresh_cell_aggregates` updates two buckets per cell: provider and all-providers.
5. Client requests `/api/heatmap/` and receives aggregates plus optional interpolation.
6. UI renders the heatmap using dynamic min/max scaling and optional confidence overlay.

## Heatmap Read Path (Technical)

- `GET /api/heatmap/` filters by `block`, `floor`, `mode`, `service_provider`.
- If no aggregates exist, `rebuild_aggregates_for_floor` is triggered.
- Interpolated points are generated only from measured cells and never chained.

## Scan Ingestion Path (Technical)

- Supports JSON or form payloads.
- Enforces bounds and blocked-cell checks against floor config.
- `Scan.save()` recomputes `cell_id` from `grid_cols`.

# Workflow Steps

This page captures the end-to-end operational workflow from setup to visualization.

## End-to-End Flow

1. Admin creates an `Institution`, then creates `Block` + `FloorPlan` with grid rows/cols and optional blocked cells.
2. User signs up, selects an institution, and waits for approval.
3. Institution admin approves the access request.
4. Client posts a scan to `/api/scan/` or uses the authenticated `/scan/` UI.
5. Server validates payload and saves a `Scan` with a computed `cell_id`.
6. `refresh_cell_aggregates` updates two buckets per cell: provider and all-providers.
7. Client requests `/api/heatmap/` and receives aggregates plus optional interpolation and confidence.
8. UI renders heatmap with confidence, weak zones, and best-provider overlays.

## Heatmap Read Path (Technical)

- `GET /api/heatmap/` filters by `block`, `floor`, `mode`, `service_provider`.
- Access is scoped to the user’s approved institution.
- If no aggregates exist, `rebuild_aggregates_for_floor` is triggered.
- Interpolated points are generated only from measured cells and never chained.

## Analysis Path (Technical)

- `GET /api/weak-clusters/` groups weak cells into clusters for visualization.
- `GET /api/best-provider/` returns the strongest provider per cell.
- `GET /api/next-scan/` suggests the next scan target by confidence.

## Scan Ingestion Path (Technical)

- Supports JSON or form payloads.
- Enforces bounds and blocked-cell checks against floor config.
- `Scan.save()` recomputes `cell_id` from `grid_cols`.

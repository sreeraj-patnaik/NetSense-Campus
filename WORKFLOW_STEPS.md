# Workflow Steps

This page captures the end-to-end workflow from setup to visualization.

## Setup

1. Create `Block` and `FloorPlan` entries in Django admin.
2. Upload a floor image and define grid rows, cols, and blocked cells.
3. Confirm service providers in settings or defaults.

## Scan Ingestion

1. User or device submits a scan to `/api/scan/` or the authenticated `/scan/` UI.
2. Server validates block, floor, mode, cell bounds, and blocked cells.
3. A `Scan` row is saved with a computed `cell_id`.

## Aggregation

1. The new scan triggers `refresh_cell_aggregates`.
2. Median and scan count are updated for the provider bucket.
3. Median and scan count are updated for the all-providers bucket.

## Heatmap Read

1. Client requests `/api/heatmap/?block=...&floor=...`.
2. Server returns `CellAggregate` rows for the selected mode and provider bucket.
3. If enabled, interpolation fills empty, non-blocked cells.

## Visualization

1. `static/heatmap/js/home.js` scales signals to a dynamic min/max range.
2. The heatmap is rendered in smooth or contour mode.
3. Optional confidence overlay highlights higher scan density.

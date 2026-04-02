# Data Models And APIs

This page documents the core data models and the public API surface.

## Data Models

### Block

- Fields: `code`, `name`, `is_active`.
- Notes: `code` is unique and used for routing and lookups.

### FloorPlan

- Fields: `block`, `number`, `name`, `grid_rows`, `grid_cols`, `blocked_cells`, `image`, `is_active`.
- Constraints: unique `(block, number)`.
- Notes: single source of truth for grid dimensions and blocked cells.

### Scan

- Fields: `floor_plan`, `cell_x`, `cell_y`, `cell_id`, `mode`, `service_provider`, `network_name`, `signal_strength`, `created_at`.
- Indexes: `(floor_plan, mode)`, `(cell_x, cell_y)`, `(cell_id)`.
- Notes: `cell_id` is derived from `cell_y * grid_cols + cell_x` on save.

### CellAggregate

- Fields: `floor_plan`, `cell_x`, `cell_y`, `cell_id`, `mode`, `service_provider`, `is_all_providers`, `median_signal`, `scan_count`, `updated_at`.
- Constraints: unique composite key on floor, cell, mode, provider, and bucket.
- Purpose: precomputed medians for fast heatmap queries.

## API Endpoints

### `POST /api/scan/`

- Purpose: ingest a scan from a device or client.
- Auth: none, CSRF exempt.
- Payload: JSON or form body.
- Required fields: `block`, `floor`, `cell_x`, `cell_y`, `mode`, `signal_strength`.
- Optional fields: `service_provider`, `network_name`.
- Response: `{ status, scan_id, block, floor, cell_x, cell_y }`.

### `GET /api/heatmap/`

- Purpose: return aggregate heatmap points, optionally interpolated.
- Query params: `block`, `floor` required.
- Optional params: `mode` (`wifi` or `mobile`), `service_provider`, `interpolate` (`0` to disable).
- Response: array of points with `cell_x`, `cell_y`, `signal`, `count`, `interpolated`.

### `GET /api/config/`

- Purpose: return configuration needed by clients.
- Response: `blocks`, `block_floors`, `floor_configs`, `service_providers`.

## Related Implementation Files

- Models: `heatmap/models.py`.
- API handlers: `heatmap/views.py`.
- Aggregation: `heatmap/aggregation.py`.
- Interpolation: `heatmap/utils.py`.

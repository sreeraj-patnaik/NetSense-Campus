# Data Models and APIs

This page documents the core models, algorithms, and APIs that power the product.

## Data Models

### Institution

- `name`, `code`, `is_active`.
- Organization boundary for access control.

### InstitutionMembership

- `user`, `institution`.
- `status` (`pending`, `approved`, `rejected`), `role` (`member`, `admin`).
- Admins approve access requests.

### Block

- `institution` FK, `code` (unique), `name`, `is_active`.
- Ordering by `code`.

### FloorPlan

- `block` FK, `number`, `name`.
- `grid_rows`, `grid_cols` (defaults 12/8).
- `blocked_cells` JSON list, `image` upload, `is_active`.
- Unique constraint on `(block, number)`.

### Scan (raw sample)

- `floor_plan` FK, `cell_x`, `cell_y`, `cell_id`.
- `mode` (`wifi` or `mobile`), `service_provider`, `network_name`.
- `signal_strength` (dBm), `created_at`.
- Indexes: `(floor_plan, mode)`, `(cell_x, cell_y)`, `(cell_id)`.
- `cell_id` computed as `cell_y * grid_cols + cell_x` in `save()`.

### CellAggregate

- `floor_plan`, `cell_x`, `cell_y`, `cell_id`.
- `mode`, `service_provider`, `is_all_providers`.
- `median_signal`, `signal_variance`, `scan_count`, `updated_at`.
- Unique composite constraint on floor/cell/mode/provider/bucket.
- Indexes: `(floor_plan, mode, is_all_providers)`, `(cell_x, cell_y)`, `(cell_id)`.

## Core Algorithms

### Median Aggregation

- Uses Python `statistics.median` on all signals per cell bucket.
- Two buckets per cell/mode: specific provider and all-providers.
- Variance computed with `statistics.variance` when >= 2 samples.

### Interpolation

- Single-pass fill for empty cells within `max_distance=2`.
- Weight = `(1 / distance_sq) * max(1, sqrt(count))`.
- Output includes `interpolated: true` and `count: 0`.

## API Endpoints

### `POST /api/scan/`

- Accepts JSON or form body.
- Validates block, floor, mode, cell bounds, blocked cells.
- Returns `{ status, scan_id, block, floor, cell_x, cell_y }`.

### `GET /api/heatmap/`

- Required query params: `block`, `floor`.
- Optional: `mode`, `service_provider`, `interpolate`.
- Returns ordered cell list with `signal`, `count`, `confidence`, `interpolated`.
- Auto-rebuilds aggregates if none exist.

### `GET /api/weak-clusters/`

- Required: `block`, `floor`, optional `mode`, `service_provider`.
- Returns `clusters` with `size`, `avg_signal`, and `cells`.

### `GET /api/best-provider/`

- Required: `block`, `floor`, optional `mode`.
- Returns strongest provider per cell.

### `GET /api/next-scan/`

- Required: `block`, `floor`, optional `mode`, `service_provider`.
- Returns suggested `cell_x`, `cell_y`.

### `GET /api/config/`

- Returns `blocks`, `block_floors`, `floor_configs`, `service_providers`.

## Validation Rules (Scan Payload)

1. `floor`, `cell_x`, `cell_y`, `signal_strength` must be numeric.
2. `block` must exist in registry.
3. `floor` must be allowed for the block.
4. `mode` must be `wifi` or `mobile`.
5. `service_provider` validated against configured providers (or `Unknown`).
6. `cell_x`, `cell_y` within grid bounds.
7. Cell must not be blocked.
8. FloorPlan must exist.

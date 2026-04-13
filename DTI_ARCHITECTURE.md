# DTI (Design Thinking & Innovation)

This page presents the system through a Design Thinking & Innovation lens while staying implementation-grounded.

## Design Thinking (Technical Interpretation)

### Empathize (Operational Pain Points)

- Indoor signal issues are hard to localize without spatial context.
- Raw dBm values are noisy and not decision-friendly.
- Teams need clear Wi-Fi vs mobile comparisons on the same floor grid.

### Define (Problem Frame)

- Capture repeatable, validated samples tied to `block`, `floor`, and `cell`.
- Summarize signal per cell in a robust, queryable way.
- Expose a minimal API for scanners and dashboards.

### Ideate (Technical Options Considered)

- Median vs mean: median is resistant to outliers.
- Keep raw `Scan` rows to preserve auditability (not only aggregates).
- Optional interpolation to fill gaps while labeling inferred cells.

### Prototype (System Architecture Choices)

- Django monolith with core APIs: `/api/scan/`, `/api/heatmap/`, `/api/config/`.
- Analysis APIs: `/api/weak-clusters/`, `/api/best-provider/`, `/api/next-scan/`.
- Institution access control with approval-based membership.
- Grid-based indexing: `cell_id = cell_y * cols + cell_x`.
- Dual aggregation buckets: per-provider and all-providers.

### Test (Behavioral Guarantees)

- Validation rejects invalid blocks, floors, modes, and blocked cells.
- Heatmap API auto-rebuilds aggregates when none exist.
- Interpolation is single-pass and never chains inferred values.

## Innovation (Implementation-Level Highlights)

- **Dual aggregates**: `CellAggregate` stores per-provider and all-provider medians for fast queries.
- **Median aggregation**: uses `statistics.median` to reduce noise in cell values.
- **Confidence scoring**: combines scan count, variance, and recency.
- **Interpolation formula**: inverse-square distance * sqrt(count) weighting for neighbor influence.
- **Explicit labeling**: interpolated cells are tagged `interpolated: true` in API payloads.
- **Dynamic scaling**: UI normalizes min/max per fetch for consistent readability.
- **Weak-zone clustering**: groups low-signal cells for rapid triage.
- **Best-provider view**: highlights strongest carrier per cell.

## Traceable Data Flow

```
POST /api/scan/
  -> validate payload
  -> create Scan
  -> refresh CellAggregate (median, count)
GET /api/heatmap/
  -> query aggregates
  -> optional interpolation
  -> JSON payload for UI
GET /api/weak-clusters/
  -> group weak cells into clusters
GET /api/best-provider/
  -> strongest provider per cell
GET /api/next-scan/
  -> next scan target based on confidence
```

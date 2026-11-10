# UniParkingBuddy backend data contracts — FR-05 through FR-11

This implements the approved **FastAPI / CV / PostgreSQL boundary** and
the public read-only monitored-lot interface. No user-facing editing,
surveillance/enforcement, identity tracking, or additional occupancy domain
state is introduced.

## Configured monitored lots

`GET /api/lots` returns only cameras/lots actively configured in the
backend, ordered by the existing two-camera mapping:

```json
{
  "lots": [
    {
      "lot_id": "lot1",
      "display_label": "Lot 1",
      "camera": "camera_1",
      "space_ids": [1, 2],
      "total_spaces": 2,
      "has_current_data": false,
      "available_spaces": null,
      "occupied_spaces": null
    }
  ]
}
```

The IDs and counts here are **illustrative schema examples**, not a claim
about the actual number of spots in the current committed configurations.
When a camera has **no current validated occupancy result**,
`has_current_data` is false and current counts are `null` — not zero.
A camera removed from active monitoring is not listed. The unsupported
Lot 3 card is not a monitored lot and is not returned.

`GET /api/lots/{lot_id}/spaces` returns a configured, active lot with
the persistent space IDs and current state, for example:

```json
{
  "lot_id": "lot1",
  "display_label": "Lot 1",
  "camera": "camera_1",
  "has_current_data": false,
  "spaces": [
    {"id": 1, "occupied": null},
    {"id": 2, "occupied": null}
  ]
}
```

An unknown/inactive lot returns 404. `occupied: null` means no valid
current observation, **not** a third occupancy domain state. Once a
complete valid frame has been processed, each value is a boolean.
The API does not substitute older database history for missing live
camera results. Only the existing two domain states, `AVAILABLE` and
`OCCUPIED`, are ever persisted.

## Trusted structured occupancy input

The CV subsystem already runs inside the backend's trusted local process.
Its **internal** ingestion entry point is
`backend.occupancy_contract.accept_occupancy_update(repository, update)`,
which accepts the following conceptual Pydantic schema:

```json
{
  "lot_id": "lot1",
  "observed_at": "2026-10-10T12:00:00+00:00",
  "spaces": [
    {"space_id": "1", "status": "AVAILABLE"},
    {"space_id": "2", "status": "OCCUPIED"}
  ]
}
```

This is a **contract example**, not an actual database observation.
The timestamp must identify an offset-aware time. Each space ID must
be a canonical positive configured-space identifier. Empty snapshots,
duplicate IDs, unknown PostgreSQL-configured spaces, extra fields,
invalid state values, and naive timestamps are rejected before they
can alter history. The PostgreSQL repository writes both history and
current state within one transaction; an invalid/unknown ID rolls back
the entire batch, preserving the last valid stored state.

The live CV loop uses
`backend.occupancy_writer.persist_processed_observation`, which now
converts a freshly inferred boolean observation to this contract and
passes it to the trusted ingestion function. Database-free demo mode
also validates occupancy input before publishing a live result.

**Security / access boundary:** These internal functions are callable
only by the running backend; there is deliberately **no unauthenticated
HTTP POST endpoint** for occupancy changes. Public FastAPI endpoints
remain GET-only (SR-06). If a future deployment requires a separate
remote CV producer, defining authenticated transport and university-
approved network controls would require a separate explicit design
decision; it is not silently added to the read-only web interface here.

## Existing unchanged public routes

- `GET /api/status/{camera}` — current processed live observation, or
  404/503 when unknown/unavailable.
- `GET /api/history/{lot_id}/{space_id}` — bounded anonymous history.
- `GET /api/trends/{lot_id}?days=7` — descriptive sampled observations,
  **not** real-world traffic predictions.

Their existing response field names/status codes remain unchanged so
the React application is not broken by the addition of the lot APIs.
FastAPI's `/docs` and `/openapi.json` document all GET endpoints.

## Testing and traceability

- FR-05: Timestamped lot/space/status model and CV conversion.
- FR-06: Trusted ingestion of validated CV updates by the backend.
- FR-07 and FR-08: Atomic current-state and historical storage.
- FR-09: Configured monitored lots/spaces, including unavailable.
- FR-10: Existing bounded history and hourly-trend interfaces.
- FR-11 / SR-07: Input validation, no partial transactions and no
  invalid-state overwrite.
- SR-06: Web interface cannot create/alter occupancy observations.

Unit and real PostgreSQL tests cover the above; live browser and camera
acceptance tests remain separate documented work in
`docs/VALIDATION.md`. This implementation note does not amend the
submitted SRS/SOW/WBS baseline.

# PostgreSQL occupancy foundation

This implementation follows the **approved UniParkingBuddy SDD Part 2
Database Design v1.0 (September 21, 2026)**, Section 12.

## Implemented in this stage

- `backend/schema.sql`: the approved enum and four tables, with the
  documented composite keys, foreign keys, checks, and two history indexes.
- `backend/occupancy_repository.py`: data-access operations for:
  - Registering monitored lots, stable-ID spaces and their JSON polygon regions.
  - Appending a **validated, timestamped** occupancy snapshot; history and
    current state are committed together as one transaction.
  - Preserving a more recent current state when a valid older observation
    arrives, while retaining the older observation in history.
  - Summarizing a lot without treating a missing current state as Available.
  - Reading time-ordered space occupancy history.
- `backend/seed_occupancy_database.py`: explicit registration of the existing
  **Lot 1** and **Lot 2** configurations from `configs/camera_1.json` and
  `configs/camera_2.json`, respectively.
- PostgreSQL integration tests against an isolated disposable database in CI.

The SQL schema contains only `parking_lot`, `parking_space`,
`parking_space_region`, and `occupancy_record`, plus the
`AVAILABLE`/`OCCUPIED` enum. It stores **no** raw video, identity, faces,
license plates, detected-vehicle identities, or predictions.

## Local setup

Install PostgreSQL, create an **empty database** for this project, and install
Python requirements:

```sh
python -m pip install -r requirements.txt
```

Keep connection credentials private and out of Git:

```sh
# Set DATABASE_URL locally using your shell's secure environment mechanism.
# Example URL shape ONLY (replace placeholders; never commit real passwords):
# postgresql://<user>:<password>@localhost:5432/<database>
```

Apply the SDD schema **once** to the empty database, from the repository root:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/schema.sql
```

The command above uses POSIX-shell syntax; in Windows PowerShell use
`psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -f backend/schema.sql`.

Then register the **existing** JSON-configured lots/spaces:

```sh
python -m backend.seed_occupancy_database
```

The setup utility does not erase history. If PostgreSQL contains a space
missing from current JSON configuration, registration fails rather than
silently deleting historic data. Reconcile changes intentionally.

## Example Python repository usage

```python
import os
from datetime import datetime, timezone

from backend.occupancy_repository import OccupancyRepository

repo = OccupancyRepository(os.environ["DATABASE_URL"])
repo.record_observations(
    "lot1",
    [{"space_id": "1", "status": "OCCUPIED"}],
    datetime.now(timezone.utc),
)
print(repo.lot_summary("lot1"))
print(repo.space_history("lot1", "1"))
```

## Using PostgreSQL with the existing live backend

After the database schema is applied, set `DATABASE_URL` in the shell running
`python backend/main.py`, then start the
normal FastAPI/Uvicorn/OpenCV backend. The backend automatically registers configured
Lot 1/Lot 2 regions at startup and **writes each newly inferred per-space
observation before publishing that result** to the live availability API.

- Every valid inference produces a timestamped snapshot of configured
  `AVAILABLE`/`OCCUPIED` states. Repeated display frames using cached YOLO
  detections are **not** written again.
- A failed database transaction invalidates that camera's live status until
  a later valid inference commits. The API displays unavailable—not an
  unpersisted open count or false FULL status.
- If `DATABASE_URL` is **unset**, the original live, in-memory video demo
  remains available, but a startup message explicitly says that occupancy
  history **is not being persisted**.
- If `DATABASE_URL` is set but its database is inaccessible or its schema
  doesn't match the configured space identifiers, backend startup fails
  rather than silently running without persistence.
- The OpenCV `m` marking toggle is disabled **when database persistence is
  enabled**. Live edits cannot be made transactionally across the JSON file
  and PostgreSQL; edit/validate the JSON while offline, and use the explicit
  registration/maintenance procedure before resuming. Marking works as
  before in local in-memory demo mode.
- Current live availability is still served from recent processed results
  held in RAM; the database is now the source of timestamped history and
  materialized latest-valid occupancy state. Historical read API/UI and
  trend aggregation remain separate future work.

**Recorded footage caveat:** The sample videos repeat during the demo.
Observations written from these videos are valid *prototype inference events*,
not independent measurements of real-time parking conditions on campus.
Do not present demo-video aggregate patterns as evidence of actual campus
busy times. Accurate real-world interpretations require suitable genuine
timestamped footage/observations and controlled validation.

The SDD Part 1 targets FastAPI, whereas the current repository uses Flask.
This stage stays transport-neutral and does **not** silently substitute one
for the other. A deliberate API-framework decision remains necessary before
claiming full design alignment.

## Tests

The regular backend unit suite runs without a database, and the database
integration tests skip unless `TEST_DATABASE_URL` is configured.

CI starts a disposable PostgreSQL 16 server named
`uniparkingbuddy_test` and runs:

```sh
python -m unittest discover -s backend/tests -p 'test_occupancy_repository.py' -v
```

**Safety:** The database integration test suite truncates tables between
test cases and will refuse to run against any database whose exact name is
not `uniparkingbuddy_test`. Never point `TEST_DATABASE_URL` at real project
data. The GitHub workflow's simple password is only for its ephemeral,
isolated test container—not a production credential.

No benchmark accuracy, update latency, or operational availability value
is claimed by these database tests.

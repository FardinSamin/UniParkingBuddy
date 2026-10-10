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

**Important:** This is a **database-foundation stage**, not a claim that
the live CV-processing loop already writes to PostgreSQL. The existing
Flask availability endpoint still uses in-memory processed results. Camera
integration, historical trend API and frontend history/trend views are
separate next stages. This avoids silently altering the live user experience
before persistence behavior is verified in a real database.

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

# FastAPI backend transition (replaces temporary Flask)

The approved SOW/WBS/SRS require FastAPI. This stage replaces the temporary
Flask HTTP layer while **preserving** the existing React-compatible read API
contracts, PostgreSQL repository, and configured-space YOLO/OpenCV behavior.

## Running the local prototype

From the repository root, install the application requirements:

```sh
python -m pip install -r requirements.txt
python backend/main.py
```

`python -m backend.main` also works. The backend starts Uvicorn on
`http://127.0.0.1:5000` and opens the two existing OpenCV test-video
windows. The local React frontend can run separately with
`cd frontend && npm ci && npm run dev`.

The backend uses the existing `DATABASE_URL` environment variable. If
the variable is set, the PostgreSQL schema must be initialized as described
in `backend/DATABASE_SETUP.md`. If unset, live status remains available
without persistence, while history/trends return HTTP 503.

The FastAPI application is created by `backend.status_api.create_status_app`.
Importing `backend.main` no longer opens cameras, YOLO weights, GUI windows,
or a database. These resources initialize only when its `main()` function
runs. The application and CV processing loop still share a local process
for the semester demonstration, and Uvicorn is hosted in a daemon thread
so the OpenCV GUI remains on the calling thread.

## Preserved HTTP interface

| Endpoint | Behavior |
|---|---|
| `GET /api/status/camera_1` | Current configured-space states and vehicle counts |
| `GET /api/status/camera_2` | Same for Lot 2 |
| `GET /api/trends/lot1?days=7` | Last 7 days of UTC-hour observed occupancy shares |
| `GET /api/history/lot1/2` | Up to 100 newest timestamped states for Lot 1, Space 2 |

Original JSON field names, missing/unavailable responses and error codes
are preserved. The history data remains two-state (`AVAILABLE`,
`OCCUPIED`) and descriptive only. The public API remains **read-only**.

FastAPI automatically generates documentation at:
- `http://127.0.0.1:5000/docs`
- `http://127.0.0.1:5000/openapi.json`

HTTP 404 indicates an unknown camera/lot/space; 503 means no processed
current observation or unavailable historical storage; invalid trend-day
filters return 400. Failure responses retain the existing
`{"error": "..."}` format so React treats unavailable as an error,
not a false available or FULL state.

## Testing

For local API tests, install the HTTPX test client dependency
(`python -m pip install httpx`), then execute:

```sh
python -m unittest discover -s backend/tests -p 'test_*.py' -v
```

GitHub Actions runs separate unit, PostgreSQL integration and real YOLO
inference checks. Current API tests now use FastAPI's TestClient.
They verify status codes/response contracts, OpenAPI models, CORS for
read-only browser access, and absence of startup side effects on import.

## What is intentionally not part of this PR

- No new end-user feature or authentication system.
- No new public write endpoint. The separately required **trusted CV
  ingestion/validation interface** and configured-lot query responsibilities
  will be addressed in the following focused stage.
- No changes to the existing PostgreSQL schema, historical math, ROI
  geometry, YOLO confidence/classes, or frontend component appearance.
- No claimed classification accuracy or end-to-end UI timing result.

This document records an implementation change and does not revise the
approved submitted SOW, WBS or SRS.

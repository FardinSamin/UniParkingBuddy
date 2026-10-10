# Read-only historical occupancy and descriptive trends

The approved SRS/SDD UC-03 calls for descriptive historical occupancy/busy-time
information based on stored anonymous space states. It does **not** call for a
future parking availability prediction, traffic forecast, vehicle tracking, or
new occupancy domain status.

## Prerequisites

- Apply the approved PostgreSQL schema (`backend/schema.sql`).
- Configure a local `DATABASE_URL` and run `python backend/main.py`.
- Allow the camera loop to write **newly processed**, timestamped
  `AVAILABLE`/`OCCUPIED` observations.
- Run `npm run dev` from `frontend`.

If `DATABASE_URL` is absent, current status can still run in demo mode,
but historical API calls return **HTTP 503**; the UI clearly reports that
historical records are unavailable.

## Read-only API

| Endpoint | Data |
| --- | --- |
| `GET /api/trends/lot1?days=7` | Occupied observation shares grouped by UTC hour over the last 7 days; any whole-number window from 1 to 31 days |
| `GET /api/history/lot1/1` | At most 100 newest timestamped `AVAILABLE`/`OCCUPIED` observations for configured space 1 |
| `GET /api/trends/lot2` | Same descriptive view for Lot 2 |

Unknown lot/space returns 404. Invalid day windows return 400. An
unconfigured or failed PostgreSQL connection returns 503 rather than
inventing empty historical results. A known space without history returns
`has_history: false` and an empty list.

## Frontend

Navigate from the **Historical trends** button on the Lot 1/Lot 2 status
dashboard, or directly to `/history/lot1` or `/history/lot2`.

- The graph shows **24 UTC hour positions**; a dash means **no recorded
  observations in that hour**. A genuine recorded 0% is shown as 0%
  alongside the number of observations. Missing data is never a zero.
- A selected configured space shows the most recent 100 occupancy
  observations, newest first, with local-device display times.
- There are explicit loading, insufficient-history, and error states.
- The view is entirely read-only.

## Correct interpretation

The percentage for one UTC hour is:

```
recorded OCCUPIED space observations in that UTC hour
----------------------------------------------------- × 100
all recorded AVAILABLE or OCCUPIED space observations in that UTC hour
```

These are **sampled observation proportions**. They are not:
- a measurement of minutes/seconds a vehicle stayed parked,
- guaranteed real-world campus busiest hours,
- or a prediction of whether a spot will be available tomorrow.

The team's prerecorded parking videos loop in demonstration mode.
Replaying the same footage at different clock times can generate artificial
patterns. The UI explicitly warns viewers not to interpret those patterns
as actual campus busy-time evidence. Genuine time-appropriate observations,
representative collection, and controlled validation are needed for that.

## Tests

GitHub Actions runs:
- PostgreSQL integration tests for hourly group counts, time-window filtering,
  recent space history and no-data behavior.
- Flask API unit tests for safe response/error handling.
- Node frontend API-response validation tests and the production frontend
  build/lint.

Full real-video end-to-end verification and manual browser accessibility checks
are still required before declaring the complete project validated.

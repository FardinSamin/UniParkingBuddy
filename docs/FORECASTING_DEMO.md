# Future parking availability — demo infrastructure and evidence policy

**Status:** Implemented software prototype; not a measured or validated campus
traffic forecast. This extension does not revise the submitted SOW, WBS/Gantt,
SRS, or SDD. It adds no database table or migration and cannot change current
camera occupancy. All existing three-camera functions remain intact.

## What someone can do

Open the UniParkingBuddy homepage, click **Forecast availability**, choose a
future UNCP date/time and compare all three configured lots. Quick shortcuts
select 8 AM, noon, 5 PM and 9 PM on the chosen date.

- React route: /forecast
- API: GET /api/forecast?at=YYYY-MM-DDTHH:MM&mode=demo
- Time zone: America/New_York (Eastern campus local time, not viewer time)
- Dates: strictly future, up to 14 days; ambiguous/nonexistent DST hours
  are rejected with 400, as are invalid modes and date strings.
- The endpoint is GET only, with no reservations, payments or writes.
- Results report per-lot capacity, estimated open/occupied counts and share,
  source, selected time, methodology and number of historical sample days.

## The two intentionally distinct modes

### 1. mode=demo (default, no PostgreSQL needed)

The default returns a deterministic **synthetic scenario**. Illustrative
weekday/hour patterns simulate commuter vs residential parking and create
bounded whole-space example estimates. These patterns are made up, not
trained, calibrated, observed or derived from prerecorded parking-video
timestamps. No database rows are read or modified.

The interface conspicuously displays **Demo scenario — not real campus
predictions** and **SYNTHETIC DEMONSTRATION DATA**. Never describe these
outputs as campus forecasts, measured machine learning, or guaranteed
parking. They only demonstrate working UI, time input, API, computation
and comparison infrastructure.

### 2. mode=historical (operator-provenance gate)

The existing database records observed_at at the time prerecorded video
was *processed*, which is not necessarily when cars were physically parked.
Those replay timestamps are invalid training evidence for genuine campus
time-of-day behavior unless independently corrected and verified.

Historical mode stays disabled by default. Enable it **only after** an
authorized operator verifies that the stored records truly represent
real capture-time campus observations. Set both a private DATABASE_URL
and PARKING_FORECAST_TRUSTED_HISTORY=1 in the backend environment.

PowerShell example, after the provenance review (never commit credentials):

~~~powershell
$env:PARKING_FORECAST_TRUSTED_HISTORY = '1'
& .\.venv\Scripts\python.exe -m backend.main
~~~

The flag means the operator is asserting completed verification; it
does not itself verify data. The React selector remains disabled until
the backend reports the historical mode as available.

The historical method is an auditable **same-weekday/hour baseline**, not
a trained neural network:

1. Read at most 56 days of anonymous per-space observations, SELECT only.
2. Include only complete timestamps: exactly one recorded status for each
   currently configured space. Skip incomplete and duplicate snapshots.
3. Convert instants to America/New_York dates, weekdays and hours.
4. Average multiple snapshots within each calendar date/hour, so frequent
   sampling on one date is not counted as independent days.
5. Find prior samples matching the future local weekday and hour.
6. Require at least **three distinct matching calendar days**. Give each
   day equal weight, then scale the average occupied share to the lot capacity.

If data are insufficient, a lot reports status insufficient_history with
**null** estimated counts. It never silently fills missing results with
synthetic numbers or zero. Historical days/snapshots accompany every result.
There are no fabricated confidence scores or claimed accuracy metrics.

Even with verified history, this simplistic baseline cannot account for
holidays, course timetables, weather, lot changes or real parking duration.
It must be backtested before a deployment accuracy claim.

## Demonstrating the complete software workflow today

1. Check out the project; install requirements.txt in the Python environment,
   then run npm ci inside frontend. Windows obtains IANA time-zone data via
   the tzdata package in requirements.txt.
2. Start the existing three-camera backend: python -m backend.main.
3. In a second terminal run cd frontend then npm run dev.
4. Open the Vite URL and click Forecast availability on the homepage, or
   navigate directly to /forecast.
5. Choose a future date/time, compare three lot estimates, and use preset
   time buttons to show different illustrative availability.
6. Optionally request the API JSON at
   http://127.0.0.1:5000/api/forecast?at=2026-11-11T14:00&mode=demo
   (the date is valid ONLY while it is in the future; otherwise substitute
   an appropriate upcoming date).

No PostgreSQL, model training or actual camera deployment is needed
for this demonstration. No synthetic observations are inserted into the DB.
The existing live dashboard and history remain separate from future estimates.

## API contract

GET /api/forecast?at=YYYY-MM-DDTHH:MM&mode=demo

Response shape (values below are structural illustrations, NOT an actual
prediction or a specific output at a particular time):

~~~json
{
  "requested_at": "2026-11-11T14:00:00-05:00",
  "timezone": "America/New_York",
  "mode": "demo",
  "source": "synthetic_demo",
  "model": "illustrative_schedule_v1",
  "basis": "Illustrative schedule, not measured campus activity",
  "historical_enabled": false,
  "lots": [
    {
      "lot_id": "lot1",
      "display_label": "Lot 1",
      "total_spaces": 139,
      "status": "illustrative",
      "estimated_available": 42,
      "estimated_occupied": 97,
      "estimated_open_percent": 30.2,
      "historical_days": 0,
      "historical_snapshots": 0
    }
  ]
}
~~~

The response's actual lot list reflects the configured source cameras.
Historical mode changes source to verified_history, model to
weekday_hour_baseline_v1, and statuses to historical_estimate or
insufficient_history. Missing estimates are JSON null, never fake zeros.

- Invalid or out-of-window date/time, invalid mode, DST gap/fold: HTTP 400.
- Historical mode without the private verified-data gate and PostgreSQL:
  HTTP 503. Demo mode always remains independently available.
- Read failure: sanitized HTTP 503, no connection string disclosure.
- POST attempts: HTTP 405, read-only interface.

## Tests and evidence

- backend/tests/test_availability_forecast.py verifies deterministic
  illustrative estimates, DST and future time bounds, capacities,
  insufficient historical data, provenance and API failure behavior.
- backend/tests/test_forecast_repository.py runs only on a disposable
  PostgreSQL database. It tests complete snapshots, distinct days, DST,
  duplicate sampling, read-only behavior and historical cutoff.
- frontend/tests/forecastApi.test.mjs verifies time-zone defaults,
  same-origin API, result validation, integer capacity conservation,
  provenance labeling and null for insufficient samples.
- backend/tests/test_browser_react_fastapi.py covers real Chromium
  navigation, 3-lot forecast cards, changing the time, API gate,
  HTTP read-only behavior and narrow mobile viewport.
- GitHub Actions tests the frontend, backend, PostgreSQL, Chromium,
  and existing real-YOLO three-camera pipeline.

Green CI validates **software integration** only. The demo is not
measured forecasting accuracy. Before making a real-world predictive
claim, collect permissioned real-time records with trustworthy capture
timestamps, use chronological train/test separation, backtest against
human-verified occupancy, measure error and compare against a naive
baseline. Record limitations and uncertainty before any deployment.

## Non-destructive, public-repository and privacy safeguards

No changes to the approved four-table backend/schema.sql, space IDs,
existing configs, videos, submitted official baseline documents or prior
historical evidence. No new prediction table, generated personal data,
credentials or private values in Git. Existing authorization and media
licensing review remains required before public video distribution.
Forecast calculations are anonymous and read-only. No production camera
deployment or parking guarantee is implied.

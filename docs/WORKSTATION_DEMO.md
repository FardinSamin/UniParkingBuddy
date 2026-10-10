# UniParkingBuddy — controlled workstation demonstration procedure

**Status:** Execution instructions only. Do not mark any official
acceptance test as passed without actual, recorded observations.
Consult the locked SRS and [AT-01–AT-08 test record](ACCEPTANCE_TEST_RECORD.md)
for requirements and official acceptance conditions.

## Before touching equipment or test footage

1. Confirm authorization to use the intended media/location and any
   university testing/filming approvals. Reduce unnecessary exposure of
   identifiable people, vehicle plates, and other personal information.
2. Use the latest GitHub `main` code from the real repository. Record
   `git rev-parse HEAD` in the acceptance record and keep the configuration
   unchanged during a controlled test round.
3. Record team members/reviewers present, time zone, workstation OS,
   Python, Node/npm and installed package versions **actually used**.
   Use private local logs rather than committing credentials or video frames.
4. Keep the two committed source videos and manually configured JSON
   regions together: `camera_1` → `footage/stockvidsample2.mp4`,
   `camera_2` → `footage/parkinglotfootage1_1.mp4`. Their current
   configured-space IDs must come from the JSON; don't rename or invent IDs.
5. Verify local OpenCV **GUI** availability; this backend opens windows
   and cannot be presented as a headless production server. The current
   `backend/main.py` explicitly uses the prerecorded video files.
   **Physical EMEET/portable camera input has not been wired into this
   startup path; do not claim physical-camera acceptance merely by
   launching this video-based demonstration.**

## Workstation preparations (PowerShell)

Follow the [root quickstart](../README.md) to create `.venv`, install
`requirements.txt`, and run `npm ci` under `frontend`.

From the repository root, run:

```powershell
git status --short
git rev-parse HEAD
& .\.venv\Scripts\python.exe -m backend.preflight --require-gui
& .\.venv\Scripts\python.exe --version
node --version
npm --version
```

Fix every preflight FAIL before proceeding. A missing database produces
an expected warning for the **video/status-only** demo; it is not
acceptable evidence for a passing historical-trends test.

If this run includes PostgreSQL history, create a private empty database,
apply [backend/schema.sql](../backend/schema.sql) exactly once, seed
the approved configurations as described in
[backend/DATABASE_SETUP.md](../backend/DATABASE_SETUP.md), and set
`DATABASE_URL` privately in the shell that will launch FastAPI.
Then check `python -m backend.preflight --require-gui --check-db`.
Never run the CI destructive database tests against this evidence database.

## Start and inspect the prototype

In PowerShell terminal 1, from repository root:

```powershell
& .\.venv\Scripts\python.exe -m backend.main
```

Observe that **two video windows** open and show a marked polygon
for each configured space. Verify names `camera_1` and `camera_2`,
stable IDs, green open/red occupied region colors, and marked vehicle
centers. YOLO may require local processing time, especially on CPU.

In a separate terminal 2:

```powershell
cd frontend
npm run dev
```

Open the printed Vite URL (normally `http://localhost:5173`).
In the browser, check:

- Homepage shows monitored Lots 1 and 2 with current statuses; Lot 3
  remains a visibly disabled placeholder.
- Open each lot, compare available/occupied/total counts and each
  configured-space label to the current OpenCV window and API.
- Open FastAPI docs at `http://127.0.0.1:5000/docs`. The public
  routes must be GET-only for viewing, not writing occupancy.
- In another PowerShell terminal, optionally inspect current data:
  `Invoke-RestMethod "http://127.0.0.1:5000/api/lots"` and
  `Invoke-RestMethod "http://127.0.0.1:5000/api/status/camera_1"`.
- In PostgreSQL mode only, open history/trends and compare their
  dated observations to the stored sample records. Replayed video
  produces **prototype inference events**, not true campus arrival
  frequencies or predictions.

## Required controlled cases and evidence

Record each outcome in
[ACCEPTANCE_TEST_RECORD.md](ACCEPTANCE_TEST_RECORD.md);
record actual defects with reproducible steps and GitHub issue links.

| Official case | Workstation observation to capture |
| --- | --- |
| AT-01 | Authorized input through video/YOLO/polygon/backend/API/React; correct current lot/space view, with screenshot or timestamped observation |
| AT-02 | Controlled **new processed occupancy change**, start at valid backend result and stop when corresponding React view visibly changes; record actual elapsed time and observer/clock method |
| AT-03 | Independently manually count configured occupied/available/total spaces and compare with both UI and HTTP output, including FULL versus unavailable |
| AT-04 | With PostgreSQL, inspect actual timestamped stored occupancy and compare history/trend API and UI; explicitly distinguish no data from measured 0% |
| AT-05 | For each selected case, manually establish known configured-space ground truth and record whether the model classification matched it; mismatches become documented defects or reviewed dispositions |
| AT-06 | Use the independent preview/annotation workflow; calculate verified accuracy only after **every** selected frame-space row is labeled; document lighting, occlusion and other limitations |
| AT-07 | Stop an authorized input/backend or force a controlled invalid update and observe unavailable/recovery; verify old **valid PostgreSQL history** remains intact; do not deliberately damage shared data |
| AT-08 | Keyboard-only navigation, status text beyond color, responsive layout, WCAG-informed screen-reader and contrast review, read-only UI, and privacy/scope inspection |

The accuracy evaluation workflow is specified in
[ACCURACY_EVALUATION.md](ACCURACY_EVALUATION.md). Start with
`python -m backend.evaluate_accuracy prepare --output evaluation_runs/round1`
and have a **human independently fill** the blank ground-truth CSV.
Do not take the YOLO predictions as ground truth, skip obstructed cases
without documenting exclusion, or invent a required accuracy threshold.

### Do not confuse timing measurements

The automated `controlled-react-update-timing` Actions artifact records
synthetic in-memory backend state mutation → browser render via
Vite/FastAPI. It does **not** include real footage decoding, YOLO,
PostgreSQL, or a physical camera.

For SRS NFR-P02 / AT-02, a human or validated local instrumentation
must record the actual run's **newly processed valid occupancy state**
becoming available and when the React view presents that state. Write
down the observation method (e.g. synchronized local timestamps in
logs and recorded UI), uncertainty, clock references, and raw values.
No numeric SRS latency threshold has been approved; do not call a
trial passing solely because it is under an arbitrary time value.

### Controlled failures and recovery

- If the input ends or decoding fails, current live data should show
  **UNAVAILABLE**, not `0 of 0 open` or FULL; already committed
  PostgreSQL history must remain intact.
- For backend interruption, React should show unavailable; restarting
  the backend should restore status after new valid inference.
- In database mode, failed writes must not be shown as current valid
  occupancy, and stale configuration must not silently alter historical
  IDs. Back up the private demo database before destructive manual
  experiments.
- If no database is configured, history must be **unavailable**, not
  a graph pretending to represent observed campus traffic.
- If a passing vehicle's detected center intersects a configured space,
  the center-point algorithm can misclassify it. Document this limitation
  rather than claiming it recognizes parked-versus-moving vehicles.

## Local controls and safe shutdown

With a video window in focus:
- `q`: exit the backend video processing loop and release windows.
- `m`: toggle manual space marking **only without DATABASE_URL**;
  avoid editing region files during a controlled validation round.
- `1` or `2`: remove the corresponding camera from active monitoring
  for this run; use only in a recorded failure/recovery test, and restart
  for a fresh two-camera baseline.

Terminate Vite in its PowerShell terminal with `Ctrl+C`. If you used
a local private PostgreSQL database, keep only necessary, access-
controlled anonymous evidence; do not publish raw recorded frames,
screenshots with identities, passwords, or database connection URIs.

## What cannot yet be signed off by automation alone

The current tested code uses authorized **prerecorded media**, not the
actual portable camera. There is **no real, independently verified
accuracy percentage** until human annotation is completed, and there
is **no observed full processed occupancy → React timing** until the
integrated acceptance run is measured. A targeted Chromium keyboard
test does not constitute complete WCAG 2.2 A/AA conformance.

Leave unexecuted acceptance fields pending and record each defect and
retest. The final acceptance sign-off belongs to the project team and
reviewers based on evidence, not an automated PR merge.

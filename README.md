# UniParkingBuddy

**University of North Carolina at Pembroke · CSC 4900 · Fall 2026**

UniParkingBuddy is a **prototype** campus-parking availability viewer.
Authorized prerecorded test videos or a separately approved portable
camera setup are processed with YOLO/OpenCV against **manually configured**
parking-space polygons. FastAPI serves current availability to a
read-only React + TypeScript interface. Optional PostgreSQL persistence
records anonymous, timestamped `AVAILABLE`/`OCCUPIED` observations and
descriptive history.

The committed example setup uses **two monitored lots**:
- Lot 1: `camera_1` → `footage/stockvidsample2.mp4`
- Lot 2: `camera_2` → `footage/parkinglotfootage1_1.mp4`

**Lot 3 is not monitored.** The existing placeholder card is intentionally
disabled. The system does not automatically discover parking stalls,
identify people/plates/specific vehicles, reserve spaces, take payments,
enforce parking, or predict future occupancy. Replayed video observations
must **not** be presented as current campus traffic.

## Windows quick start — sample-video demo (no database required)

Use a fresh clone of this repository, not an older downloaded ZIP.
These commands are for **PowerShell** opened in the clone's root.

**1. Install the prerequisites:** Git, Python **3.11** (the version used
by CI), Node.js **22** and npm. A local graphical desktop is required
for the OpenCV video windows. Node 22 and Python 3.11 are **tested CI
versions**, not invented mandatory university specifications.

```powershell
git clone https://github.com/FardinSamin/UniParkingBuddy.git
cd UniParkingBuddy
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

If the `py -3.11` launcher is not installed, use the installed Python
3.11 executable to create `.venv`. The direct `.venv\Scripts\python.exe`
commands do **not** require changing PowerShell's script-execution policy.

**2. Run the read-only readiness check** (from the repo root):

```powershell
& .\.venv\Scripts\python.exe -m backend.preflight --require-gui
```

Expected: `[PASS]` for required files, both decoded video frames,
configured polygons and packages. A `[WARN]` about unset
`DATABASE_URL` is expected when running **without** historical storage;
it is not a false success for the historical trends page. A `[FAIL]`
means fix that problem before attempting the demo. This check does not
load YOLO weights, open application video windows, or write database rows.

**3. Start the backend and video windows**, in PowerShell terminal 1
from the repository root:

```powershell
& .\.venv\Scripts\python.exe -m backend.main
```

FastAPI listens on `http://127.0.0.1:5000`. If a video window has
focus, press `q` to exit cleanly. In the database-free development
mode, `m` toggles **manual** polygon marking; changes to the actual
JSON region configs are persistent. Do not edit polygons during
validation without recording the new configuration and corresponding
test conditions. With PostgreSQL enabled, live marking is disabled.

**4. Start React**, in a **separate** PowerShell terminal 2:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:5173` (or the URL Vite prints). The browser
requests `/api` through Vite's same-origin development proxy.
The webpage should display two monitored cards and the disabled Lot 3
placeholder. Open Lot 1/Lot 2, verify configured-space text states
and counts. **Historical trends will be unavailable** with no database.

To inspect FastAPI: `http://127.0.0.1:5000/docs`,
`/api/lots`, `/api/status/camera_1`. Loading/unavailable is the
correct state before a valid occupancy result or during a failure:
it must not be rendered as FULL.

## Optional PostgreSQL demo (history enabled)

Create an **empty private database** in local PostgreSQL, configure
`DATABASE_URL` in the backend terminal without committing the URL or
password, then initialize the schema **once**:

```powershell
# Supply your private, valid PostgreSQL connection URI in this shell.
# Do not paste real credentials into the shared repo, screenshots or chat.
psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -f backend/schema.sql
& .\.venv\Scripts\python.exe -m backend.seed_occupancy_database
& .\.venv\Scripts\python.exe -m backend.preflight --check-db --require-gui
& .\.venv\Scripts\python.exe -m backend.main
```

The schema and seed commands above require the environment variable to
be set to your actual private PostgreSQL connection URI first. They
should **not** be run repeatedly as a reset mechanism, and must **never**
target a production or shared database accidentally. The schema/seed
instructions and constraints are in
[backend/DATABASE_SETUP.md](backend/DATABASE_SETUP.md).

If `DATABASE_URL` is set but PostgreSQL is unavailable or the configured
space IDs differ, startup fails rather than silently pretending history
works. Recorded test-video history is **demo replay evidence**, not a
real-time campus-usage study.

## Calibrate parking-space geometry before evaluating car matching

The included JSON files currently cover **seven** spaces in camera 1 and
**four** in camera 2. Many other parked vehicles visible in the sample
videos are intentionally **unassigned** until their stalls are configured.
Do not interpret an unassigned detection as proof the car is outside the lot.

Stop the running backend and, from the repository root, run the paused-frame
manual calibration editor for one camera:

```cmd
.venv\Scripts\python.exe -m backend.calibrate_spaces --camera camera_1 --frame 0
```

The GUI lets an operator mark four corners of each physical stall, see
stable existing IDs, and explicitly save a validated JSON configuration
with a local backup. No automatic line inference or accuracy guarantee
is implied. For instructions and the second camera see
[parking-space calibration](docs/PARKING_SPACE_CALIBRATION.md).
The original center-point vehicle association remains a known limitation
pending separate validation of improved matching.

## Experimental automatic location discovery (read-only)

The proposed **camera-adaptive** method is being developed separately from
the approved, manually configured parking-space baseline. Its first stage
groups recurring **anonymous vehicle positions** across sampled frames of
any suitable fixed-view video; it produces **unverified vehicle-location
hypotheses**, not verified stall boundaries or occupied/available states.
It does **not** detect parking lines yet, alter configs or write database rows.

From the repository root, to try this with the included first video:

```cmd
.venv\Scripts\python.exe -m backend.discover_space_hypotheses --video footage/stockvidsample2.mp4 --output evaluation_runs/discovery_camera1
```

Review local `hypotheses.json` and `preview.png`. Use a new output folder
for each experiment. The preview may include people or vehicle details;
do not publish it without appropriate permission/privacy review.
[Experiment instructions and limitations](docs/EXPERIMENT_AUTOMATIC_DISCOVERY.md)

### Phase 2 — Painted parking-line and candidate quadrilateral evidence

The additional **read-only** offline command inspects bright, persistent
marking strokes, pairs plausible neighboring separators into **unverified
quadrilateral suggestions**, and optionally compares them to the Phase 1
vehicle-location evidence:

```cmd
.venv\Scripts\python.exe -m backend.discover_stall_geometry --video footage/stockvidsample2.mp4 --output evaluation_runs/geometry_camera1 --hypotheses evaluation_runs/discovery_camera1/hypotheses.json
```

Use a **new output folder**; omit `--hypotheses` if Phase 1 data is absent.
Outputs are local previews and `stall_candidates.json`; they are **not**
approved space regions or valid evidence of occupancy. Bright lane edges,
vehicle contours and camera perspective can generate false candidates.
See [Phase 2 instructions and limitations](docs/EXPERIMENT_STALL_GEOMETRY.md).

**New pavement-contrast gate:** Following the first Windows review in which
Phase 3 shortlisted zero shapes out of 39, Phase 2 can test for bright
strokes against darker surroundings on **both sides**, before creating
review-only polygons, when explicitly run with `--ground-filter`. It also saves `ground_line_evidence.png` (green
ground-like, red rejected) and raw-versus-gated counts. Use a *new output*
folder when rerunning; this does **not** guarantee correct stall discovery,
especially on bright pavement and occluded/moving viewpoints. The default remains **ungated** because the three-frame smoke check
reduced camera 1's 51 raw candidate shapes to 7, and camera 2's 37 to
1; that is not verified accuracy, and may reject real stalls.
Use `--ground-filter` only for research comparison with an independent
output folder. See the updated Phase 2 experiment instructions.

### Phase 4 — Compare joined parking-row markings (read-only)

A separate experiment joins short, locally collinear painted-line
observations, then compares candidate-stall geometry from **raw** versus
**ground-supported** strokes. It deliberately does not add any unverified
stall to the live system:

```cmd
.venv\Scripts\python.exe -m backend.row_continuity_experiment --video footage/stockvidsample2.mp4 --geometry evaluation_runs/geometry_camera1_ground/stall_candidates.json --hypotheses evaluation_runs/discovery_camera1/hypotheses.json --output evaluation_runs/row_continuity_camera1
```

Check both `row_candidates_raw.png` and `row_candidates_ground.png`,
as well as joined-stroke previews and the full `row_comparison.json`.
See [line-continuity experiment and caveats](docs/EXPERIMENT_ROW_CONTINUITY.md).

### Independent geometry benchmark — measure real stall discovery

Rather than repeatedly tuning threshold rules from preview images, mark a
small region of **all verifiable true parking stalls** in the original video
(including empty bays) and compare proposed polygons with one-to-one IoU
matching. Human annotations stay in ignored `evaluation_runs/` and do
**not** become production configurations.

```cmd
.venv\Scripts\python.exe -m backend.stall_discovery_benchmark annotate --video footage/stockvidsample2.mp4 --frame 0 --output evaluation_runs/stall_benchmark_camera1
```

Press R then click two region corners, mark four corners of **every**
verifiable stall inside it, then S to save local human reference geometry.
Compare **both** Phase 4 variants and full-versus-shortlisted candidates:

```cmd
.venv\Scripts\python.exe -m backend.stall_discovery_benchmark score --truth evaluation_runs/stall_benchmark_camera1/ground_truth.json --proposals evaluation_runs/row_continuity_camera1/row_comparison.json --output evaluation_runs/stall_benchmark_camera1/phase4_scores.json
```

See [independent discovery benchmark and bias limitations](docs/EXPERIMENT_STALL_DISCOVERY_BENCHMARK.md).
Geometry precision/recall is **not** configured-space occupancy accuracy.




### Phase 3 — Rank unverified stall hypotheses and filter likely car artifacts

Once Phase 1 and Phase 2 have generated their **local** reports, use the
read-only quality-review command:

```cmd
.venv\Scripts\python.exe -m backend.review_stall_candidates --video footage/stockvidsample2.mp4 --geometry evaluation_runs/geometry_camera1/stall_candidates.json --hypotheses evaluation_runs/discovery_camera1/hypotheses.json --output evaluation_runs/review_camera1
```

This compares shared parking-row separators, recurring vehicle evidence,
and obviously too-small roof/window-like candidates. It produces a **review
shortlist**, not approved parking polygons. See the
[Phase 3 review procedure](docs/EXPERIMENT_STALL_QUALITY_REVIEW.md).


and [research architecture](docs/RESEARCH_ADAPTIVE_SPACE_DISCOVERY.md).

## Validation and team reproduction

- [Workstation demonstration and evidence checklist](docs/WORKSTATION_DEMO.md)
- [Acceptance cases AT-01–AT-08](docs/ACCEPTANCE_TEST_RECORD.md)
- [Controlled human-verified CV accuracy](docs/ACCURACY_EVALUATION.md)
- [End-to-end validation plan](docs/VALIDATION.md)
- [Accessibility and manual WCAG review](docs/ACCESSIBILITY_REVIEW.md)
- [FastAPI and public API contracts](docs/FASTAPI_MIGRATION.md) /
  [docs/API_CONTRACT.md](docs/API_CONTRACT.md)
- [React/Vite networking and second-device instructions](frontend/README.md)

The accuracy workflow requires independently labeled ground truth.
The CI timing measurements use **synthetic** backend states, not
physical-camera capture-to-browser times. Neither is an invented
pass threshold.

### Basic project checks

From the root (with Python dependencies installed):

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py" -v
```

Some PostgreSQL/real YOLO/Chromium tests intentionally **skip** without
their dedicated CI test conditions. Do not treat these skips as passes.
From `frontend`:

```powershell
npm test
npm run lint
npm run build
```

GitHub Actions covers backend tests, PostgreSQL integration, real YOLO
inference on committed videos, Chromium UI navigation, and controlled
synthetic frontend timings. It does **not** establish physical-camera
performance, ground-truth accuracy or complete accessibility conformance.

### Privacy and deployment notes

No raw video is written to PostgreSQL by default. Conduct campus
testing only with approved equipment/media and permissions. Never
publish identifiable video frames, credentials or unreviewed
accuracy/performance claims.

The Vite proxy runs in development only. Static React production
builds need an authorized web server to forward `/api/*` to FastAPI
and serve client-side routes (see [frontend/README.md](frontend/README.md)).
Do not expose the local development server, camera windows or PostgreSQL
to the public internet.

**Source of truth:** submitted SOW, WBS/Gantt, SRS and SDD documents
remain the locked requirements/design baseline. This README describes
the current implementation and does not revise those submissions.

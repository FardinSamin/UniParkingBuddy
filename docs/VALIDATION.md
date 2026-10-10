# End-to-end validation plan — UniParkingBuddy

## What automated CI proves

The normal pull-request checks cover:

- React TypeScript compilation, lint, production build and API contract tests.
- PostgreSQL schema, atomic persistence, historical records and sampled
  trend queries against an isolated test database.
- **First-frame decoding** of both committed sample videos using OpenCV,
  and confirmation that all configured polygon corners fit their source
  frame dimensions.
- Headless synthetic detection boxes -> OpenCV polygon association ->
  stable IDs -> transactional PostgreSQL write -> FastAPI current, history
  and trend endpoints. It checks that a vehicle **outside** configured
  regions does not raise occupied-space counts.
- A forced failed write or stopped video makes live status unavailable,
  while already committed history remains retrievable.

A separate dedicated CI job now **loads the committed YOLO weights and runs
actual CPU inference** on frames 0 and 30 of both configured test videos. It
checks COCO vehicle class mapping, bounding box validity, and consistency of
resulting configured-space IDs/states. This is a **model/pipeline smoke test**,
not independent manual verification of parking accuracy.

Automated tests still do **not** check OpenCV window interaction, verify
frontend layout in a browser, or establish camera availability,
ground-truth classification accuracy or response-time guarantees.

## Workstation acceptance test (manual and evidence-based)

Use a fresh clone/checkout of `main` after the relevant PR has been
merged. Ensure the committed footage files, `yolo26n.pt`, and
`configs/camera_1.json` and `configs/camera_2.json` exist locally.

1. Install requirements, and (optionally) create a private PostgreSQL
   test database, apply `backend/schema.sql`, and set `DATABASE_URL`
   **locally**. Do not commit connection strings or passwords.
2. Start `python backend/main.py` in one terminal. Start the frontend
   with `npm ci` and `npm run dev` from `frontend` in another.
3. Check that both windows load the correct video and configured regions,
   each with stable identifiers. Confirm Lot 3 says Coming Soon and
   is not clickable.
4. Watch a frame where a detection center is inside a configured space:
   its **red SPACE N** marker and the correct configured-space occupancy
   should agree with the HTTP API and React dashboard.
5. Watch a detection **outside** every configured region: its **yellow
   OUTSIDE SPACE** marker and count must not change any space to occupied.
6. Compare visible results against **manually verified** Open/Occupied
   states for the configured spaces, using an independently reviewed
   set of test images or time-stamped frame observations.
7. Stop/unplug/unavailable the backend or input source and verify that
   React reports data **unavailable**, not FULL or `0 of 0 open`.
8. With a PostgreSQL connection, verify fresh inference observations
   appear in `occupancy_record` with matching lot/space IDs, states
   and timezone-aware times. Retry a known valid frame after any failure
   and confirm recovery. Never assume that repeated video playback is
   new real-world traffic.
9. Open Historical trends for Lots 1/2. Verify correct HTTP/API responses,
   time-zone wording, per-space records, and distinction between a recorded
   0% hour and an hour with **no observations**. On no database, it
   must show an unavailable message.
10. Confirm the app is usable with keyboard navigation, visible focus,
    readable labels in addition to colors, and on a narrow viewport.

## Reproducible manually verified accuracy workflow

The ground-truth evaluation tools and full labeling guide are in
[ACCURACY_EVALUATION.md](ACCURACY_EVALUATION.md).

Use `python -m backend.evaluate_accuracy prepare` to sample frames
systematically and generate preview images with **only** configured-space
outlines. A reviewer must independently label each `AVAILABLE` /
`OCCUPIED` condition before running and scoring the YOLO predictions.
Unverifiable images can be explicitly excluded from the denominator but
must be counted. Incomplete annotations produce **no accuracy claim**.

Unit tests use deliberately synthetic labels to verify the evaluator; they
are not evidence of the system's real detection accuracy.

## Controlled accuracy and update-time evidence

**Accuracy:** Record the number of configured-space classification results
that match manually verified Occupied/Available ground truth, divided by
the total number of evaluated configured-space results. Identify precisely
which spaces, frames/test conditions and annotation approach were used.
Do not claim any fixed pass threshold unless the team has approved one.

**Update behavior:** Observe and record elapsed time from newly processed
occupancy results becoming available to their display in the React UI
during system testing. Keep a log of conditions and measured timings.
The approved baseline does **not** stipulate a fixed numerical latency
or accuracy guarantee.

Suggested evidence fields: test run date, git commit, video/camera input,
configured-space IDs, frame/time reference, manually verified state,
observed model state, correctness, time measurement method, raw timing,
and notes for occlusions/edge cases. Do not collect personal identities,
license plates, or face crops.

## Findings and follow-up

If the test reveals a YOLO misclassification or a passing vehicle
crossing a configured space, record that counterexample. The current
geometric matching algorithm is not a parked-versus-moving classifier.
Do not describe it as one, and do not invent accuracy metrics.

The history graph currently describes **stored observed space samples**.
With looping demonstration video it is inappropriate to infer actual
peak campus parking hours from those samples.

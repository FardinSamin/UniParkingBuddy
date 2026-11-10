# Repository recovery and reproducibility reconciliation — November 10, 2026

Repository: FardinSamin/UniParkingBuddy  
Original main: 0f398d2ea5ebed85ad87aa2327e65b2d93b02ad7 (recover)  
Preservation reference: 68ef36ae79d0616159eced1488706492c26c7819  
Recovery branch: repair/reconcile-three-camera-recovery  
Review: https://github.com/FardinSamin/UniParkingBuddy/pull/42

This is an implementation and recovery record, not a revision to the
submitted SOW, WBS/Gantt, SRS or SDD requirements baseline.

## Non-destructive recovery policy

- Preserve all current camera code, tests, configs, footage, history and
  project documentation. Do not reset to the older two-camera prototype.
- The November 10 recovery commit restored 30 backend test files, 15 documents,
  configs/README.md, and the two active medium-model weights.
- This repair branch restores the root .gitignore, yolo26n.pt and
  yolo26n-obb.pt using the **exact historical Git blob IDs** from 68ef36a,
  rather than replacing model files with placeholders or downloading
  unverified substitutes.
- The nano detection model is used by the legacy evaluation/research code,
  but **not** by any active camera.
- The nine previously tracked backend/__pycache__/*.pyc files remain in the
  branch: restoring .gitignore stops new untracked bytecode but does not
  remove already tracked files. Generated-artifact cleanup requires a
  separate reviewed decision; no source or test was removed here.
- The main branch was unprotected at audit time. Admins should configure
  reviewed PRs and required status checks. This PR does not claim to have
  modified GitHub repository settings.

## Current code inventory

| Lot | Source camera | Video | Deployed weights | Matching | Configured spaces |
| --- | --- | --- | --- | --- | ---: |
| Lot 1 | camera_1 | footage/stockvidsample2.mp4 | yolo26m.pt | overlap | 139 |
| Lot 2 | camera_2 | footage/parkinglotfootage1_1.mp4 | yolo26m.pt | overlap | 57 |
| Lot 3 | camera_3 | footage/parkinglot3.mp4 | yolo26m-obb.pt | center | 69 |

The FastAPI server serves read-only current states; PostgreSQL, when
explicitly configured, persists anonymous timestamped observations in
the existing approved four-table model. All three sources are currently
prerecorded demonstration videos, not a validated physical camera
installation. Descriptive hourly trends do not predict future parking
availability.

## Schematic consistency, without fabricated geometry

The backend camera polygons and the separate frontend schematics are
distinct coordinate systems.

| Lot | Backend IDs | Schematic IDs | Unmapped source IDs |
| --- | ---: | ---: | --- |
| 1 | 139 | 132 | 10, 54, 94, 116, 117, 138, 139 |
| 2 | 57 | 48 | 37 through 45 |
| 3 | 69 | 69 | none |

The UI now visibly lists the live occupancy state of any configured
space lacking a verified schematic polygon. Browser integration tests
assert that map labels plus the list account for all configured IDs.
A separate human geometry review is still necessary to locate the
remaining 16 positions on the schematic images. Do not invent them.

## Reconciliation of tests and evaluation

- Browser tests were updated from two-lot, disabled-Lot-3 and obsolete
  HTML grid assumptions to the real three-lot, SVG-based React interface,
  checking keyboard navigation, current counts, history and recovery.
- The actual CPU YOLO model and PostgreSQL integration tests now exercise
  Cameras 1, 2 and 3 with their active medium and aerial weights and
  per-camera detection/matching rules, not just the legacy nano model.
- Independent evaluation uses version-2 manifests with all three source
  videos, each detector's exact model/configuration hashes and settings.
  Predictions use the live matching rules by default, and save provenance
  plus a checksum to prevent silent substitution. Archived version-1
  two-camera nano-model annotations remain readable and scorable.
- Regression fixtures are explicitly synthetic. Smoke tests establish
  software compatibility, not independently verified CV accuracy.

The first fully green revision was 9455a35b75e3e5f4eedb3cc7d4e1480760716bdc:
https://github.com/FardinSamin/UniParkingBuddy/actions/runs/42835016194

Five CI jobs must pass again on the **latest PR head** before merging:
backend unit/configuration; PostgreSQL; real YOLO/video/DB/API;
frontend lint/tests/build; Chromium/Vite/FastAPI.

## Outstanding real acceptance and governance

- Perform an authorized real Windows workstation run of all three
  OpenCV windows and verify UI/API behavior with recorded evidence.
- Obtain independently human-reviewed configured-space ground truth
  before making any accuracy claim.
- Do not claim physical portable-camera acceptance without a real test.
- Verify the 16 undrawn schematic positions against source maps.
- Complete manual accessibility review and the existing AT-01–AT-08
  acceptance worksheet without inventing passing outcomes.
- Review permissions, personal information and media licensing for all
  committed footage/images before distributing a public demonstration.
- Configure appropriate branch protections through GitHub administration.

No synthetic result is reported as observed campus traffic. No numerical
accuracy threshold or latency commitment is fabricated. No future
parking-availability forecasting engine is part of this recovery.

See README.md, docs/VALIDATION.md, docs/ACCURACY_EVALUATION.md,
docs/WORKSTATION_DEMO.md, and docs/ACCEPTANCE_TEST_RECORD.md.

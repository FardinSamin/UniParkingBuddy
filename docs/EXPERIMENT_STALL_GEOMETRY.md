# Phase 2 experiment: persistent painted lines and stall-geometry candidates

**Status:** Experimental, read-only candidate detection; **not** a validated
automatic parking layout. This extends
[Phase 1 recurring vehicle-location hypotheses](EXPERIMENT_AUTOMATIC_DISCOVERY.md)
and follows the
[research-backed architecture](RESEARCH_ADAPTIVE_SPACE_DISCOVERY.md).
The submitted SRS/SDD and existing stable-ID manually configured spaces
remain the approved baseline.

## Why two evidence streams?

Phase 1 groups recurring detections, so it tends to find *vehicles*
rather than complete marked stalls. A vehicle can remain stopped in a
traffic lane; a legitimate empty stall can be missing entirely.
Phase 2 independently finds **paint-like** (white/yellow) pixels visible
across several frames, identifies line strokes using Canny+Hough, merges
close duplicate paint edges, and proposes possible quadrilaterals by
pairing adjacent approximately parallel strokes with overlapping depth.

Vehicle hypotheses can then **corroborate** a line-pair suggestion when an
anonymous approximate ground-anchor lies inside its quadrilateral.
This does not prove that the shape is a legal parking stall, that its
quadrilateral covers the full stall, or that any particular vehicle is
parked. No one-to-one vehicle assignment or occupancy classification is
performed by this tool.

This is not a trained parking-marking detector. It is an **interpretable
geometric baseline** that we can inspect, test and improve before considering
segmentation or specialized parking-line models.

## Windows CMD commands

Update the repository after PR is merged. **You do not need to start React
or FastAPI** for this offline experiment.

```cmd
cd /d C:\Users\Fardin\UniParkingBuddy
git pull --ff-only
.venv\Scripts\python.exe -m backend.discover_stall_geometry --video footage/stockvidsample2.mp4 --output evaluation_runs/geometry_camera1 --hypotheses evaluation_runs/discovery_camera1/hypotheses.json
```

If you did not run Phase 1 or no longer have its output, simply **omit**
`--hypotheses` to inspect paint/geometry alone:

```cmd
.venv\Scripts\python.exe -m backend.discover_stall_geometry --video footage/parkinglotfootage1_1.mp4 --output evaluation_runs/geometry_camera2
```

You can also use `--video "C:\some\authorized\fixed_view.mp4"` and any
new output folder. For controlled experiments, `--frames 12` and
`--paint-support 0.5` may be changed, but these are trial engineering
parameters, **not accepted accuracy thresholds**. Every experiment must
use a new output directory. The script does not overwrite prior evidence.

Open the generated overlays:

```cmd
start "" "evaluation_runs\geometry_camera1\geometry_preview.png"
start "" "evaluation_runs\geometry_camera1\persistent_markings.png"
```

The files contain:

- `persistent_markings.png`: bright paint-like pixels retained across
  sampled frames, not a verified marking classifier.
- `geometry_preview.png`: thin **yellow** stroke detections; numbered
  **cyan** geometry-only hypotheses or **magenta** hypotheses with Phase 1
  vehicle-anchor corroboration. All are unverified.
- `stall_candidates.json`: image coordinates of suggested quadrilaterals,
  paired strokes, relative geometry ranking, optional matching Phase 1
  proposal IDs, video checksum, frames, and limitations.

If `--hypotheses` is supplied from **a different video**, processing
fails rather than fusing incompatible geometry. The number of candidates
can be zero, and many can be false/duplicated. Neither zero nor many
candidates proves anything about real parking availability.

## Improvement after the Phase 3 zero-shortlist result

In the October 10 demonstration, Phase 2 produced 39 shapes and the
Phase 3 reviewer shortlisted **zero**, flagging 31 shapes as possible
car-surface artifacts. That is **not** a successful stall layout.
The problem begins upstream: persistent bright paint-like pixels include
stationary car roofs, windows, curbs and background objects.

This version adds a **dark-ground contrast evidence gate** before Phase 2
pairs the lines into quadrilaterals. It checks whether a candidate stroke
has a visibly brighter center than the regions on **both sides** over the
sampled video frames. A parking stripe on dark asphalt often has this
property; a car roof/window edge usually does not.

This is **not a road segmentation network** and it can miss legitimate
markings on bright concrete or heavily obscured lanes. If the count is
zero, treat it as *no evidence found*, not an empty lot. Never relax the
gate merely to produce more polygons without checking source frames.

To compare against the earlier run on your Windows PC, generate a **new**
Phase 2 experiment directory:

```cmd
cd /d C:UsersFardinUniParkingBuddy
git pull --ff-only
.venvScriptspython.exe -m backend.discover_stall_geometry --video footage/stockvidsample2.mp4 --output evaluation_runs/geometry_camera1_ground --hypotheses evaluation_runs/discovery_camera1/hypotheses.json
start "" "evaluation_runsgeometry_camera1_groundground_line_evidence.png"
start "" "evaluation_runsgeometry_camera1_groundgeometry_preview.png"
```

**Review both images.** In `ground_line_evidence.png`, green strokes
have supporting paint-on-ground contrast; red strokes were rejected.
The new `stall_candidates.json` records *raw line count*, *ground-supported
line count*, *raw ungated geometry count* and *gated geometry count*.
These counts are evidence about the algorithm only, not how many stalls
actually exist. The data still contain **unverified** proposals.

To reproduce the earlier algorithm for a controlled comparison, use
`--no-ground-filter` with a **different output folder**; do not overwrite
prior evidence. The experiment's `--ground-min-fraction` option adjusts
a heuristic, not a course-level performance requirement.

For the existing Phase 3 reviewer, use the newly generated geometry file
and another new output folder:

```cmd
.venvScriptspython.exe -m backend.review_stall_candidates --video footage/stockvidsample2.mp4 --geometry evaluation_runs/geometry_camera1_ground/stall_candidates.json --hypotheses evaluation_runs/discovery_camera1/hypotheses.json --output evaluation_runs/review_camera1_ground
start "" "evaluation_runseview_camera1_groundeview_preview.png"
```

If very few true stalls survive, capture the **missed marked separators**
as false negatives and improve scene-ground estimation/parking-row
geometry before adding further heuristics. We have **no independent
measured precision/recall** yet; even a visually cleaner overlay does not
prove generalization to unseen lots.

## Human review protocol

For each candidate L001 etc., examine the **original video frames**, not
just the overlay. Verify: two genuine stall-side lines, correct shared
endpoints, plausible near/far boundaries, row alignment, whether it lies
in a driving lane, and whether the line evidence is blocked by vehicles.

Record private decisions: **confirmed marked stall / false candidate /
uncertain**, plus missed visible stalls. A successful experiment may
identify some previously unseen **empty** marked stalls, but a proposed
quadrilateral is still a hypothesis, not an approved map.

**Never copy `suggested_quadrilateral_xy` directly into live
`configs/camera_*.json`**, and do not use proposed counts in React or
PostgreSQL. Geometry ranking is not calibrated confidence. A later
explicit approval interface and full validation must happen first.
The existing manual calibration editor is available as a correction
fallback after the real boundaries are checked.

The local `evaluation_runs/` folder is Git-ignored; previews can
include people, faces or license plates from the source video. Do not
publish previews, raw frames or private images without permission.

## Known shortcomings

- Long white edges on cars, curbs, buildings or lane markings can survive
  multi-frame thresholding and be proposed as stalls.
- Shadows and changing lighting may suppress actual painted lines.
- A partially occluded line may be shortened, yielding an incorrect
  depth estimate or no candidate at all.
- Two approximately parallel separators may not define the actual legal
  parking bay; a third/fourth boundary and lane geometry must be reviewed.
- Perspective changes pixel width/depth ratios across the view; this
  baseline does not calculate a ground-plane homography.
- Camera motion, zoom and video editing may invalidate the fixed-coordinate
  assumption and must be detected before promoting maps.
- Nearby candidates and missing spaces require human reconciliation.
- A corroborating stationary vehicle in an illegal position still does not
  establish a legitimate parking bay.

**Next research steps:** robust line-junction/entrance detection, row-level
perspective consistency, lane exclusion, and controlled human-reviewed
stall-boundary labeling on held-out fixed-camera views. Compare proposals
against independently verified stall polygons, separately from the SRS
configured-space Occupied/Available accuracy measurement. No numeric
accuracy or portability commitment is made by this Phase 2 prototype.

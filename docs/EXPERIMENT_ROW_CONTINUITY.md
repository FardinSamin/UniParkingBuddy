# Phase 4 experiment: join observed parking-row line fragments

**Status:** Offline, unverified research experiment. This does **not**
identify legal stalls or alter SRS-required monitored-space configuration.

The October 10 Windows result showed a partial success: many real parking
stall dividers survived the new contrast filter, but a subset of car edges
also survived. Camera 1 had 289 raw bright line segments, 126
ground-contrast-supported segments, 39 ungated quadrilateral proposals,
and 7 ground-filtered proposals. Those are **algorithm counts**, not
ground-truth parking-space totals.

Our next hypothesis is that **visible painted dividers are fragmented**
by glare, occlusion, shadows, and Hough extraction. Treating each fragment
as a complete edge yields shallow or mismatched potential stall polygons.
A real parking row often has multiple similarly oriented, spaced divider
strokes; we should compare whether joining locally collinear observations
helps recover the intended physical geometry.

## What this experiment adds

- Read a prior Phase 2 `stall_candidates.json` report and verify that
  its SHA-256 matches the actual input video.
- Read **all** raw detected line segments and **all** ground-contrast
  supported segments directly from Phase 2's existing evidence array.
- Conservatively join short fragments that are nearly collinear and close
  enough along the same line. The merged stroke endpoints are limited to
  observed extrema. The JSON explicitly records the number of observed
  pieces and the fraction of the joined span backed by visible strokes.
  Gaps remain **uncertain**; no invisible painted line is confirmed.
- Independently create candidate quadrilaterals and run our Phase 3
  ranking for **both** raw-line and ground-supported-line variants.
- Preserve `weak_evidence` and `likely_artifact` candidates in the JSON
  even if they are hidden in shortlist preview images.
- Do **not** write to cameras, approved `configs/`, PostgreSQL,
  occupancy history, or React; no permanent camera/vehicle tracking.

This tests **line continuity**, not complete perspective rectification,
end-junction detection, a validated parking-row model, or automatic
parking-stall acceptance.

## Windows CMD steps

Phase 2 results from the preceding test are sufficient. Start from the
project root, pull the latest merged code, then run:

```cmd
cd /d C:\Users\Fardin\UniParkingBuddy
git pull --ff-only
.venv\Scripts\python.exe -m backend.row_continuity_experiment --video footage/stockvidsample2.mp4 --geometry evaluation_runs/geometry_camera1_ground/stall_candidates.json --hypotheses evaluation_runs/discovery_camera1/hypotheses.json --output evaluation_runs/row_continuity_camera1
```

To examine the two generated **shortlist-only** previews:

```cmd
start "" "evaluation_runs\row_continuity_camera1\row_candidates_raw.png"
start "" "evaluation_runs\row_continuity_camera1\row_candidates_ground.png"
```

And examine the underlying joined strokes:

```cmd
start "" "evaluation_runs\row_continuity_camera1\joined_raw.png"
start "" "evaluation_runs\row_continuity_camera1\joined_ground.png"
```

The output `row_comparison.json` records *all unverified candidate
polygons*, observed line-fragment support, artifact decisions, row-neighbor
evidence, and experiment provenance. It refuses to overwrite existing
output directories; use a new directory name for reruns.

If Phase 1 results are not available, omit `--hypotheses`; geometry-only
comparison is still meaningful. For Camera 2 or any other authorized
**fixed-camera** video, first run Phase 2 on that source and reuse its
matching SHA-256 report. Never combine evidence from different videos.

## What to evaluate (manual checks required)

Compare the source video with the **raw joined-line** and **ground-joined**
previews, looking specifically for:

1. True stall separator lines recovered after joining fragments.
2. Previously shallow or broken candidate polygons that now span actual
   visible stall depth.
3. Joined lines that incorrectly bridge gaps between vehicles or different
   painted structures.
4. Empty visible stalls still missing, and lanes/curbs/vehicle windows
   mistakenly suggested as stalls.
5. True dividers rejected by the ground-contrast filter.

Record manually verified true/missed/false candidate cases from a
representative set of frames, including views held out from algorithm
tuning. **Do not use a cleaner image or a higher shortlist count as an
accuracy claim.** Even a line pair and a row neighbor can describe
painted roadway markings rather than a legal bay.

Next studies should investigate painted **stall end/entrance junctions**
and perspective-consistent row spacing based on independent labelled
evidence. Until then the only authoritative monitored-space maps are the
approved, calibrated four-corner polygons with stable IDs.

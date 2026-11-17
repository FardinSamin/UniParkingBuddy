# Phase 3 — Geometry quality review (experimental, read-only)

This stage **does not automatically certify parking spaces**. The October
2026 sample screenshot showed many cyan Phase 2 shapes drawn over vehicle
roofs/windows and scene structures rather than painted stalls. Phase 3
prioritizes plausible review cases and demotes some obvious artifacts using
rules that do not depend on a specific video's hardcoded coordinates.

The submitted SRS, SDD, verified camera JSON configurations, FastAPI,
PostgreSQL, React, and two-state occupancy domain remain unchanged.

## What Phase 3 checks

- **Shared stall dividers:** two candidate quadrilaterals sharing a similar
  painted separator, with comparable area and apparent depth, can support a
  parking-row hypothesis. They might still be lane markings or car edges.
- **Independent vehicle-position corroboration:** an anonymous Phase 1
  vehicle anchor lies within a Phase 2 polygon. This is tentative evidence,
  not proof of legally parked vehicles or correct stall boundaries.
- **Car roof/window artifacts:** a tiny candidate polygon almost completely
  inside a repeatedly observed vehicle bounding box is flagged as a
  likely false shape rather than prioritized as a potential full-sized stall.
  This cannot determine all false proposals and can wrongly demote genuine
  tiny or severely foreshortened spaces.
- **Preserve uncertainty:** isolated or otherwise weak candidates remain in
  the full JSON for review even when omitted from the shortlist preview.

Candidate review tiers:

| Tier | Meaning |
| --- | --- |
| `multiple_cues` | Shared painted divider and recurring vehicle anchor |
| `row_evidence` | Adjacent row-shaped candidate with shared divider |
| `vehicle_evidence` | Recurring ground-anchor support without verified row neighbor |
| `weak_evidence` | Isolated line pair without corroboration; still possible stall |
| `likely_artifact` | Small candidate contained inside a recurring vehicle box |

All tiers have `review_state: unverified`. None is a probability or
equivalent to an occupied/available application state. The exploratory
geometry/size factors in the implementation are **not SRS commitments**.

## Try it on your Windows PC (CMD)

With Phase 1 and Phase 2 results already available, stop any OpenCV
video/demo instance and run:

```cmd
cd /d C:\Users\Fardin\UniParkingBuddy
git pull --ff-only
.venv\Scripts\python.exe -m backend.review_stall_candidates --video footage/stockvidsample2.mp4 --geometry evaluation_runs/geometry_camera1/stall_candidates.json --hypotheses evaluation_runs/discovery_camera1/hypotheses.json --output evaluation_runs/review_camera1
start "" "evaluation_runs\review_camera1\review_preview.png"
```

For Camera 2, first generate its Phase 1 and Phase 2 reports or run the
review in **geometry-only mode** (omit `--hypotheses`). For any newly
authorized fixed-camera video, use its own Phase 1 and Phase 2 reports
and a new output folder. The tool checks the **original video's SHA-256**
against each supplied report; mixing sources is rejected.

### What to expect

`review_preview.png` shows a **human review shortlist**, not all possible
parking stalls. Green outlines have multiple independent evidence cues.
Amber outlines have row evidence or vehicle anchor evidence, but not both.
Small red crosses flag some likely car-surface artifacts. Weak isolated
candidates are hidden from this preview but remain in `review.json`.

Review these candidate groups against **painted, physically valid stalls**.
In particular, identify false adjacent road-lane stripes, real empty bays
missing from the shortlist, and true marked stalls wrongly demoted. Counts
and review tiers should be compared to manually verified geometry before
deciding whether heuristics improve actual precision or recall.

No one has yet measured the full-stall precision or recall for this
prototype on these videos. **A cleaner preview is not a validated result.**

### Safety, privacy, and reproducibility

- `review.json` is an audit-friendly complete record with original Phase 2
  candidate IDs, tier, evidence reasons, neighbor IDs and retained hypotheses.
- New outputs live inside the Git-ignored `evaluation_runs/` folder.
  Each run refuses to overwrite an existing directory.
- The generated preview can contain visible people/vehicles; don't publish
  it without authorization and privacy review.
- Candidate quadrilaterals are never added to `configs/` or PostgreSQL.
  Only human-reviewed, approved space geometry may later be promoted via
  the separate stable-ID configuration workflow.
- This stage is intended for **fixed camera positions**. Moving cameras,
  lighting shifts and severe occlusion remain unsolved limitations.

## What comes after reviewing these results

Record human judgments on false positives and missing true stalls, then
improve **painted junction and row-entrance evidence** and **ground-plane
perspective consistency**. Once verified on multiple **unseen** fixed-view
lots, add a separate explicit review/approval workflow. Next, compare
occupancy association algorithms against those approved polygons and
measure independent SRS AT-01–AT-08 acceptance evidence.

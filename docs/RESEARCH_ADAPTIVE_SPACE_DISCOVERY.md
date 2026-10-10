# Research decision: adaptive parking-space discovery and occupancy

**Status:** Agreed exploratory architecture direction (October 10, 2026). Research/implementation plan, **not** a change to the submitted SOW, WBS, SRS, or SDD; not a claim that automatic discovery is already implemented or validated.

## The problem seen in the first Windows demonstration

The existing prototype successfully runs YOLO/OpenCV on two prerecorded videos, but its saved maps include only **7 configured stalls for camera_1** and **4 for camera_2**. The OpenCV UI reported many detections as `OUTSIDE SPACE`, even though vehicles were visibly parked in other real stalls. Also, `backend/space_matching.py` tests only the *center* of a vehicle's axis-aligned detection box against configured polygons, which can be unreliable for oblique perspectives.

**Important distinction:** An unassigned detection is outside **the configured set**, not necessarily outside the parking lot. PR #29 corrected the display label and added a safe manual calibration editor. This does not fix discovery or space matching.

## Design direction agreed with the project lead

Move toward a **hybrid, fixed-camera, transferable video pipeline**:

1. **Automatic candidate stall discovery as an offline calibration stage**, based on multiple frames, parking-marking geometry, recurring anonymous vehicle positions, and scene perspective.
2. **Uncertainty-aware candidate review**: present supported polygons and confidence/evidence; use manual correction only for missed/uncertain areas. Never silently create confirmed stalls from a guess.
3. **Stable approved parking-space map**: publish verified four-corner polygons/IDs via the existing validated JSON and approved database configuration path. Only approved configured spaces become part of current occupancy totals.
4. **Vehicle-to-space spatial association**: use overlap or vehicle ground-contact estimates and a global one-to-one matching decision, not only a detection box center. One detected vehicle must not fill multiple spaces.
5. **Temporal occupancy evidence**: stabilize **space-level** AVAILABLE/OCCUPIED results over several observations, handle passing vehicles and occlusion, and preserve error/unavailable states independently of the two-state occupancy domain.
6. **Measured validation on unseen fixed-camera views**: compare stall discovery and occupancy against independent human verification; preserve the existing SRS acceptance cases and avoid invented numerical pass thresholds.

This is **not** a promise that *every arbitrary video* can yield a complete parking map. A fixed, calibrated view and enough visible/repeated evidence are necessary. A completely obscured bay, camera movement, one brief clip, or severely missing markings may yield uncertain/unobserved candidates. Under uncertainty, the system must not report an unverified stall as available.

### Approved scope versus exploration

The authoritative corrected SRS FR-02 requires monitored lots and configured regions and FR-04 requires Occupied/Available classification for those configured spaces. Existing manual mapping, FastAPI, PostgreSQL, React, history and acceptance obligations remain intact. An automatic calibration module would **generate suggestions for reviewed configuration**, rather than replace the approved configured-region contract or silently enlarge monitored totals. Any material change to course deliverables/performance promises would use the SRS change-control process.

## Directly relevant research (verified 2026-10-10)

1. **Ratko Grbić and Brando Koch (2023), _Automatic vision-based parking slot detection and occupancy classification_, Expert Systems with Applications 225, 120147.**
   - Article: https://doi.org/10.1016/j.eswa.2023.120147
   - Open preprint: https://arxiv.org/abs/2308.08192
   - Author's explanatory account: https://brandokoch.com/projects/parking-slot-detection/
   - **Reported approach:** vehicle detections across images; centers mapped by a homography into bird's-eye view; DBSCAN clustering; projection back; cluster-spread/outlier reasoning to reject passing/illegally parked vehicle positions; subsequent cropped-slot ResNet34 classification.
   - **Reusable rule:** repeated detections near consistent physical locations provide parking-space candidates; an isolated detection does not. Sampling across genuinely different times matters; a single stationary car throughout one short clip does not prove the presence of a legal marked stall. Camera motion breaks accumulated geometry. The author's write-up notes that its evaluation still needed an externally supplied number of slots, so it is not a guaranteed fully parameter-free detector.
   - **Fit:** very high for fixed surveillance video, including our two camera angles. The authors' published accuracy is **not** UniParkingBuddy accuracy.

2. **_Video-Based Parking Occupancy Detection for Smart Control System_ (2020), Applied Sciences 10(3), 1079.**
   - https://doi.org/10.3390/app10031079
   - **Reported approach:** recognizes center-point matching errors due to oblique surveillance views; compares YOLO boxes and parking-grid intersection/IoU/overlap ratios and applies temporal voting after vehicle stopping evidence.
   - **Reusable rule:** check the part of a car detection that actually intersects a known stall and combine multiple observations. Compare at least polygon-normalized overlap and intersection-over-union; don't transplant the paper's thresholds without independent tuning.

3. **Qian Li, Chunyu Lin and Yao Zhao (2018), _Geometric Features-Based Parking Slot Detection_, Sensors 18(9), 2821.**
   - https://doi.org/10.3390/s18092821
   - **Reported approach:** line segment detection and clustering, separating-line pairs, then parking-slot entrance geometry in a bird's-eye view.
   - **Reusable rule:** multiple consistent line segments, corner/junction patterns and neighboring-stall spacing can support candidate stall boundaries, *even where current vehicles do not expose the entire marking*.
   - **Transfer caveat:** developed for BEV parking-slot markings; overhead/vehicle-surround-view methods may need substantial adaptation for elevated oblique surveillance images.

4. **Jae Kyu Suhr and Ho Gi Jung (2013), _Full-automatic recognition of various parking slot markings using a hierarchical tree structure_, Optical Engineering 52(3), 037203.**
   - https://doi.org/10.1117/1.OE.52.3.037203
   - **Reported approach:** generate permissive candidates from corners/junctions/slot types, then prune incompatible proposals by structural constraints.
   - **Reusable rule:** **candidate generation followed by geometric rejection** is safer than committing a detected line as a real stall. Maintain row orientation, consistent boundary spacing, non-overlap, plausible width and stall entrance.
   - **Transfer caveat:** slot-marking geometry often comes from vehicle-mounted camera imagery; validate adaptation before use.

5. **Jae Kyu Suhr and Ho Gi Jung (2016), _Automatic Parking Space Detection and Tracking for Underground and Indoor Environments_.**
   - https://sejong.elsevierpure.com/en/publications/automatic-parking-space-detection-and-tracking-for-underground-an/
   - **Reported approach:** complement parking-line pairs with free-space information from parked vehicles and pillars/obstacles.
   - **Reusable rule:** combine painted-marking cues and neighboring scene context. Never infer a valid stall from an empty rectangle in a drive aisle solely because it fits a vehicle.
   - **Transfer caveat:** originating vehicle-sensor setting includes information not available to our single fixed camera.

6. **_Robust Parking Block Segmentation from a Surveillance Camera Perspective_ (2020), Applied Sciences 10(15), 5364.**
   - https://doi.org/10.3390/app10155364
   - **Reported approach:** detect parking blocks in a satellite view and project them into a surveillance camera using a homography.
   - **Reusable rule:** a verified ground-plane projection can assist extreme perspective differences; external overhead reference imagery is a possible optional calibration aid, **not** a requirement or permission to retrieve private site imagery.

7. **Paulo Lisboa de Almeida et al. (2026), _MetaPKLot – new challenges and protocols for vision-based parking lot management_, Neural Computing and Applications, published 29 August 2026.**
   - https://doi.org/10.1007/s00521-026-12398-0
   - Dataset: https://github.com/DSBD-Research/MetaPKLot-Dataset
   - **Reported contribution:** harmonized PKLot, CNRPark-EXT and PLds data, explicit *parking spot extraction* benchmark, human-annotated polygons, occupancy and segmentation masks; evaluates generalization to **held-out parking environments**. Recommends geometrically faithful polygons where possible, rotated rectangles otherwise, and AP across IoU thresholds for stall discovery.
   - **Reusable rule:** assess both **discovered stall geometry** (precision/recall and IoU/AP) and **space occupancy** separately, on camera/lot views not used for parameter fitting. Avoid treating tests against the same two demonstration videos as evidence that the system generalizes to any video.
   - **Scope/privacy caveat:** the dataset also offers vehicle-identity/dwell information, but **we must not implement or persist specific-vehicle tracking** under SRS SR-03.

8. **MetaPKLot GraphSpot research baseline (2026; same paper).**
   - https://doi.org/10.1007/s00521-026-12398-0
   - **Reported approach:** car instance masks accumulated across frames into candidate-location heatmaps; one-to-one association using a linear-sum assignment; temporal consistency/coverage and a graph neural network used to prune false parking-space candidates.
   - **Reusable rule:** enforce one detection per stall association; use **independent repeated observations** and spatial neighborhood relationships to reject lanes/driveways and unreliable locations.
   - **Scope and compute:** GraphSpot's Mask R-CNN/ConvNeXt/GNN training is substantially more complex than our present project; start with an interpretable clustering+geometry prototype and use GraphSpot as a research comparison, **not** a dependency.

9. **_Comparative Evaluation of Deep Learning Object Detectors for Real-Time Parking Occupancy Detection Under Variable Lighting Conditions_ (2026), Sensors 26(17), 5329.**
   - https://www.mdpi.com/1424-8220/26/17/5329
   - **Reported rule:** for fixed oblique cameras, the vehicle detection rectangle can extend far beyond the **ground-plane** stall polygon; measuring car-box/parking-polygon intersection divided by **stall area** is an operationally meaningful alternative to box IoU. The article also describes best-scoring association and center fallback.
   - **Reusable rule:** test an intersection-over-stall-area score and ground-contact estimates as separate alternatives rather than assume ordinary box IoU is always best. Visual occlusion is still a limitation.

10. **_Vision-based Parking-slot Detection: A DCNN-based Approach and A Large-scale Benchmark Dataset_ (2018), IEEE Transactions on Image Processing; DeepPS / PS2.0 dataset.**
    - https://cslinzhang.github.io/deepps/
    - **Reported approach:** deep learning of parking-slot marking features across different parking-slot orientations in surround-view data.
    - **Reusable rule:** if classical line detection performs poorly, benchmark a pretrained line/junction detector before building a custom one; its surround-view training distribution differs from our fixed surveillance perspective.

11. **CNRPark+EXT dataset and accompanying decentralized parking occupancy work (2017).**
    - https://cnrpark.it/
    - https://doi.org/10.1016/j.eswa.2016.10.055
    - **Reported dataset:** many different fixed viewpoints, lighting, weather, occlusion and labeled vacant/occupied stall images.
    - **Reusable rule:** test robustness across camera views and weather; use full images plus appropriate stall annotations for extraction and occupancy studies. Review the source terms of any image, annotation or trained model before adding files to our public repository.

## Candidate implementation rules (our proposed synthesis, not claimed verbatim paper requirements)

**R1 — Scene suitability.** Accept a declared fixed-view test video; detect large camera movement/zoom/view change using static background landmarks. If the geometry changes, **invalidate the old proposed map** and require recalibration or review. Never silently reuse stale coordinates.

**R2 — Spaced temporal sampling.** Sample observations across as broad an authorized period as practicable. Correlated adjacent frames are not independent evidence of different vehicles or true parking stalls. Give each observation at most one contribution per candidate; document sample spacing.

**R3 — Candidate generation, two paths.**
- From markings: detect line segments/corners; group by approximately consistent perspective and stall geometry; propose actual marked bays.
- From recurring detections: gather **anonymous frame-local car geometry**, normalize perspective if supported, cluster recurring spatial positions with density-based methods (e.g. DBSCAN).
- Union and compare the candidates; a corroborating line+vehicle hypothesis increases confidence; candidates based on only one cue require stronger validation.

**R4 — Guard against passing and illegal parking.** Penalize candidate locations with broad spatial spread, crossing motion/detection paths or lane-like geometry. Treat a single persistent vehicle in a short recording cautiously: it is insufficient proof of a legitimate *marked stall*. Keep candidates as suggestions until independently verified.

**R5 — Geometric consistency.** Resolve plausible rows, orientation and neighboring-stall widths in the ground plane rather than assume equal image-pixel spacing under perspective. Prevent positive-area stall overlap, invalid quadrilaterals, and candidates obstructing obvious driving lanes. Do not generate unseen stalls solely by extrapolating a row.

**R6 — Human-review gate.** Candidate data may include `geometry`, `support`, `evidence_sources`, `review_state` and a transient `confidence`; these are **calibration metadata**, not new occupancy states or new public DB tables. Promote only reviewed stalls to existing validated configuration. Preserve stable IDs and archive old configuration/hashes.

**R7 — Vehicle-to-stall association.** Compare alternatives on manually verified cases:
- detection/polygon intersection divided by polygon area (coverage score);
- IoU;
- vehicle **ground-contact** location or mask footprint, where geometry/model supports it;
- center-point fallback only.
Avoid one vehicle occupying multiple stalls; resolve competing matches globally rather than by polygon order. Do not invent a universal confidence or overlap threshold.

**R8 — Space-level temporal evidence.** Use several inference observations, hysteresis or majority voting to reduce one-frame false occupancy from passing cars; sample movement/obstruction at the space level without persistent car IDs, license plates, faces, individual journey paths or dwell-time tracking. Tune any trial values on validation evidence rather than claiming SRS thresholds. Continue to represent verified occupancy as only AVAILABLE/OCCUPIED; **loading/unavailable** is a data-freshness/error status, not a third occupancy state.

**R9 — Failure and uncertainty.** If there is too little reliable evidence, leave a candidate **unapproved** and outside displayed monitored totals; if approved-space data become unavailable, display an error/unavailable state rather than assuming AVAILABLE. Do not persist raw video to PostgreSQL.

**R10 — Compare against explicit baselines.** Evaluate:
1. old manual-ROI + box-center method;
2. independently reviewed manual ROI + better association;
3. automatically proposed and human-reviewed ROI + same association;
4. optional direct cropped-stall classifier for hard occlusion cases.
Keep accuracy from actual independent human labels only, not pseudo-labels or visually pleasing displays.

## Validation and experiment plan

1. **Baseline freeze**: record current `main` commit, existing footage hashes, model, configurations and preflight result. Record screenshot issue as a reproducible defect.
2. **Small proof of concept**: run a **read-only offline** discovery experiment over both committed videos, export candidate polygons and confidence/evidence to `evaluation_runs/` (ignored by Git). No automatic update of `configs/`, PostgreSQL, public current counts or original documents.
3. **Manual audit**: annotate true visible stall boundaries and any unobservable/invisible bays. Check per-stall overlap, false candidate count and missed stalls.
4. **Unseen-scene evaluation**: run the same frozen discovery algorithm on appropriately licensed PKLot / CNRPark-EXT / MetaPKLot held-out camera viewpoints, or newly authorized separate test footage; do **not** fit thresholds on the test views. Report geometry and number of candidates, not just an occupancy percentage.
5. **Matching comparison**: with **verified** space polygons, test box-center, coverage, IoU and ground-contact matching on angled and partially occluded vehicles, passing traffic and crowded rows. Record FP/FN and ambiguous assignments.
6. **Controlled integration**: only after improved matching is independently validated, connect approved configuration to existing CV -> FastAPI -> PostgreSQL -> React path, re-run CI, SRS AT-01 through AT-08, measure actual updates and document real limitations.

## Engineering priorities

**Now:** keep the known-good current system; separate offline discovery from online occupancy. Start with repeat-detection clustering + perspective-aware geometry + line evidence; produce inspectable candidate overlays and machine-readable suggested polygons; require review.

**Next:** robust matching and temporal smoothing, with synthetic unit tests and independent observed video cases.

**Later, if evidence warrants:** evaluate segmentation masks and GraphSpot-inspired spatial graph reasoning, learned mark/junction detectors, optional homography estimation and automatic recalibration. These are **research alternatives**, not obligatory semester features.

## Risks and ethical constraints

- Insufficient varied observations cannot reveal spaces permanently occluded or never occupied. Mark as uncertain; don't fabricate open spaces.
- A stationary car in a driving lane or a briefly stopped vehicle must not establish a legitimate space by itself.
- A per-frame box might cover multiple far-field polygons; never indiscriminately mark all such spaces occupied.
- Camera changes break polygon coordinates: use a versioned calibration step.
- Published benchmark accuracy/parameters do **not** transfer automatically to our two sample videos.
- External datasets/code/model weights require license and privacy review. Ultralytics' official licensing describes AGPL-3.0 versus Enterprise: https://www.ultralytics.com/license ; keep the project compliant with the approved software distribution plan.
- Preserve approved site/camera authorization and SRS SR-01 through SR-09: no facial recognition, LPR, person/vehicle identification or tracking; only anonymous configured-space occupancy and timestamps in the application database.

**Decision:** We retain the manual editor as a correction/review tool while researching and incrementally implementing automatic candidate discovery. No exact detection, timing or accuracy percentage is promised before evidence-based testing.

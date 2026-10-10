# UniParkingBuddy acceptance test execution record

**Baseline:** Submitted corrected SRS (September 7, 2026), approved SOW
and WBS/Gantt, SDD Part 1 and Part 2, and submitted test cases.
This file is a **test-execution worksheet**, not a revision of those baselines.

**Project:** UniParkingBuddy — CSC 4900, Fall 2026  
**Test run ID:** _to be recorded_  
**Test date / time zone:** _to be recorded_  
**Git commit:** _to be recorded_  
**Reviewers / witnesses:** _to be recorded_  
**Backend / database / frontend / browser versions:** _to be recorded_  
**Authorized input location and source:** _to be recorded_  
**Applicable campus test permission:** _to be confirmed and recorded_

## Acceptance cases (copied meaning from corrected SRS)

Do not mark these as fully passed just because a related component CI
test has passed. Record evidence and actual outcomes from a controlled
end-to-end test with the intended prototype/demo setup.

| Case | Official acceptance subject | Expected result / measurement | Relevant existing automation | Actual result | Evidence / defects |
| --- | --- | --- | --- | --- | --- |
| AT-01 | End-to-end current availability | Authorized input yields configured-space status and lot/space totals in integrated web UI | Real YOLO→DB→API CI; separate Chromium→React CI | **Not executed as single live system** | _enter link/time/observations_ |
| AT-02 | Occupancy change propagation | Controlled Occupied/Available change reaches latest backend state and web view; time is measured and recorded | Synthetic FastAPI→Chromium polling test records actual elapsed milliseconds in CI | **Live-run time not yet measured** | _enter timestamp/state/display evidence_ |
| AT-03 | Counts / fullness consistency | Available/Occupied/Total matches manually checked current states; FULL indicator agrees | API consistency tests + synthetic FULL/UNAVAILABLE browser tests | **Field observations outstanding** | _enter counts and comparison_ |
| AT-04 | Historical trend pipeline | Stored timestamped samples match the retrieved displayed descriptive trends; no prediction claim | PostgreSQL history/trend checks and synthetic browser view | **Integrated demo check outstanding** | _enter DB/API/UI comparison_ |
| AT-05 | Controlled classification cases | Each selected manually verified configured-space state matches model output; mismatches recorded/resolved or approved disposition | `backend.evaluate_accuracy` prepares annotated frames and model predictions | **Human labels outstanding** | _enter case IDs/observations/defect IDs_ |
| AT-06 | Accuracy measurement and limitations | Compute accuracy from manually verified comparisons; log lighting/occlusion conditions and limitations; no invented threshold | `backend.evaluate_accuracy report` refuses incomplete human labels | **No real accuracy figure yet** | _enter `accuracy_report.json` location and conditions_ |
| AT-07 | Failure handling | UI shows loading/unavailable state, invalid update rejected, last valid stored history/current not overwritten | CI simulates failed writes, invalid updates, missing API and browser recovery | **Workstation failure test outstanding** | _enter actual failure/recovery evidence_ |
| AT-08 | Privacy, accessibility and scope | No facial/LPR/person tracking, bookings, payment, enforcement; verify keyboard navigation and status labels; relevant WCAG review | Source/data scope checks and partial Chromium keyboard/viewport checks | **Full accessibility/scope inspection outstanding** | _enter checklist/results/defects_ |

These are the eight SRS acceptance topics, **not eight invented test
thresholds**. Use `docs/VALIDATION.md` and
`docs/ACCURACY_EVALUATION.md` for detailed execution instructions.

## Measurement evidence: NFR-P01

Human reviewer and model must be independent. Label every sampled
configured-space/frame pair `AVAILABLE`, `OCCUPIED`, or
`UNVERIFIABLE` for ambiguous visual cases. The last is an
**evaluation exclusion only**, not an application occupancy state.

- Model/video/configuration checksums and Git commit: _enter_
- Reviewer, labeling approach and any disagreements: _enter_
- Lighting, occlusion, glare, replay limitations: _enter_
- Evaluated verified space-frame results: _enter_
- Excluded unverifiable observations: _enter_
- Correct verified results: _enter_
- **Measured accuracy = correct ÷ all human-verifiable results × 100:** _do not fill until calculated_
- False positives / false negatives and specific defect IDs: _enter_
- Report artifact path and review sign-off: _enter_

A unit-test arithmetic fixture is never evidence of real-world
classification accuracy.

## Measurement evidence: NFR-P02

**Acceptance clock endpoints:**
1. Start: newly processed valid configured-space occupancy change is
   available at the backend (record the exact event used, clock and method).
2. Stop: the corresponding new Occupied/Available state is visibly
   rendered in the actual web interface.
3. Record each interval, environment/network/browser, test state/space,
   source video or authorized live camera, and clock synchronization /
   observer method used. Include failures and trial variability.

Do **not** confuse raw video acquisition time, YOLO inference duration,
a nominal frontend polling interval, backend/API-only latency, or a
simulated source-to-browser measurement with the full required
end-to-end observed value. No numerical performance threshold is
specified by the approved baseline.

**Existing automated supporting evidence:**

GitHub Actions job `Real Chromium + Vite + FastAPI UI integration`
uploads the file `controlled-react-update-timing/browser_update_timing.json`.
The actual artifact filename is `browser_update_timing.json`, stored
inside an Actions artifact named `controlled-react-update-timing`.

That automated measurement starts **before a controlled synthetic
in-memory backend status mutation** and stops when the matching state
is observed in real Chromium. It includes React polling, Vite routing
and FastAPI delivery; it **excludes** real CV, camera acquisition and
PostgreSQL persistence. It supplies **measured software UI propagation
evidence only**, not the full NFR-P02 result. Results vary by CI machine,
so retain the JSON along with the Actions run URL and environment data.

| Run | Camera/space | Source/change | Processed timestamp / clock | UI timestamp / clock | Observed elapsed ms | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| _run 1_ | _enter_ | _enter_ | _enter_ | _enter_ | _unmeasured_ | _enter_ |
| _run 2_ | _enter_ | _enter_ | _enter_ | _enter_ | _unmeasured_ | _enter_ |
| _run 3_ | _enter_ | _enter_ | _enter_ | _enter_ | _unmeasured_ | _enter_ |

## Scope, privacy and accessibility review (AT-08)

Record reviewer, date, browser/OS, test method, relevant WCAG 2.2
A/AA criterion where applicable, observed result, and any issue ID.

- [ ] Keyboard-only access to all primary navigation (lots, lot
      details, historical trends, space selection, back navigation)
- [ ] Visible keyboard focus and readable labels
- [ ] Available/Occupied/FULL/UNAVAILABLE conveyed without color alone
- [ ] Desktop and mobile/narrow-browser layout
- [ ] Relevant WCAG 2.2 A and AA criteria examined and findings recorded;
      **do not claim formal conformance** without all applicable checks
- [ ] PostgreSQL contains only approved lot/space status, region and
      timestamp information; no raw video storage by default
- [ ] No face recognition, license-plate recognition, personal or specific
      vehicle tracking, booking/payment, enforcement actions
- [ ] Authorized test setup; minimize needless identifiable video capture
- [ ] No secrets or privileged write functionality exposed to public browser

## Defect and disposition log

| ID / GitHub issue | Related acceptance case | Observation and reproduction | Severity | Fix PR / review | Retest outcome |
| --- | --- | --- | --- | --- | --- |
| _enter_ | _enter_ | _enter_ | _enter_ | _enter_ | _pending_ |

**Final acceptance decision:** _PENDING REAL OBSERVATIONS AND TEAM REVIEW_  
**Reviewer sign-off:** _not recorded_

Never replace a blank or pending field with a guessed pass/fail,
accuracy percentage, latency value, physical-camera result, or
reviewer approval.

# Proposal Alignment and Related AR Research Review

**Review date:** 2026-11-24<br>
**Project:** Adaptive Headlight Glare Suppression System Using Computer Vision and Eye Tracking<br>
**Implementation reviewed:** GlareTracker v1.3.0, source baseline `e1bd51d`, plus the existing documentation work<br>
**Status:** Assessment and research reference. No implementation, hardware commitment,
or development-plan change is made by this review.

## 1. Main findings

The LCD prototype is supported by the full proposal. Section 3.2, PDF page 18,
describes a flap grid followed by a transparent LCD upgrade. Section 3.3.4, PDF
page 21, explicitly gives the LCD its own second integration stage. Figure 1.0 on
page 19 also names a transparent LCD matrix as the output. The strongest explanation
is therefore that the team is implementing the proposal's intended later output
stage, using available commercial hardware.

The proposal also names physical servo flaps in its specific objectives, expected
outcomes and evaluation method. Reaching the LCD stage does not automatically prove
that the promised first-stage flap experiment was performed. Whether that experiment
can be omitted is an assessment decision; no institutional change policy or marking
rubric was supplied. No guarantee against mark deductions can be inferred.

The more substantial implementation differences are the laptop execution platform,
the specific NIR imaging hardware, optional research-video retention, and the
unverified automatic-transparency failure claim. These deserve explicit evidence
and wording rather than a last-minute rewrite of the working application.

Related work exists in automotive glare control and optical see-through AR. It
supports the technical basis of selective LCD attenuation and eye-dependent spatial
alignment. It also limits claims that the overall idea or three-camera architecture
is unprecedented. The defensible contribution is the particular low-cost system,
its implementation, calibration, experiments and measured limitations.

Continue the existing camera-to-LCD and ToF integration sequence. Any additional
flap, microcontroller benchmark or NIR imaging work described below is a conditional
assessment contingency, not an addition to the active development queue.

## 2. Source and interpretation rules

The complete supplied proposal has 30 PDF pages. Page references here count the cover
as page 1; some pages have no printed page number.

Original file: `C:/Users/vosha/Desktop/Research/Proposal/Group01_MM_Research Proposal.pdf`<br>
SHA-256: `e58c9a8da9e9dc2a56d744ab848d2c040ec23b8ae976baac2ebcac036287138f`

The filename says Group01 while the cover says Group 36. Confirm which submitted
version is authoritative before using it in an assessment pack. This administrative
check does not affect the technical interpretation of the supplied document.

The survey is **partially completed according to the user**; no survey dataset was
audited here. Software capabilities were checked against the local source and the
existing status records. The last recorded regression result is 138 passing tests
on 2026-11-18; no new application test result is asserted by this review.

## 3. Current system understanding

The intended laboratory rig places an LCD panel between a driver-side eye target and
road-side light sources. Two rigidly mounted road cameras face the lights. A separate
driver webcam faces the driver; a purchased VL53L0X range module is intended to be
mounted beside it. The cameras do not need to look at the LCD surface.

The current source detects independent bright candidates, associates the two road
views, estimates stereo positions when its profile is compatible, and maintains
stable light IDs. The driver pipeline retains two iris-centre estimates. The tracker
calculates one eye-to-light crossing for every valid combination and presents those
results in the 3D scene, front view, telemetry and secondary-display output.

Road lens/stereo calibration has a saved passing fit candidate and a plausible
baseline check. The live coordinate conversion still uses simplified mounting
assumptions. Installed camera-to-LCD transforms exist as backend mathematics but
are not yet applied throughout live tracking. Driver distance currently comes from
manual/reference or IPD-based estimation. ToF acquisition and fusion are planned.

The physical display window and Run/Standby/Stop lifecycle have been demonstrated.
Accurate physical spot alignment, actual attenuation and external response time
still require measurements on the assembled rig. Rendering a dark spot on a monitor
establishes output functionality, not successful glare attenuation at an eye.

Source entry points:

- [Driver observations](../../glare_tracker/camera.py),
  [road detection](../../glare_tracker/headlight_detector.py), and
  [temporal light tracking](../../glare_tracker/light_sources.py).
- [Intersection mathematics](../../glare_tracker/geometry.py),
  [installed transforms](../../glare_tracker/extrinsics.py), and
  [tracking coordination](../../glare_tracker/tracking.py).
- [LCD renderer](../../glare_tracker/lcd_blocker.py),
  [recording](../../glare_tracker/diagnostics.py), and
  [application orchestration](../../glare_tracker/window.py).
- [Current technical brief](PROGRESS_MEETING_TECHNICAL_BRIEF.md) and
  [unchanged integration plan](../plans/CAMERA_LCD_AND_TOF_INTEGRATION_PLAN.md).

## 4. Objective and commitment traceability

| Proposal commitment and location | Present evidence | Remaining obligation or interpretation |
|---|---|---|
| Main objective: localized, automated optical attenuation; Section 1.5.1, p7 | Vision, geometric mapping, simulation views and LCD output implemented | Demonstrate measured attenuation and alignment on the final rig |
| Local driver survey; Sections 1.5.2 and 1.7, p7-8; 18-question instrument expected | User reports partial completion | Complete and preserve the actual instrument, responses and analysis; report perceived effects separately from objectively measured driving performance |
| Detect and classify headlights/high-intensity sources; p7-8 | Multi-source bright-region detection, stereo correspondence and temporal IDs | Define and test the classes. A confidence score is not semantic vehicle/headlight classification; candidate count is not vehicle count |
| NIR-assisted 3D pupils and drowsiness; RQ3, p8 | RGB iris estimates and experimental drowsiness indicators; ToF integration planned | Evaluate the hybrid approach, but disclose that p20 specifies an NIR camera and LED ring |
| 3D-to-2D mapping, multiple sources and inclined windshield; RQ4, p8 | Per-eye/per-light ray-plane intersections and panel bounds | Complete installed calibration and held-out physical error tests; inclination must be represented and tested explicitly |
| Sunlight in RQ4, p8; daytime mitigation listed as future work in Section 1.9, p9 | Headlight-like laboratory sources are the current focus | Acknowledge the internal scope tension; describe sunlight as untested/future unless assessed scope is clarified |
| Digital twin and dynamic multi-source validation; Sections 1.7, 3.1 and 3.3.5, p8, p18, p21-22 | Geometric visualization, manual inputs, motion scenarios and unit-tested geometry | Preserve repeatable scenarios and independent reference results. A visual animation alone does not validate camera imagery, optics or real-world latency |
| Physical flap matrix and MCU evaluation; objective 6, RQ6 and outcomes, p7-9 | No physical flap-grid evaluation or MCU mapping benchmark established | LCD is an intended later stage, but literal flap/MCU deliverables remain a separate assessment question |
| LCD upgrade; Section 3.2, p18; Figure 1.0, p19; Section 3.3.4, p21 | Fullscreen LCD output and physical panel profiles implemented | Strong documentary support for using LCD as the main prototype; compare promised and actual stages honestly |
| MCU spatial processing; Figure 1.0 and Section 3.3.3, p19-20 | Mapping currently runs in Python on the laptop | An MCU ToF reader alone will not establish MCU coordinate-mapping performance |
| All MediaPipe/pupil processing on embedded MCU; Section 3.3.6, p22 | Local laptop processing | The wider embedded-computing promise remains unmet; a standalone EXE is not MCU deployment |
| Research UI in React/TypeScript/TanStack Query; p19, p22-23 | PyQt5/PyQtGraph interface with worker threads and asynchronous recording | Explain the implementation-tool substitution and demonstrate the intended monitoring/responsiveness outcomes; do not rebuild solely to reproduce framework names |
| Millimetre error, latency, transparency retention and MCU efficiency; Section 3.4, p23 | Logging/analysis infrastructure and software checks exist | Collect actual physical error, external latency, area/transmission and MCU measurements; none follows from the UI FPS value |
| Manual baseline, recognition-time comparison and high-speed verification; Sections 3.1, 3.5-3.6, p18, p24 | Controlled procedures exist; completed participant/comparison trials not established | Keep these as outstanding experiments rather than treating the survey or unit tests as substitutes |
| Normally open, automatic 100% transparency on failure; Section 3.3.7, p22 | Software clears/hides output on specified lifecycle/loss events | Cannot claim power-loss transparency, full transmission or automotive fail-safe behaviour without physical evidence |
| Zero retention, including no stored face/video; Sections 3.3.6 and 3.7, p22, p25 | Recording starts only when enabled, but can save camera videos and telemetry | Recording-off operation can support a narrower no-intentional-recording statement. Research recording needs a separately documented consent/retention arrangement before participant capture |
| Controlled laboratory deployment; Section 3.2 and Section 3.7, p18, p25 | Current rig and protocols are laboratory oriented | Remain within that scope; source claims do not establish industrial certification |

## 5. LCD and flap interpretation

The most useful passages for the team's explanation are:

1. **Section 1.2, p5:** physical interfacing with transparent LCD/smart glass is
   already in scope, and manufacturing automotive laminated glass is excluded.
2. **Section 3.2, p18:** the rig is described as using a mechanical flap grid first,
   then upgrading to transparent LCD.
3. **Figure 1.0, p19:** the illustrated mitigation output is a transparent LCD matrix.
4. **Section 3.3.4, p21:** Stage 1 sends serial commands to servo flaps; Stage 2 passes
   calculated coordinates to transparent LCD drivers.

A suitable explanation is:

> The mechanical grid was proposed as an initial demonstrator of the coordinate
> mapping. The same proposal also specifies transparent LCD integration as its second
> stage. We selected an available commercial LCD for that output stage while retaining
> the central eye-to-light mapping method. We separately report which intermediate
> flap and microcontroller experiments were actually completed.

This supports the LCD route without claiming that a higher-resolution output proves
the omitted flap stage. LCD may provide finer spatial addressing and remove servo
movement from the output mechanism, but better measured accuracy, latency and optical
performance remain hypotheses until tested.

## 6. Corrections to earlier informal interpretations

### NIR ranging and NIR imaging

VL53L0X uses a 940 nm emitter and SPAD detection array; describing it as NIR ranging
is correct. [Manufacturer datasheet](https://www.st.com/resource/datasheet/vl53l0x.pdf).
RGB iris detection plus calibrated NIR range is a reasonable interpretation of RQ3's
broad combined-sensor question. It does not reproduce Section 3.3.1's NIR camera and
active IR LED ring, nor illuminate the webcam's eye image. Full-proposal alignment
must therefore distinguish the intended hybrid variant from that specific method.

ToF still needs sensor-to-camera geometry, face-surface-to-eye correction, valid
target/pose limits and timing checks. Its detector array does not supply an iris
image. Whether the RGB camera can still see the eyes in darkness or headlight glare
is a separate test. Likewise, iris landmarks are estimates of eye features, not
automatically validated metric pupil coordinates or gaze direction. Google's
[MediaPipe Iris description](https://research.google/blog/mediapipe-iris-real-time-iris-tracking-depth-estimation/)
supports the distinction between iris localization, metric depth estimation and gaze.

### Inclined windshield and sunlight

A panel-local coordinate system can represent a physically inclined flat panel if
every camera/target pose is measured relative to it. Setting the plane to `Y = 0`
does not prohibit this mathematically. However, the current viewer's vertical plane
and approximate live camera placement do not demonstrate inclined-windshield
accuracy. The planned installed transforms are the relevant next step.

RQ4 mentions sunlight while Section 1.9 places it in future work. This ambiguity is
worth flagging rather than declaring either sentence irrelevant. A simulated
directional-light case can demonstrate geometry; it cannot establish real solar
detection or attenuation.

### Latency and transparency claims

Separate coordinate-kernel time, vision time, communications, rendering and measured
optical response. Sub-millisecond arithmetic is not sub-millisecond camera-to-eye
mitigation. At the current requested road capture rate of 15 FPS, frames are about
66.7 ms apart; that alone prevents treating a fast geometry function as proof of an
always-sub-millisecond full-loop response. Actual exposure, buffering and display
response must be measured.

The commercial LCD is also not the MEMS microshutter/micromirror technology discussed
in the proposal's literature and novelty sections. Its switching speed and failure
behaviour cannot inherit those devices' specifications.

Similarly, an unmasked-area percentage and optical transmittance are different
measurements. More than 90% unmasked area does not mean the reused panel transmits
more than 90% of incident light. No dark-mask command or white screen establishes
100% physical transparency or the power-off state.

### Privacy and participant evidence

The proposal's no-cloud intent is compatible with local laptop processing, but local
processing and zero retention are separate properties. The explicit research-video
switch creates a recording path. Before recording participants, resolve that path
against the promised data handling and participant consent. This review does not
change the application or authorize additional participant recording. Artificial
targets remain useful for coordinate and optical tests without collecting face data.

## 7. Assessment contingencies that preserve the main prototype

These are options to discuss if literal commitments are enforced. They are not
scheduled development work and do not alter the existing integration plan.

| If assessors require | Smallest useful evidence route | Boundary |
|---|---|---|
| Explanation of LCD selection | Cite Sections 3.2/3.3.4 and Figure 1.0; show the same intersection coordinates driving LCD pixels | Technical support already in proposal, but acceptance is the institution's decision |
| Physical flap grid | A small independently addressable 2x2 or 3x3 servo fixture driven by the same coordinate-to-cell data, alongside the main LCD rig | Virtual flaps or LCD squares are not physical servo evidence. One isolated servo is not a grid. Report grid quantization and actuator settling separately |
| Low-cost MCU coordinate mapping | Send known eye/light vectors to the MCU; calculate intersections/bounds/cell indices there; compare with the Python reference and measure time, precision and RAM/flash | A genuine kernel benchmark addresses the mapping part of RQ6, not the separate promise that the entire vision pipeline runs on MCU |
| Entire embedded vision execution | Treat as a separate port/deployment evaluation with an appropriate embedded processor | Do not claim a Nano ToF reader or laptop EXE fulfils it; the proposal itself loosely mixes MCU and Raspberry Pi terminology |
| NIR imaging demonstration | A bounded test of an actual NIR-sensitive camera/illumination arrangement with the intended eye-tracking model | NIR ToF alone is not that image stream. Model compatibility and low-light/glare results must be measured |
| Unchanged physical-prototype deliverable | Keep LCD as main prototype and distinguish any requested intermediate comparison fixture | No need to discard the LCD or replace working Python UI to manufacture similarity with wording |

Prepare three factual clarification points for the supervisor/assessors:

1. Is direct evaluation of the proposal's stated LCD stage acceptable without the
   intermediate servo-grid experiment?
2. Is laptop vision plus measured MCU coordinate mapping acceptable for the
   prototype, given the conflicting embedded descriptions?
3. How should the planned RGB-plus-NIR-range variant and optional research recording
   be documented against the detailed NIR-camera and zero-retention sections?

Keep the response with the approved proposal/version and assessment evidence.
Nothing in this review sends a message, requests an amendment or changes the proposal.

## 8. Related technical research

The closest connection is **optical see-through AR occlusion**, where a spatial
modulator controls which real-world light reaches an eye. Conventional additive AR
overlays do not become real light blockers just by drawing black. Glare suppression
shares the registration and attenuation problem, although this prototype does not
need virtual-image optics or a VR engine. [Factored Occlusion research](https://www.computationalimaging.org/publications/factored-occlusion-ar-display-ieee-vr-2020/).

### R1 Automotive LCD precedent

Bosch's 2020 Virtual Visor combines a transparent LCD and driver-facing camera to
darken selected regions based on facial landmarks/shadows. It is a close industrial
precedent for the LCD-output principle. The described method targets sun glare and
does not establish our stereo multi-headlight implementation or its accuracy.
Use it to justify the component class, not as a performance result for the reused
monitor. [Bosch primary announcement](https://www.bosch-presse.de/pressportal/de/en/safe-eyes-save-lives-how-bosch-engineers-are-innovating-the-95-year-old-sun-visor-204928.html).

### R2 Existing automotive geometry foundation

Ungureanu, Miclea, Korodi and Silea (2020), *A Novel Approach against Sun Glare to
Enhance Driver Safety*, Applied Sciences 10(9), 3032, is already cited by the proposal.
It treats driver/light geometry and windshield shading, with MATLAB validation and
a separate equation-solving MCU discussion. Its discussion leaves a real laboratory
prototype for future work. Its timing report concerns a numerical kernel, not a
complete camera/LCD pipeline; the text also contains a timing-unit inconsistency,
so do not transfer its numbers to our system. [Primary paper](https://www.mdpi.com/2076-3417/10/9/3032).

### R3 Camera controlled LCD glare attenuation

Bian, Liao, Guo, Heng and Zheng (2015), *LCD-based digital eyeglass for modulating
spatial-angular information*, Optics Express 23(9), 11813-11818,
DOI 10.1364/OE.23.011813, uses a scene camera and transmissive LCD patterns, with
headlamp glare among its applications. The author paper describes a camera serving
as an eye in bench evaluation, useful precedent for an artificial-eye experiment.
Their wearable optical geometry and reported results are not performance guarantees
for a large windshield panel. [Author paper](https://www.researchgate.net/publication/275589889_LCD-based_digital_eyeglass_for_modulating_spatial-angular_information),
[author laboratory publication record](https://smartimaging.uconn.edu/publications/).

### R4 Optical see through AR occlusion

Krajancich, Padmanaban and Wetzstein (2020), *Factored Occlusion: Single Spatial Light
Modulator Occlusion-Capable Optical See-Through Augmented Reality Display*,
DOI 10.1109/TVCG.2020.2973443, demonstrates spatially selective real-scene occlusion
with a DMD, also generating virtual content. This is related computational optics,
not a transmissive monitor or a requirement to buy a DMD. [Author project page](https://www.computationalimaging.org/publications/factored-occlusion-ar-display-ieee-vr-2020/).
Use the work for terminology and the distinction between adding imagery and
physically attenuating scene light; our display implementation is different.

### R5 Selective dimming and mask blur

Hu, Zhang, Uchiyama, Isoyama, Sakata and Kiyokawa, *Smart Dimming Sunglasses for
Photophobia Using Spatial Light Modulator*, arXiv version 4 (2023), journal reference
Displays 81 (2024), 102611, combines an HDR scene camera and LC attenuation. It
examines mask blur, camera/display alignment and measured grayscale/transmittance
behaviour. It offers useful evaluation ideas, not evidence that the current panel
has the same optical response. [Author manuscript](https://arxiv.org/html/2304.07013v4).
Inference for our tests: measure attenuation at the artificial eye and determine mask
size from pupil coverage, source extent and error, rather than judging the spot only
on the operator display. This is compatible with the existing physical LCD protocol.

### R6 Per eye registration and repeated calibration

Moser and Swan (2015), *Improved SPAAM Robustness Through Stereo Calibration*, an
IEEE ISMAR poster, compares optical see-through alignment methods and eye/IPD
estimates. Its preliminary experiment uses a single user, so its reported consistency
improvement is not broad population evidence. [Author-hosted paper](https://ed-swan.github.io/publications/papers/2015_Moser-Swan_SPAAM-Stereo-Calibration_IEEE-ISMAR.pdf).
The transferable principle is testing per-eye alignment and depth sensitivity over
repeated setups. SPAAM is not a replacement for our measured-jig camera-pose
calibration and does not imply we need two driver cameras.

### R7 Particularly close thesis lead

Niharika Khare, *Glare Cancellation System for Vehicles and Aircraft*, hosted on
IIT Kanpur faculty infrastructure, describes in its indexed abstract two front
cameras, a third eye-tracking camera and transparent LCD shading. This is particularly
close architectural prior work and should be examined before asserting novelty.
[Primary thesis link](https://home.iitk.ac.in/~venkats/Thesis/Glare%20Cancellation%20System%20for%20Vehicles%20and%20Aircraft.pdf).
The abstract was available through search indexing; direct full-PDF retrieval failed
during this review. Publication year, implementation details and quantitative results
are therefore not verified here. Treat it as a literature lead, not a source of
established benchmark performance.

## 9. Practical advantages from the related work

The following are interpretations for this project, not claims that those papers
implemented our software or proved its accuracy:

1. **Use established terminology.** Describe the output as localized optical
   attenuation or an occlusion mask, and calibration as camera-eye-display spatial
   registration. The apparatus remains a glare-suppression prototype, not a VR headset.
2. **Measure from the eye position.** Use an artificial pupil/eye-view camera to
   inspect whether commanded masks attenuate the actual ray for each eye. This
   complements the already planned external-error measurements.
3. **Keep geometry and optics separate.** A correct centre coordinate does not
   determine sufficient mask size. Include pupil aperture, light-source extent,
   tracking/calibration uncertainty and measured motion delay in the coverage test.
4. **Measure real transmission.** Characterize grayscale versus light transmission
   and unshaded-area loss separately. Reuse the existing LCD protocol rather than
   importing a near-eye display's transmission values.
5. **Keep simulation claims bounded.** Existing vector scenarios can validate geometry
   and demonstrate a virtual grid. Add camera-image realism, road scenarios or a
   human visual model only if those are actually implemented and validated later.

The relevant theory can strengthen the explanation and experimental design without
changing PyQt, adding Unity/Unreal, buying AR optics or redirecting the active build.

## 10. Contribution and examiner wording

Avoid claiming invention of LCD glare blocking, eye-dependent ray-plane mapping or
the general three-camera arrangement. A more defensible candidate contribution is:

> An implementation and laboratory evaluation of a low-cost, multi-source,
> binocular glare-mapping prototype, using calibrated commodity cameras, an existing
> LCD output and a reproducible simulation and measurement workflow.

Add camera-plus-ToF distance fusion to that statement only after it is implemented.
Present it as an evaluated design choice, not an automatically novel combination.
Cost advantage needs a complete bill of materials, distinguishing already-owned
laptop equipment from an embedded deployment cost. Reused hardware does not make
its cost disappear from a fair comparison.

Useful responses to likely questions:

- **Why LCD instead of flaps?** The proposal specifies LCD as the later stage. It
  provides individually addressable regions without servo motion; measured output
  behaviour and any omitted intermediate experiment are reported separately.
- **Is this AR or VR?** It shares spatial registration and real-light attenuation
  techniques with optical see-through AR. It is built for glare suppression and
  does not require virtual content or a headset.
- **What has NIR actually done?** The present webcam supplies iris features. The
  purchased NIR ToF sensor's distance fusion is planned; it is not yet NIR eye imaging.
- **Does the MCU run everything?** Currently the laptop runs vision and mapping.
  Future sensor firmware or a separate mapping benchmark must be identified by the
  functions actually deployed, not described as full MCU execution.
- **Has accuracy been demonstrated?** The geometry is unit-tested and the stereo fit
  has passed software checks. Final installed eye/light-to-panel accuracy remains a
  physical validation task.
- **Are failures transparent?** Specified software events clear spots. Actual panel
  behaviour during HDMI, controller or power failures remains to be measured.

## 11. Evidence pack for the progress meeting

Keep the authoritative proposal and this page-to-implementation matrix together with:

- survey progress, questionnaire, analysis and appropriately handled source data;
- dated camera calibration reports, baseline measurements and rig photographs;
- the current implementation diagram distinguishing laptop and MCU responsibilities;
- software test records with dates and a separate physical-results table;
- repeatable synthetic scenarios and independent reference intersections;
- per-eye, multi-source physical position/attenuation measurements when available;
- stage-by-stage timing and external optical response, with the test hardware stated;
- actual hardware costs and the participant recording/retention arrangement;
- any supervisor clarification on the intermediate flap stage or embedded execution.

The active next work remains the
[Installed Camera-to-LCD and Driver ToF Integration Plan](../plans/CAMERA_LCD_AND_TOF_INTEGRATION_PLAN.md).
This review preserves that plan, the current preparation documents, application code,
saved profiles and hardware state.

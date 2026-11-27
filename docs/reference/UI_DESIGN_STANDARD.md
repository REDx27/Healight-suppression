# GlareTracker UI Design Standard

> Adopted: 2026-11-11
> Last reviewed: 2026-11-27
> Scope: desktop operator interface only; tracking and calibration algorithms remain
> independent of this presentation layer.

## Design direction

The interface follows the visual and interaction model of a technical 3D editor such
as Blender rather than a consumer dashboard. It uses persistent editor regions,
movable splitters, compact tool controls, neutral gray surfaces, and blue selection
accents. Semantic green, amber, and red are reserved for operating state and warnings.

## Principles

1. **Content first.** The 3D scene, camera frames, telemetry, and configuration are
   separate editor regions. Decorative cards must not reduce their usable area.
2. **Consistent rhythm.** Use a compact 2 px grid: 8 px between form rows, 16 px
   inside panels and between sections, with a separate 28 px panel header.
3. **Visual hierarchy.** Region heading, panel heading, field label, value, and hint
   text must be visibly distinct without adding a box behind every label.
4. **Progressive disclosure.** Normal operation shows the calibrated-stereo workflow.
   detailed detector, legacy, and experimental controls remain available through
   explicit advanced switches.
5. **Responsive regions.** Splitters, stretch factors, minimum sizes, wrapping, and
   scroll areas—not fixed pixel allocations—control resizing. Narrow windows reflow
   the configuration region below the main workspace.
6. **Correct control semantics.** Momentary actions use buttons, mutually exclusive
   states use grouped buttons or selectors, and persistent binary settings use toggle
   switches. A toggle remains keyboard accessible because it subclasses `QCheckBox`.
7. **State clarity.** Color is not the only state signal; every camera and session
   state also has readable text. Disabled and unavailable states must remain distinct.
8. **Readable density.** Form fields and commands use a 24 px logical height;
   context icons use 32 px targets with 12 px separation. Qt scales these for high-DPI displays. Use one
   logical-pixel type scale so desktop font DPI does not independently enlarge text
   while leaving the surrounding spacing unchanged. Retain visible focus feedback.
9. **Stable live layout.** Incoming pixmaps and changing status messages must not
   modify splitter positions or cause camera cards to jump.
10. **Separation of concerns.** UI widgets communicate through existing Qt signals and
    settings objects. Computer-vision, geometry, calibration, and logging modules must
    not depend on visual styling.

## Current region structure

- slim session toolbar across the top;
- resizable 3D scene above the lower data region;
- equal-width driver, road-left, and road-right camera editors;
- independent telemetry editor beside the camera region; and
- viewport controls for grid visibility, canvas theme, and scene settings; and
- Blender-like vertical context rail selecting one scrollable properties page at a
  time: Operation, Cameras, Driver, Road Lights, Geometry, or Research.
- integrated collapsible property panels with disclosure chevrons, compact headers,
  subtle detail grips, recessed value fields, and content-driven height; and
- grouped XYZ editors with first-row-aligned labels plus functional per-axis lock and
  reset actions.

## Typography and layout tokens

| Element | Logical size |
| --- | --- |
| Main control text / section header | 12 px, Segoe UI |
| Hint / device metadata | 11 px |
| Region caption / compact status badge | 10 px |
| Application name | 17 px |
| Session toolbar | 48 px high |
| Form input / command / vector row | 24 px high |
| Collapsible section header | 28 px high |
| Form label column | 104 px, with fields aligned across sections |
| Related row gap | 8 px |
| Section gap / body inset | 16 px |
| Context rail / button / icon / gap | 48 / 32 / 20 / 12 px |
| Normal properties width | 360–480 px; default approximately 27% of window width |

Keep plain labels and helper text transparent. Use subtle gray surface changes for
sections, recessed gray input fields and blue selection/focus. Avoid bright outlines
on every field. Display concise camera names; retain resolution/backend in hover text.
Long device names and genuinely constrained commands elide instead of forcing a wider
page. The panel preset occupies a full-width row above aligned width/height fields.

Qt 5 does not collapse the spacing of hidden QFormLayout rows. Conditional rows are
therefore taken out of the layout without deleting their widgets, then restored in
their original order. Default/custom threshold values and mode visibility survive
these transitions. Property panels use a preferred vertical size policy and expose
height-for-width so wrapped status text can expand; a maximum policy clips that text
at the single-line size hint. Layout changes propagate to the containing scroll page.

The driver and road camera image areas share a common stage-row height. Telemetry
has its own scroll area, allowing sixteen intersections without pushing the camera
strip taller. Compact desktop widths reduce the telemetry column to leave room for
three feeds. Narrow windows retain the existing vertical reflow, with the windshield
inset constrained by viewport height and room reserved for the legend.

All settings sections start collapsed. Click a header or focus it and press Space/
Enter to expand. Collapsed controls leave the keyboard tab order; reopening restores
their focus policies without changing values or mode visibility. Operation and Camera
icons are retained. Driver uses a profile symbol, Road Lights a bulb, Geometry a
monitor and Research a microscope. The four added SVGs are bundled
[Google Material Symbols](https://github.com/google/material-design-icons), with their
Apache 2.0 license and source list in `assets/icons/material/`.

## Review evidence — 2026-11-27

248 automated tests pass on Python 3.13. Seventeen checks added in the camera-rig/
spacing update cover calibrated poses, orientation, profile incompatibility, display-
only isolation, default collapse, keyboard behavior and icon assets. The preceding
ten layout checks cover aligned
camera fields at three widths, complete wrapped notes, conditional-row restoration,
profile field alignment, device metadata, toolbar bounds, scrolling intersections
and the short-viewport inset. Existing configuration/session tests remain included.
Native Windows renders covered representative pages at 960 x 640, 1000 x 700,
1280 x 720, 1536 x 864 and 1920 x 1080, including custom and manual settings. These
renders used sample device labels and stopped camera placeholders; they are UI
evidence, not live-camera detection or physical calibration results.

Saved views: [camera/calibration page](images/operator-ui-cameras.png) and
[geometry page](images/operator-ui-geometry.png). Also see the
[expanded camera panels](images/operator-ui-cameras-expanded.png) and the clearly
labelled [synthetic camera-rig example](images/camera-rig-offline-example.png).

## Technology decision

PyQt5 is sufficient for the required desktop UI. Qt Designer may later be used to
author `.ui` layout files, while QSS and small custom widgets provide the visual theme.
Moving to Qt Designer does not require changing Python algorithms: generated or loaded
widgets connect to the same signals and slots.

A microcontroller is not expected to run this desktop UI or the complete OpenCV,
MediaPipe, and stereo pipeline. The planned architecture keeps the Python/Qt interface
and high-level vision on a PC, Raspberry Pi-class board, Jetson, or other embedded-
Linux computer. An ESP32 or Arduino can handle deterministic sensor/actuator I/O such
as ToF distance and LCD control, exchanging compact messages with the Python system.
This boundary avoids rewriting validated geometry merely to improve the interface.

## Review checklist

- no clipped titles, field values, status text, or splitter regions at 960 x 640;
- no unnecessary background rectangle behind ordinary text or telemetry values;
- camera cards expand equally and do not inherit native frame size hints;
- viewport grid divisions do not overlap and the grid toggle changes the rendered
  grid-item visibility;
- all configuration content is reachable by scrolling;
- toggles expose focus, checked, hover, enabled, and disabled states;
- advanced toggles provide immediate visible feedback and identify where revealed
  panels are located;
- related X/Y/Z coordinates use one grouped vector editor with aligned axis labels;
- property headers collapse without altering mode-controlled child visibility;
- lock and reset affordances perform their stated action and expose tooltips;
- warning colors are not used decoratively;
- wide and narrow layouts pass off-screen regression tests; and
- a native Windows render is inspected after material visual changes.

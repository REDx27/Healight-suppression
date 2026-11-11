# GlareTracker UI Design Standard

> Adopted: 2026-11-11
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
2. **Consistent rhythm.** Use a 4 px base unit: 4 px related-item gaps, 8 px panel
   padding, and larger separation only between workflow sections.
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
8. **Readable density.** Inputs and buttons use compact technical-tool dimensions,
   but important targets retain at least a 26 px height and clear focus feedback.
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

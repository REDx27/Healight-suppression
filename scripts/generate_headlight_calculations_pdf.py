"""Generate the graphical headlight-calculation guide for GlareTracker."""

from __future__ import annotations

import math
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "GlareTracker_Headlight_Calculations_Visual_Guide.pdf"

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 34

NAVY = HexColor("#0B1722")
NAVY_2 = HexColor("#122536")
INK = HexColor("#183142")
MUTED = HexColor("#5E7180")
PAPER = HexColor("#F3F6F7")
CARD = white
GRAY = HexColor("#D8E0E5")
GRAY_2 = HexColor("#B4C1CA")
BLUE = HexColor("#2F80ED")
BLUE_DARK = HexColor("#175AA8")
CYAN = HexColor("#00AFC5")
GREEN = HexColor("#2BAE66")
AMBER = HexColor("#F4A825")
ORANGE = HexColor("#F26A2E")
RED = HexColor("#D94848")
YELLOW = HexColor("#FFD84D")


def wrap_lines(text: str, font: str, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split()
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if stringWidth(candidate, font, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def text_block(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    size: float = 10,
    leading: float | None = None,
    color=INK,
    font: str = "Helvetica",
    max_lines: int | None = None,
) -> float:
    leading = leading or size * 1.32
    lines = wrap_lines(text, font, size, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color)
    cursor = y
    for line in lines:
        c.drawString(x, cursor, line)
        cursor -= leading
    return cursor


def rounded_box(c, x, y, w, h, fill=CARD, stroke=GRAY, radius=10, line=1):
    c.setLineWidth(line)
    c.setStrokeColor(stroke)
    c.setFillColor(fill)
    c.roundRect(x, y, w, h, radius, stroke=1, fill=1)


def pill(c, text, x, y, fill=BLUE, color=white, size=8.5, pad=8):
    width = stringWidth(text, "Helvetica-Bold", size) + pad * 2
    c.setFillColor(fill)
    c.roundRect(x, y, width, 19, 9.5, stroke=0, fill=1)
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", size)
    c.drawCentredString(x + width / 2, y + 5.5, text)
    return width


def page_header(c, section: str, title: str, page: int):
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 66, PAGE_W, 66, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(CYAN)
    c.drawString(MARGIN, PAGE_H - 24, section.upper())
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(white)
    c.drawString(MARGIN, PAGE_H - 49, title)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawRightString(PAGE_W - MARGIN, 18, f"GlareTracker visual guide  |  {page}")


def source_note(c, text: str):
    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, 18, text)


def arrow(c, x1, y1, x2, y2, color=BLUE, width=2.2, head=8):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)
    angle = math.atan2(y2 - y1, x2 - x1)
    left = (
        x2 - head * math.cos(angle) + head * 0.55 * math.sin(angle),
        y2 - head * math.sin(angle) - head * 0.55 * math.cos(angle),
    )
    right = (
        x2 - head * math.cos(angle) - head * 0.55 * math.sin(angle),
        y2 - head * math.sin(angle) + head * 0.55 * math.cos(angle),
    )
    path = c.beginPath()
    path.moveTo(x2, y2)
    path.lineTo(*left)
    path.lineTo(*right)
    path.close()
    c.drawPath(path, stroke=0, fill=1)


def draw_camera(c, x, y, scale=1.0, color=BLUE_DARK):
    c.setStrokeColor(color)
    c.setFillColor(white)
    c.setLineWidth(2)
    c.roundRect(x, y, 56 * scale, 34 * scale, 5 * scale, stroke=1, fill=1)
    c.circle(x + 28 * scale, y + 17 * scale, 10 * scale, stroke=1, fill=0)
    c.circle(x + 28 * scale, y + 17 * scale, 4 * scale, stroke=1, fill=1)
    c.roundRect(x + 8 * scale, y + 34 * scale, 20 * scale, 6 * scale, 2, stroke=1, fill=1)


def draw_light(c, x, y, r=10, color=AMBER):
    c.setFillColor(color)
    c.setStrokeColor(color)
    c.circle(x, y, r, stroke=0, fill=1)
    c.setLineWidth(1.6)
    for index in range(8):
        a = index * math.pi / 4
        c.line(
            x + math.cos(a) * (r + 3),
            y + math.sin(a) * (r + 3),
            x + math.cos(a) * (r + 11),
            y + math.sin(a) * (r + 11),
        )


def draw_eye(c, x, y, scale=1.0):
    c.setStrokeColor(BLUE)
    c.setFillColor(white)
    c.setLineWidth(2)
    p = c.beginPath()
    p.moveTo(x - 22 * scale, y)
    p.curveTo(x - 10 * scale, y + 13 * scale, x + 10 * scale, y + 13 * scale, x + 22 * scale, y)
    p.curveTo(x + 10 * scale, y - 13 * scale, x - 10 * scale, y - 13 * scale, x - 22 * scale, y)
    p.close()
    c.drawPath(p, stroke=1, fill=1)
    c.setFillColor(BLUE)
    c.circle(x, y, 6 * scale, stroke=0, fill=1)


def draw_windshield(c, x, y, w, h, fill=Color(0.0, 0.69, 0.77, alpha=0.12)):
    c.setStrokeColor(CYAN)
    c.setFillColor(fill)
    c.setLineWidth(3)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=1)


def flow_card(c, x, y, w, h, number, title, detail, color=BLUE):
    rounded_box(c, x, y, w, h, CARD, GRAY, 10, 1)
    c.setFillColor(color)
    c.circle(x + 25, y + h - 25, 15, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(x + 25, y + h - 29, str(number))
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x + 48, y + h - 23, title)
    text_block(c, detail, x + 14, y + h - 48, w - 28, 8.5, 11, MUTED)


def equation_box(c, x, y, w, title, equation, note, accent=BLUE):
    rounded_box(c, x, y, w, 76, CARD, accent, 8, 1.4)
    c.setFillColor(accent)
    c.rect(x, y, 7, 76, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(MUTED)
    c.drawString(x + 18, y + 55, title.upper())
    content_width = w - 36
    equation_size = 15.0
    while equation_size > 11.5 and stringWidth(equation, "Helvetica-Bold", equation_size) > content_width:
        equation_size -= 0.5
    equation_lines = wrap_lines(equation, "Helvetica-Bold", equation_size, content_width)
    if len(equation_lines) > 1:
        equation_size = min(equation_size, 11.5)
        equation_lines = wrap_lines(equation, "Helvetica-Bold", equation_size, content_width)[:2]
        equation_y = y + 36
        equation_leading = 14
        note_y = y + 7
        note_size = 7.5
    else:
        equation_y = y + 32
        equation_leading = 14
        note_y = y + 14
        note_size = 8.5
    c.setFont("Helvetica-Bold", equation_size)
    c.setFillColor(INK)
    for line in equation_lines:
        c.drawString(x + 18, equation_y, line)
        equation_y -= equation_leading
    c.setFont("Helvetica", note_size)
    c.setFillColor(MUTED)
    c.drawString(x + 18, note_y, note)


def page_1(c):
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(BLUE)
    c.circle(PAGE_W - 85, PAGE_H - 82, 115, stroke=0, fill=1)
    c.setFillColor(NAVY_2)
    c.circle(PAGE_W - 60, PAGE_H - 62, 92, stroke=0, fill=1)

    pill(c, "VISUAL EXPLAINER", MARGIN, PAGE_H - 72, GREEN)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(MARGIN, PAGE_H - 126, "How GlareTracker Calculates")
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(YELLOW)
    c.drawString(MARGIN, PAGE_H - 166, "Headlight Glare")
    text_block(
        c,
        "A picture-first guide to finding a headlight, estimating where it is, and calculating the exact place its light ray crosses the windshield.",
        MARGIN,
        PAGE_H - 205,
        535,
        13,
        18,
        HexColor("#C9D8E3"),
    )

    y = 112
    node_w = 132
    gap = 27
    labels = [
        ("CAMERA", "sees a bright dot", BLUE),
        ("3D POSITION", "X, Y, Z in cm", GREEN),
        ("RAY", "eye toward light", RED),
        ("WINDSHIELD HIT", "blocking location", AMBER),
    ]
    for index, (title, sub, color) in enumerate(labels):
        x = MARGIN + index * (node_w + gap)
        c.setFillColor(HexColor("#142A3B"))
        c.setStrokeColor(color)
        c.setLineWidth(1.5)
        c.roundRect(x, y, node_w, 80, 10, stroke=1, fill=1)
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(x + node_w / 2, y + 49, title)
        c.setFillColor(HexColor("#B8C8D3"))
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(x + node_w / 2, y + 27, sub)
        if index < len(labels) - 1:
            arrow(c, x + node_w + 5, y + 40, x + node_w + gap - 5, y + 40, CYAN, 2)

    c.setFillColor(HexColor("#9BB0BE"))
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN, 48, "Audience: age 15+  |  Based directly on the current GlareTracker source code")
    c.showPage()


def page_2(c):
    page_header(c, "Step 1", "Turn a camera image into one reliable bright point", 2)
    top = PAGE_H - 98
    c.setFont("Helvetica", 10)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, top, "The computer does not understand 'headlight' first. It starts by finding a very bright group of pixels.")

    panel_y = 254
    panel_w = 175
    panel_h = 190
    gap = 23
    stages = [
        ("1. Camera frame", "A dark road image contains one intense light.", "frame"),
        ("2. Clean image", "Convert to gray and blur 5 x 5 to reduce tiny noise.", "gray"),
        ("3. Keep bright pixels", "Threshold 240/255, then remove small specks.", "mask"),
        ("4. Find center", "Choose the largest valid blob and calculate its center.", "center"),
    ]
    for i, (title, detail, kind) in enumerate(stages):
        x = MARGIN + i * (panel_w + gap)
        rounded_box(c, x, panel_y, panel_w, panel_h, CARD, GRAY, 10)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(INK)
        c.drawString(x + 12, panel_y + panel_h - 23, title)
        image_x, image_y = x + 12, panel_y + 70
        image_w, image_h = panel_w - 24, 78
        c.setFillColor(HexColor("#101820") if kind != "mask" else HexColor("#20252A"))
        c.roundRect(image_x, image_y, image_w, image_h, 5, stroke=0, fill=1)
        if kind in ("frame", "gray"):
            for radius, alpha_color in [
                (25, HexColor("#604B20")), (16, HexColor("#A97919")), (8, YELLOW)
            ]:
                c.setFillColor(alpha_color)
                c.circle(image_x + image_w * 0.66, image_y + image_h * 0.55, radius, stroke=0, fill=1)
        elif kind == "mask":
            c.setFillColor(white)
            c.circle(image_x + image_w * 0.66, image_y + image_h * 0.55, 13, stroke=0, fill=1)
            c.circle(image_x + 26, image_y + 19, 2, stroke=0, fill=1)
        else:
            cx, cy = image_x + image_w * 0.66, image_y + image_h * 0.55
            c.setFillColor(YELLOW)
            c.circle(cx, cy, 13, stroke=0, fill=1)
            c.setStrokeColor(GREEN)
            c.setLineWidth(2)
            c.line(cx - 18, cy, cx + 18, cy)
            c.line(cx, cy - 18, cx, cy + 18)
            c.setFillColor(GREEN)
            c.circle(cx, cy, 3, stroke=0, fill=1)
        text_block(c, detail, x + 12, panel_y + 52, panel_w - 24, 8.5, 11, MUTED)

    rounded_box(c, MARGIN, 92, PAGE_W - 2 * MARGIN, 125, HexColor("#EAF4EE"), HexColor("#A6D5B8"), 10)
    pill(c, "WHY A WEIGHTED CENTER?", MARGIN + 16, 181, GREEN)
    text_block(
        c,
        "A headlight is not a perfect single pixel. Brighter pixels receive more 'votes', so the calculated center lands closer to the true light core. The code accepts a blob only when its area is between 5 and 10,000 pixels.",
        MARGIN + 16,
        158,
        430,
        10,
        14,
        INK,
    )
    equation_box(
        c,
        520,
        116,
        275,
        "Idea",
        "center = sum(pixel x brightness) / sum(brightness)",
        "The same idea is used for horizontal and vertical position.",
        GREEN,
    )
    source_note(c, "Source: glare_tracker/headlight_detector.py - detect_bright_spot()")
    c.showPage()


def page_3(c):
    page_header(c, "Step 2A", "One camera: direction is measured, distance is assumed", 3)
    pill(c, "IMPORTANT", MARGIN, PAGE_H - 96, RED)
    text_block(
        c,
        "One flat picture tells us which direction the light is in, but not how far away it is. GlareTracker asks the user for an assumed depth D (default 120 cm).",
        MARGIN + 92,
        PAGE_H - 84,
        670,
        10.5,
        14,
        INK,
    )

    # Diagram
    dx, dy, dw, dh = MARGIN, 145, 400, 320
    rounded_box(c, dx, dy, dw, dh, CARD, GRAY, 12)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(INK)
    c.drawString(dx + 16, dy + dh - 26, "Pinhole-camera picture")
    draw_camera(c, dx + 36, dy + 135, 1.05)
    sensor_x = dx + 145
    c.setStrokeColor(GRAY_2)
    c.setLineWidth(3)
    c.line(sensor_x, dy + 95, sensor_x, dy + 245)
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawCentredString(sensor_x, dy + 80, "image")
    plane_x = dx + 340
    c.setStrokeColor(CYAN)
    c.setLineWidth(3)
    c.line(plane_x, dy + 75, plane_x, dy + 265)
    c.drawCentredString(plane_x, dy + 58, "assumed depth D")
    light_y = dy + 220
    draw_light(c, plane_x, light_y, 8)
    lens_x, lens_y = dx + 66, dy + 152
    c.setStrokeColor(AMBER)
    c.setLineWidth(2)
    c.line(lens_x, lens_y, plane_x, light_y)
    c.setFillColor(GREEN)
    c.circle(sensor_x, lens_y + (light_y - lens_y) * (sensor_x - lens_x) / (plane_x - lens_x), 4, stroke=0, fill=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(dx + 26, dy + 34, "Pixel offset + camera field of view -> direction")

    rx = 465
    rounded_box(c, rx, 145, 342, 320, CARD, GRAY, 12)
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(INK)
    c.drawString(rx + 18, 432, "The current formulas")
    equation_box(c, rx + 18, 342, 306, "Camera focal length", "fx = (image width / 2) / tan(HFOV / 2)", "HFOV is the horizontal field of view.", BLUE)
    equation_box(c, rx + 18, 253, 306, "Headlight position", "X = (u - centerX) x D / fx", "Y = D", GREEN)
    equation_box(c, rx + 18, 164, 306, "Height", "Z = cameraHeight - (v - centerY) x D / fy", "The image Y direction points downward.", CYAN)

    rounded_box(c, MARGIN, 68, PAGE_W - 2 * MARGIN, 58, HexColor("#FFF5DE"), HexColor("#E6C16B"), 9)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(MARGIN + 15, 105, "Worked example")
    text_block(
        c,
        "1280 x 720 image, HFOV 70 deg, point (u=700, v=390), D=120 cm, camera height=19.5 cm -> fx about 914 px -> headlight about (X=7.9, Y=120, Z=15.6) cm.",
        MARGIN + 15,
        87,
        PAGE_W - 2 * MARGIN - 30,
        9,
        12,
        INK,
    )
    source_note(c, "Source: MonocularHeadlightDetectorThread in glare_tracker/headlight_detector.py")
    c.showPage()


def page_4(c):
    page_header(c, "Step 2B", "Two cameras: pixel shift reveals distance", 4)
    text_block(
        c,
        "Stereo vision works like your two eyes. A nearby object appears to move more between the left and right views. That horizontal movement is called disparity.",
        MARGIN,
        PAGE_H - 90,
        750,
        10.5,
        14,
        INK,
    )

    # Top-view stereo diagram
    x0, y0, w0, h0 = MARGIN, 150, 430, 330
    rounded_box(c, x0, y0, w0, h0, CARD, GRAY, 12)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(INK)
    c.drawString(x0 + 16, y0 + h0 - 26, "Top view")
    cam_y = y0 + 65
    cam_l = x0 + 120
    cam_r = x0 + 290
    draw_camera(c, cam_l - 28, cam_y, 0.85)
    draw_camera(c, cam_r - 28, cam_y, 0.85)
    c.setStrokeColor(BLUE)
    c.setLineWidth(2)
    c.line(cam_l, cam_y - 10, cam_r, cam_y - 10)
    c.setFillColor(BLUE_DARK)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString((cam_l + cam_r) / 2, cam_y - 25, "baseline B")
    light_x, light_y = x0 + 230, y0 + 275
    draw_light(c, light_x, light_y, 10)
    c.setStrokeColor(AMBER)
    c.setLineWidth(2)
    c.line(cam_l, cam_y + 28, light_x, light_y)
    c.line(cam_r, cam_y + 28, light_x, light_y)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(x0 + 24, y0 + 115, "Left camera sees pixel x1")
    c.drawString(x0 + 244, y0 + 115, "Right camera sees pixel x2")
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(x0 + w0 / 2, y0 + 145, "disparity = x1 - x2")

    rx = 495
    equation_box(c, rx, 382, 312, "Distance", "depth = focalLength x baseline / disparity", "Bigger disparity -> closer light", BLUE)
    equation_box(c, rx, 292, 312, "Sideways", "Xcamera = (x1 - centerX) x depth / focalLength", "Then shift by half the baseline.", GREEN)
    equation_box(c, rx, 202, 312, "Height", "Zglobal = cameraHeight - Ycamera", "Camera pixels point downward; world Z points up.", CYAN)

    rounded_box(c, rx, 103, 312, 80, HexColor("#FFF5DE"), HexColor("#E6C16B"), 9)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(rx + 14, 160, "Fallback example")
    text_block(c, "f=900 px, B=25 cm, disparity=75 px -> depth=300 cm. This fallback is an estimate, not a calibrated measurement.", rx + 14, 142, 284, 9, 12, INK)

    rounded_box(c, MARGIN, 64, 430, 69, HexColor("#EAF4EE"), HexColor("#A6D5B8"), 9)
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(GREEN)
    c.drawString(MARGIN + 14, 111, "CALIBRATED PATH")
    text_block(c, "Correct lens distortion -> rectify both images -> check similar scanlines -> calculate disparity using the saved camera matrices.", MARGIN + 14, 94, 402, 8.8, 11.5, INK)
    source_note(c, "Source: HeadlightDetectorThread and StereoCalibrationResult")
    c.showPage()


def page_5(c):
    page_header(c, "Step 3", "Put every measurement into one coordinate system", 5)
    text_block(
        c,
        "A position such as (7, 120, 15) is useful only when everyone agrees what X, Y, and Z mean. GlareTracker uses the windshield as the map origin.",
        MARGIN,
        PAGE_H - 90,
        750,
        10.5,
        14,
        INK,
    )

    # Coordinate diagram
    x, y, w, h = MARGIN, 105, 470, 370
    rounded_box(c, x, y, w, h, CARD, GRAY, 12)
    origin_x, origin_y = x + 235, y + 160
    draw_windshield(c, origin_x - 90, origin_y - 20, 180, 125)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(origin_x, origin_y + 122, "WINDSHIELD PLANE: Y = 0")
    # Axes
    arrow(c, origin_x, origin_y, origin_x + 150, origin_y, RED, 2.5)
    arrow(c, origin_x, origin_y, origin_x, origin_y + 145, BLUE, 2.5)
    arrow(c, origin_x, origin_y, origin_x - 115, origin_y - 100, GREEN, 2.5)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(RED)
    c.drawString(origin_x + 154, origin_y - 3, "X: right")
    c.setFillColor(BLUE)
    c.drawString(origin_x + 7, origin_y + 145, "Z: up")
    c.setFillColor(GREEN)
    c.drawString(origin_x - 150, origin_y - 108, "Y: forward")
    draw_eye(c, origin_x - 105, origin_y - 46, 0.7)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(origin_x - 174, origin_y - 68, "driver: Y is negative")
    draw_light(c, origin_x + 90, origin_y + 58, 8)
    c.drawString(origin_x + 106, origin_y + 54, "headlight: Y is positive")

    rx = 535
    rounded_box(c, rx, 285, 272, 190, HexColor("#EBF3FA"), HexColor("#A8C8E6"), 10)
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(BLUE_DARK)
    c.drawString(rx + 16, 444, "Camera-space -> project-space")
    items = [
        "Camera X becomes global X (sideways).",
        "Camera depth becomes global Y (forward).",
        "Camera-down becomes negative global Z (up).",
        "The rig is shifted by half its stereo baseline.",
    ]
    yy = 416
    for item in items:
        c.setFillColor(GREEN)
        c.circle(rx + 22, yy + 3, 3, stroke=0, fill=1)
        yy = text_block(c, item, rx + 34, yy + 7, 220, 9, 13, INK) - 7

    rounded_box(c, rx, 105, 272, 160, HexColor("#FDEBEC"), HexColor("#E8A4A7"), 10)
    pill(c, "HONEST LIMITATION", rx + 16, 226, RED)
    text_block(
        c,
        "The code assumes the outdoor camera rig is mounted at the windshield top-center and aimed as expected. A measured camera-to-windshield rotation and translation is still needed for measurement-grade physical coordinates.",
        rx + 16,
        203,
        240,
        9,
        13,
        INK,
    )
    source_note(c, "Coordinate model: X lateral, Y depth, Z height; see PROJECT_STATUS.md and headlight_detector.py")
    c.showPage()


def page_6(c):
    page_header(c, "Step 4", "Draw a ray from the eye to the headlight", 6)
    text_block(
        c,
        "Now both the eye and headlight have 3D coordinates. The program draws a straight line between them and asks: where does this line cross Y = 0?",
        MARGIN,
        PAGE_H - 90,
        750,
        10.5,
        14,
        INK,
    )

    # Side view diagram
    x, y, w, h = MARGIN, 156, 500, 315
    rounded_box(c, x, y, w, h, CARD, GRAY, 12)
    ground_y = y + 55
    c.setStrokeColor(GRAY_2)
    c.setLineWidth(1)
    c.line(x + 30, ground_y, x + w - 25, ground_y)
    glass_x = x + 230
    c.setStrokeColor(CYAN)
    c.setLineWidth(5)
    c.line(glass_x, ground_y, glass_x, y + h - 35)
    c.setFillColor(CYAN)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(glass_x, y + h - 24, "Y = 0 windshield")
    eye_x, eye_y = x + 75, y + 130
    light_x, light_y = x + 435, y + 245
    draw_eye(c, eye_x, eye_y, 0.72)
    draw_light(c, light_x, light_y, 9)
    c.setStrokeColor(RED)
    c.setLineWidth(3)
    c.line(eye_x, eye_y, light_x, light_y)
    ratio = (glass_x - eye_x) / (light_x - eye_x)
    hit_y = eye_y + ratio * (light_y - eye_y)
    c.setFillColor(YELLOW)
    c.circle(glass_x, hit_y, 10, stroke=0, fill=1)
    c.setStrokeColor(ORANGE)
    c.setLineWidth(2)
    c.circle(glass_x, hit_y, 17, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(BLUE_DARK)
    c.drawString(eye_x - 38, eye_y - 31, "EYE: Y < 0")
    c.drawString(light_x - 42, light_y - 31, "LIGHT: Y > 0")
    c.setFillColor(ORANGE)
    c.drawString(glass_x + 15, hit_y + 6, "intersection")

    rx = 565
    equation_box(c, rx, 385, 242, "How far along the line?", "t = -eyeY / (lightY - eyeY)", "Valid when 0 <= t <= 1.", BLUE)
    equation_box(c, rx, 292, 242, "Horizontal hit", "hitX = eyeX + t x (lightX - eyeX)", "Same line, same fraction t.", RED)
    equation_box(c, rx, 199, 242, "Vertical hit", "hitZ = eyeZ + t x (lightZ - eyeZ)", "The hit always has Y = 0.", GREEN)

    rounded_box(c, MARGIN, 65, PAGE_W - 2 * MARGIN, 70, HexColor("#FFF5DE"), HexColor("#E6C16B"), 9)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(MARGIN + 15, 114, "Worked example from the real function")
    text_block(
        c,
        "Eye E=(0, -50, 10) cm and light L=(12, 120, 12) cm -> t=50/170=0.294 -> windshield hit I=(3.53, 0, 10.59) cm.",
        MARGIN + 15,
        94,
        PAGE_W - 2 * MARGIN - 30,
        10,
        13,
        INK,
    )
    source_note(c, "Source: glare_tracker/geometry.py - compute_intersection()")
    c.showPage()


def page_7(c):
    page_header(c, "Step 5", "Convert the windshield hit into a screen pixel", 7)
    text_block(
        c,
        "The geometry result is measured in centimeters. A real LCD needs a row and column in pixels, so the program scales the point across the panel.",
        MARGIN,
        PAGE_H - 90,
        750,
        10.5,
        14,
        INK,
    )

    # Windshield mapping diagram
    x, y, w, h = MARGIN, 126, 500, 345
    rounded_box(c, x, y, w, h, CARD, GRAY, 12)
    panel_x, panel_y, panel_w, panel_h = x + 55, y + 70, 390, 220
    draw_windshield(c, panel_x, panel_y, panel_w, panel_h, HexColor("#E6F8FA"))
    c.setStrokeColor(GRAY)
    c.setLineWidth(0.6)
    for i in range(1, 8):
        c.line(panel_x + panel_w * i / 8, panel_y, panel_x + panel_w * i / 8, panel_y + panel_h)
    for i in range(1, 5):
        c.line(panel_x, panel_y + panel_h * i / 5, panel_x + panel_w, panel_y + panel_h * i / 5)
    # Example point: normalized 0.602, 0.457
    dot_x = panel_x + panel_w * 0.602
    dot_y = panel_y + panel_h * (1 - 0.457)
    c.setFillColor(YELLOW)
    c.circle(dot_x, dot_y, 10, stroke=0, fill=1)
    c.setStrokeColor(ORANGE)
    c.setLineWidth(2)
    c.circle(dot_x, dot_y, 17, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(INK)
    c.drawString(dot_x + 18, dot_y + 5, "(1156, 493)")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(panel_x, panel_y - 20, "left = -width/2")
    c.drawRightString(panel_x + panel_w, panel_y - 20, "right = +width/2")
    c.drawString(panel_x - 43, panel_y + panel_h - 2, "top")
    c.drawString(panel_x - 53, panel_y + 1, "bottom")

    rx = 565
    equation_box(c, rx, 383, 242, "Horizontal pixel", "px = (hitX + width/2) / width x pixelsX", "World center becomes screen center.", BLUE)
    equation_box(c, rx, 287, 242, "Vertical pixel", "py = (height - hitZ) / height x pixelsY", "Pixel rows count downward from the top.", GREEN)
    rounded_box(c, rx, 126, 242, 140, HexColor("#FFF5DE"), HexColor("#E6C16B"), 9)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawString(rx + 14, 243, "Worked example")
    text_block(
        c,
        "Panel: 34.5 x 19.5 cm at 1920 x 1080 pixels. Hit: (3.53, 0, 10.59) cm. Result: pixel (1156, 493).",
        rx + 14,
        222,
        214,
        9.2,
        13,
        INK,
    )
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(rx + 14, 149, "Outside the panel? Return no pixel.")
    source_note(c, "Source: glare_tracker/geometry.py - intersection_to_pixel()")
    c.showPage()


def page_8(c):
    page_header(c, "Putting it together", "The complete idea in one page", 8)
    y = 366
    w = 128
    h = 104
    gap = 20
    steps = [
        ("See", "Camera captures the road", BLUE),
        ("Detect", "Bright pixels become (u, v)", AMBER),
        ("Locate", "Single or stereo gives X, Y, Z", GREEN),
        ("Connect", "Draw eye-to-light ray", RED),
        ("Intersect", "Find where Y becomes zero", ORANGE),
    ]
    for i, (title, detail, color) in enumerate(steps):
        x = MARGIN + i * (w + gap)
        flow_card(c, x, y, w, h, i + 1, title, detail, color)
        if i < len(steps) - 1:
            arrow(c, x + w + 3, y + h / 2, x + w + gap - 3, y + h / 2, CYAN, 1.8, 6)

    rounded_box(c, MARGIN, 174, 365, 158, HexColor("#EAF4EE"), HexColor("#A6D5B8"), 10)
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(GREEN)
    c.drawString(MARGIN + 16, 304, "What the software already does")
    good = [
        "Finds the primary bright light core.",
        "Supports manual, one-camera, and stereo input.",
        "Calculates ray-plane intersections for 1-4 lights.",
        "Checks whether each hit is inside the windshield.",
        "Can map a hit to an LCD pixel.",
    ]
    yy = 281
    for item in good:
        c.setFillColor(GREEN)
        c.circle(MARGIN + 21, yy + 3, 3, stroke=0, fill=1)
        c.setFont("Helvetica", 9)
        c.setFillColor(INK)
        c.drawString(MARGIN + 33, yy, item)
        yy -= 22

    rx = 430
    rounded_box(c, rx, 174, 377, 158, HexColor("#FDEBEC"), HexColor("#E8A4A7"), 10)
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(RED)
    c.drawString(rx + 16, 304, "What must improve before physical blocking")
    todo = [
        "Measure each camera pose relative to the windshield.",
        "Guide calibration through the user interface.",
        "Use separate left-eye and right-eye rays.",
        "Filter jitter and predict small system delays.",
        "Validate error with real cameras and a real LCD.",
    ]
    yy = 281
    for item in todo:
        c.setFillColor(RED)
        c.circle(rx + 21, yy + 3, 3, stroke=0, fill=1)
        c.setFont("Helvetica", 9)
        c.setFillColor(INK)
        c.drawString(rx + 33, yy, item)
        yy -= 22

    rounded_box(c, MARGIN, 62, PAGE_W - 2 * MARGIN, 84, CARD, GRAY, 10)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(BLUE_DARK)
    c.drawString(MARGIN + 16, 121, "Four words to remember")
    glossary = [
        ("Threshold", "how bright a pixel must be"),
        ("Disparity", "left-right pixel shift"),
        ("Ray", "a straight directed line"),
        ("Intersection", "where two things meet"),
    ]
    gx = MARGIN + 16
    for word, meaning in glossary:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(INK)
        c.drawString(gx, 96, word)
        c.setFont("Helvetica", 8)
        c.setFillColor(MUTED)
        c.drawString(gx, 80, meaning)
        gx += 190
    source_note(c, "Project sources: headlight_detector.py, geometry.py, calibration.py, tracking.py, and PROJECT_STATUS.md")
    c.showPage()


def build_pdf():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("How GlareTracker Calculates Headlight Glare")
    c.setAuthor("GlareTracker Research Project")
    c.setSubject("Visual guide to headlight detection, 3D location, and windshield intersection")
    for page in (page_1, page_2, page_3, page_4, page_5, page_6, page_7, page_8):
        page(c)
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()

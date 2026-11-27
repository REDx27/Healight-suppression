"""Build bundled PNG figures and one self-contained printable offline manual."""
import base64
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QRectF, Qt
    from PyQt5.QtGui import QImage, QPainter
    from PyQt5.QtSvg import QSvgRenderer
    app = QApplication.instance() or QApplication([])
    assets = ROOT / "assets" / "calibration"
    for name in ("flat_board", "pose_coverage", "stereo_capture", "offline_workflow",
                 "rig_coordinates", "tof_wiring", "tof_offsets"):
        renderer = QSvgRenderer(str(assets / (name + ".svg")))
        if not renderer.isValid():
            raise RuntimeError("Invalid or missing SVG: " + name)
        box = renderer.viewBoxF()
        width = 1200
        height = round(width * box.height() / box.width())
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, width, height))
        painter.end()
        if not image.save(str(assets / (name + ".png"))):
            raise RuntimeError("Cannot save guide image " + name)
    # Import only after figures exist: the app supplies an explicit missing-image
    # message when an installation has lost one of its bundled files.
    from glare_tracker.calibration_help import ALL_GUIDE_SECTIONS, IMAGE_WIDTH_TOKEN
    sections = []
    navigation = []
    for index, (title, body) in enumerate(ALL_GUIDE_SECTIONS):
        navigation.append(f'<li><a href="#stage-{index}">{title}</a></li>')
        def embed(match):
            from urllib.parse import unquote, urlparse
            path = unquote(urlparse(match.group(1)).path)
            if path.startswith("/") and len(path) > 2 and path[2] == ":":
                path = path[1:]
            encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
            return 'src="data:image/png;base64,' + encoded + '"'
        body = re.sub(r'src="(file:[^"]+)"', embed, body)
        body = body.replace(IMAGE_WIDTH_TOKEN, "680")
        sections.append(f'<section id="stage-{index}"><h1>{index+1}. {title}</h1>{body}</section>')
    html = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GlareTracker — offline calibration manual</title><style>
body{max-width:850px;margin:32px auto;padding:0 24px;color:#202938;background:white;font:16px/1.55 Arial,sans-serif}
h1,h2,h3{color:#163c62;line-height:1.25}h1{font-size:26px}h2{font-size:23px}h3{font-size:19px}
img{display:block;max-width:100%;height:auto;margin:20px auto}table{border-collapse:collapse;width:100%;font-size:14px}
td,th{border:1px solid #aebdcc;padding:9px;text-align:left}section{margin:48px 0;border-top:2px solid #d7e2ec;padding-top:16px}
li{margin-bottom:12px}a{color:#155c9b}pre{white-space:pre-wrap} @media print{body{margin:0;font-size:11pt}section{break-before:page}img,table{break-inside:avoid}a{color:inherit}}
</style><h1>GlareTracker offline calibration manual</h1>
<p>Operator edition · reviewed 2026-11-27. All instructions and images in this file work without internet.
External reference/video links need internet and are optional. Use your measured values, not copied example numbers.</p>
<p><b>Hardware gate:</b> the ToF controller/bridge firmware is not supplied by this repository.
Use the explicit camera-only route until a technical helper commissions it.</p>
<p>Print with your browser's Print command. This HTML file contains its pictures; copying this one file preserves them.</p><ol>'''
    html += "".join(navigation) + "</ol>" + "".join(sections) + "</html>"
    (assets / "offline_manual.html").write_text(html, encoding="utf-8")
    print("Built 7 PNG figures and assets/calibration/offline_manual.html")


if __name__ == "__main__":
    main()

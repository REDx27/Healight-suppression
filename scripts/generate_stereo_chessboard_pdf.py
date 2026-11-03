"""Generate the dimensioned A4 road-stereo calibration checkerboard."""

from pathlib import Path

from reportlab.lib.colors import black, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


INNER_COLUMNS = 9
INNER_ROWS = 6
SQUARE_MM = 20.0
OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "pdf"
    / "road_stereo_chessboard_A4_9x6_20mm.pdf"
)


def generate(output: Path = OUTPUT) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = landscape(A4)
    square = SQUARE_MM * mm
    square_columns = INNER_COLUMNS + 1
    square_rows = INNER_ROWS + 1
    board_width = square_columns * square
    board_height = square_rows * square
    origin_x = (page_width - board_width) / 2.0
    origin_y = (page_height - board_height) / 2.0

    document = canvas.Canvas(
        str(output), pagesize=(page_width, page_height), pageCompression=1)
    document.setTitle("GlareTracker Road Stereo Chessboard - 9x6 - 20 mm")
    document.setAuthor("GlareTracker research project")
    document.setSubject(
        "A4 landscape camera-calibration board; print at actual size (100 percent)")
    document.setFillColor(white)
    document.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    for row in range(square_rows):
        for column in range(square_columns):
            if (row + column) % 2 == 0:
                document.setFillColor(black)
                document.rect(
                    origin_x + column * square,
                    origin_y + (square_rows - row - 1) * square,
                    square,
                    square,
                    fill=1,
                    stroke=0,
                )

    document.setFillColor(black)
    document.setFont("Helvetica", 7)
    document.drawCentredString(
        page_width / 2.0,
        5.5 * mm,
        "9 x 6 inner corners | 20.00 mm squares | A4 landscape | Print Actual size / 100% | Disable Fit to page",
    )
    document.showPage()
    document.save()
    return output


if __name__ == "__main__":
    print(generate())

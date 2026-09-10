from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

output = Path("assets/glaretracker-icon.ico")
sizes = (16, 24, 32, 48, 64, 128, 256)
images = []

for size in sizes:
    scale = size / 256
    image = Image.new("RGBA", (size, size), (13, 17, 23, 255))
    draw = ImageDraw.Draw(image)

    def point(value):
        return int(round(value * scale))

    draw.rounded_rectangle(
        (point(8), point(8), point(248), point(248)),
        radius=point(48), fill=(13, 17, 23, 255)
    )
    windshield = [
        (point(48), point(190)), (point(64), point(58)),
        (point(82), point(40)), (point(174), point(40)),
        (point(192), point(58)), (point(208), point(190)),
        (point(192), point(210)), (point(64), point(210)),
    ]
    draw.polygon(windshield, fill=(12, 35, 52, 255))
    draw.line(windshield + [windshield[0]], fill=(0, 191, 214, 255), width=max(1, point(9)), joint="curve")
    draw.line((point(64), point(177), point(192), point(177)), fill=(85, 219, 234, 180), width=max(1, point(4)))
    draw.line((point(82), point(62), point(174), point(62)), fill=(85, 219, 234, 160), width=max(1, point(4)))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    radius = point(42)
    center = point(128)
    for current in range(radius, 0, -1):
        alpha = int(90 * (1 - current / max(1, radius)) ** 0.5)
        glow_draw.ellipse((center - current, center - current, center + current, center + current), fill=(255, 169, 0, alpha))
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(max(1, point(3)))))
    draw = ImageDraw.Draw(image)
    draw.ellipse((point(116), point(107), point(140), point(131)), fill=(255, 247, 168, 255), outline=(255, 179, 0, 255), width=max(1, point(5)))
    draw.line((point(128), point(78), point(128), point(160)), fill=(126, 231, 242, 230), width=max(1, point(4)))
    draw.line((point(87), point(119), point(169), point(119)), fill=(126, 231, 242, 230), width=max(1, point(4)))
    draw.ellipse((point(123), point(114), point(133), point(124)), fill=(13, 17, 23, 255))
    images.append(image)

images[-1].save(output, format="ICO", sizes=[(size, size) for size in sizes])
print(output)

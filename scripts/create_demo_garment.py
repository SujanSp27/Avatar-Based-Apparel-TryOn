"""Deterministic synthetic flat-lay test fixture, explicitly labelled in the UI/docs."""

from pathlib import Path

from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
image = Image.new("RGB", (600, 660), "#f6f5ef")
mask = Image.new("L", image.size)
draw = ImageDraw.Draw(mask)
draw.polygon(
    [
        (210, 75),
        (150, 94),
        (45, 203),
        (119, 269),
        (164, 225),
        (155, 586),
        (448, 586),
        (439, 225),
        (483, 269),
        (555, 203),
        (450, 94),
        (390, 75),
        (366, 110),
        (234, 110),
    ],
    fill=255,
)
fabric = Image.new("RGB", image.size, "#2f6561")
ink = ImageDraw.Draw(fabric)
for y in range(138, 590, 46):
    ink.rectangle((0, y, 600, y + 9), fill="#d9dfc9")
ink.line((220, 90, 241, 126, 361, 126, 381, 90), fill="#1b4e4b", width=8)
image.paste(fabric, mask=mask)
image.save(root / "data/raw/garment-demo.png")
print("Created synthetic striped T-shirt fixture")

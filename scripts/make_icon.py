"""Draw the project's own geometric mark; no external artwork."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((4, 4, 252, 252), radius=56, fill="#111b22")
d.line([(66, 199), (66, 71), (108, 71)], fill="#78dcb9", width=21)
d.arc((66, 61, 148, 153), -90, 90, fill="#78dcb9", width=21)
d.line([(108, 143), (66, 143)], fill="#78dcb9", width=21)
d.line([(170, 91), (203, 128), (170, 165)], fill="#b8c9de", width=14)
(root / "assets").mkdir(exist_ok=True)
im.save(root / "assets/pypilot.ico", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
im.save(root / "assets/pypilot.png")

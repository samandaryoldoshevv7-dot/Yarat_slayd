"""Har bir shablon uchun ko'rinish rasmini (muqova + matnli slayd) previews/ ga yaratadi.

Talab: LibreOffice (soffice) va poppler-utils (pdftoppm).
Ishga tushirish: python scripts/make_previews.py
"""
import io
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app import config, pptx_builder, templates  # noqa: E402

OUTLINE = {"title": "Mavzuingiz shu yerda", "subtitle": "Taqdimot", "slides": ["Kirish", "Asosiy qism"]}
CONTENT = {
    "slides": [
        {"title": "Kirish", "bullets": ["Birinchi muhim fikr shu yerda bo'ladi", "Ikkinchi fikr va misollar",
                                        "Uchinchi fikr, raqamlar va faktlar"], "image_query": ""},
        {"title": "Asosiy qism", "bullets": ["Matn"], "image_query": ""},
    ],
    "closing": "",
}


def sample_image() -> bytes:
    im = Image.new("RGB", (800, 600), (210, 214, 222))
    d = ImageDraw.Draw(im)
    d.polygon([(0, 600), (300, 250), (520, 600)], fill=(150, 160, 175))
    d.polygon([(300, 600), (560, 320), (800, 600)], fill=(120, 130, 148))
    d.ellipse((560, 90, 680, 210), fill=(245, 190, 80))
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


def main() -> None:
    config.PREVIEWS_DIR.mkdir(exist_ok=True)
    img = sample_image()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for t in templates.all_templates():
            pptx_builder.build(t.path, tmp / f"{t.id}.pptx", "uz", OUTLINE, CONTENT, [img, None])
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp),
                        *map(str, sorted(tmp.glob("*.pptx")))], check=True, capture_output=True)
        for t in templates.all_templates():
            subprocess.run(["pdftoppm", "-r", "36", "-png", "-f", "1", "-l", "3",
                            str(tmp / f"{t.id}.pdf"), str(tmp / t.id)], check=True)
            pages = sorted(tmp.glob(f"{t.id}-*.png"))
            cover, body = Image.open(pages[0]), Image.open(pages[2])
            w, h = cover.size
            sheet = Image.new("RGB", (w * 2 + 12, h), "white")
            sheet.paste(cover, (0, 0))
            sheet.paste(body, (w + 12, 0))
            sheet.save(config.PREVIEWS_DIR / f"{t.id}.jpg", quality=82)
            print("✓", t.id)


if __name__ == "__main__":
    main()

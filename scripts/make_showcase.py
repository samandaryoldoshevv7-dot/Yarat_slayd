"""Sayt uchun namuna slayd rasmlarini (web/static/showcase/) haqiqiy dvijok orqali yasaydi.

Matnlar qo'lda yozilgan namunalar; dizayn va yig'ish botdagi bilan bir xil (pptx_builder).
Talab: LibreOffice (soffice) va poppler-utils (pdftoppm).  Ishga tushirish: python scripts/make_showcase.py
"""
import io
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from app import pptx_builder  # noqa: E402

OUT = ROOT / "web" / "static" / "showcase"


def media(template: str, name: str) -> bytes:
    with zipfile.ZipFile(ROOT / "templates" / f"template_{template}.pptx") as z:
        data = z.read(f"ppt/media/{name}")
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((1600, 1600))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


DECKS = {
    "eco": {
        "template": "13",
        "image": ("13", "image4.jpeg"),
        "image_first": False,
        "outline": {
            "title": "Qayta ishlash va yashil iqtisodiyot",
            "subtitle": "Chiqindidan resursga",
            "slides": ["Muammoning ko'lami", "Qayta ishlash qanday ishlaydi", "O'zbekistondagi tajriba", "Xulosa"],
        },
        "content": {
            "slides": [
                {"title": "Muammoning ko'lami", "bullets": [
                    "Maishiy chiqindilarning katta qismi hali ham poligonlarga tashlanadi",
                    "Plastik tabiatda yuzlab yil davomida parchalanmasdan qoladi",
                    "Chiqindi poligonlari tuproq va yer osti suvlarini ifloslantiradi",
                    "Saralash odatlari oiladan va maktabdan boshlanadi"]},
                {"title": "Qayta ishlash qanday ishlaydi", "bullets": [
                    "Yig'ish: chiqindilar turlari bo'yicha alohida konteynerlarga tashlanadi",
                    "Saralash: qog'oz, plastik, shisha va metall ajratiladi",
                    "Qayta ishlash: xomashyo tozalanib, yangi mahsulotga aylantiriladi",
                    "Natija: kamroq tabiiy resurs va kamroq energiya sarflanadi"]},
                {"title": "O'zbekistondagi tajriba", "bullets": [
                    "Shaharlarda saralangan chiqindi uchun konteynerlar ko'paymoqda",
                    "Plastik va makulatura qabul qilish shoxobchalari ishlamoqda",
                    "Tadbirkorlar qayta ishlangan xomashyodan mahsulot ishlab chiqarmoqda"]},
                {"title": "Xulosa", "bullets": [
                    "Qayta ishlash ham ekologik, ham iqtisodiy foyda beradi",
                    "Har bir inson saralashdan boshlab hissa qo'sha oladi"]},
            ],
            "closing": "Toza kelajak bugungi odatlarimizdan boshlanadi.",
        },
        "pages": {1: "eco-cover", 2: "eco-agenda", 4: "eco-text"},
    },
    "ai": {
        "template": "08",
        "image": ("09", "image4.jpg"),
        "outline": {
            "title": "Sun'iy intellekt ta'limda",
            "subtitle": "Imkoniyatlar va mas'uliyat",
            "slides": ["Sun'iy intellekt nima?", "Darsda qo'llash", "Xavf va cheklovlar", "Xulosa"],
        },
        "content": {
            "slides": [
                {"title": "Sun'iy intellekt nima?", "bullets": [
                    "Ma'lumotlardan o'rganib, vazifani bajaradigan kompyuter tizimlari",
                    "Matn yozish, tarjima qilish va rasm tahlil qilishga qodir",
                    "O'qituvchining o'rnini emas, vaqtini tejaydigan yordamchi"]},
                {"title": "Darsda qo'llash", "bullets": [
                    "Mavzu bo'yicha qo'shimcha misollar va savollar tayyorlash",
                    "O'quvchi darajasiga mos mashqlar tanlash",
                    "Taqdimot va tarqatma materiallarni tez tayyorlash"]},
                {"title": "Xavf va cheklovlar", "bullets": ["Ma'lumotni tekshirish odati shart"]},
                {"title": "Xulosa", "bullets": ["To'g'ri qo'llansa, ta'lim sifatini oshiradi"]},
            ],
            "closing": "",
        },
        "pages": {1: "ai-cover", 3: "ai-content"},
    },
    "biz": {
        "template": "07",
        "image": ("02", "image5.jpg"),
        "outline": {
            "title": "Kichik biznesni raqamlashtirish",
            "subtitle": "Amaliy qo'llanma",
            "slides": ["Nega raqamlashtirish kerak", "Birinchi qadamlar", "Xulosa"],
        },
        "content": {
            "slides": [
                {"title": "Nega raqamlashtirish kerak", "bullets": [
                    "Mijozlar mahsulotni avval internetda qidiradi",
                    "Onlayn to'lov va yetkazib berish savdoni oshiradi",
                    "Hisob-kitobni avtomatlashtirish xatolarni kamaytiradi"]},
                {"title": "Birinchi qadamlar", "bullets": ["Telegram kanal va onlayn katalog"]},
                {"title": "Xulosa", "bullets": ["Kichik qadamlardan boshlang"]},
            ],
            "closing": "",
        },
        "pages": {1: "biz-cover", 3: "biz-content"},
    },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for key, d in DECKS.items():
            img = media(*d["image"])
            pics = [img if d.get("image_first", True) else None] + [None] * (len(d["content"]["slides"]) - 1)
            pptx = tmp / f"{key}.pptx"
            pptx_builder.build(ROOT / "templates" / f"template_{d['template']}.pptx", pptx, "uz",
                               d["outline"], d["content"], pics)
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(pptx)],
                           check=True, capture_output=True)
            for page, name in d["pages"].items():
                base = tmp / f"{key}-{page}"
                subprocess.run(["pdftoppm", "-r", "110", "-png", "-singlefile", "-f", str(page), "-l", str(page),
                                str(tmp / f"{key}.pdf"), str(base)], check=True)
                im = Image.open(f"{base}.png").convert("RGB")
                im.thumbnail((1280, 720))
                im.save(OUT / f"{name}.jpg", quality=82, optimize=True, progressive=True)
                print("✓", name)


if __name__ == "__main__":
    main()

"""50 ta shablonni avtomatik sifat nazoratidan o'tkazadi.

Har bir shablonda og'ir sinov taqdimoti yig'iladi (uzun sarlavha va punktlar, rasmlar, diagramma,
katta raqamlar, bosqichlar, vaqt chizig'i), LibreOffice orqali PDF'ga aylantiriladi va tekshiriladi:
  * fayl yig'iladimi va slaydlar soni to'g'rimi;
  * matn slayd chegarasidan chiqib ketyaptimi yoki sig'dirish uchun juda maydalashib ketganmi;
  * shablonning o'zida begona yozuv (havola, @username, "bot", "slayd" brendi) qolganmi — litsenziya belgisi;
  * shablon qaysi shriftlarni talab qiladi.

Natija: data/qa/report.md (jadval) va data/qa/<id>.jpg (har shablon slaydlari bitta rasmda).
Ko'z bilan tekshirish baribir kerak: skript faqat aniq texnik nosozliklarni topadi.

Talab: LibreOffice (soffice) va poppler-utils. Ishga tushirish: python scripts/qa_templates.py [01 02 ...]
"""
import asyncio
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app import config, pptx_builder, preview, templates  # noqa: E402

OUT = config.ROOT / "data" / "qa"
LONG = ("Bu punkt ataylab uzun yozilgan: shablon uzun matnni sig'dira oladimi, shrift kichrayadimi "
        "yoki matn slayd chegarasidan chiqib ketadimi — shuni tekshiramiz")
OUTLINE = {
    "title": "Qayta tiklanadigan energiya manbalari va O'zbekistonning yashil iqtisodiyotga o'tishi",
    "subtitle": "Sifat nazorati uchun sinov taqdimoti",
    "slides": ["Kirish", "Asosiy tushunchalar va ularning amaliy ahamiyati", "Raqamlarda", "Ishlab chiqarish",
               "Bosqichlar", "Tarix", "Xulosa"],
}
CONTENT = {
    "slides": [
        {"title": "Kirish", "bullets": [LONG] * 1 + ["Qisqa punkt", "Ikkinchi qisqa punkt", "Uchinchi punkt"]},
        {"title": OUTLINE["slides"][1], "bullets": [LONG + f" ({k})" for k in range(1, 6)]},
        {"title": "Raqamlarda", "bullets": ["Asosiy raqamlar", "Taxminiy qiymatlar"], "layout": "stats",
         "items": [{"label": "quyosh stansiyalari quvvati", "value": "4,5 GVt", "text": ""},
                   {"label": "shamol stansiyalari", "value": "1,5 GVt", "text": ""},
                   {"label": "yashil energiya ulushi 2030-yilga", "value": "40 %", "text": ""}]},
        {"title": "Ishlab chiqarish", "bullets": ["Diagramma va izoh", "Ikkinchi izoh"],
         "chart": {"type": "column", "title": "Ishlab chiqarish, mlrd kVt·soat", "unit": "mlrd",
                   "labels": ["2020", "2021", "2022", "2023", "2024"], "values": [1, 2, 4, 7, 11]}},
        {"title": "Bosqichlar", "bullets": ["Jarayon"], "layout": "steps",
         "items": [{"label": "Tahlil", "value": "", "text": "Hududlarning quyosh va shamol salohiyatini o'rganish"},
                   {"label": "Loyiha", "value": "", "text": "Investor tanlash va shartnoma"},
                   {"label": "Qurilish", "value": "", "text": "Stansiya va tarmoqni qurish"},
                   {"label": "Ishga tushirish", "value": "", "text": "Energiyani tarmoqqa uzatish"}]},
        {"title": "Tarix", "bullets": ["Vaqt chizig'i"], "layout": "timeline",
         "items": [{"label": "2019", "value": "", "text": "Qayta tiklanadigan energiya qonuni"},
                   {"label": "2021", "value": "", "text": "Birinchi yirik quyosh stansiyasi"},
                   {"label": "2023", "value": "", "text": "Shamol stansiyalari qurilishi"},
                   {"label": "2030", "value": "", "text": "Maqsad: 40 % yashil energiya"}]},
        {"title": "Xulosa", "bullets": ["Birinchi xulosa", "Ikkinchi xulosa", LONG]},
    ],
    "closing": "E'tiboringiz uchun rahmat!",
}
for s in CONTENT["slides"]:
    s.setdefault("image_query", "")
    s.setdefault("chart", None)
    s.setdefault("layout", None)
    s.setdefault("items", None)

# Shablon ichida qolgan begona yozuvlar (boshqa xizmat brendi, havola) — litsenziya tekshiruvi uchun belgi
SUSPICIOUS = re.compile(r"(@\w{3,}|t\.me/|https?://|www\.|\bbot\b|slaydtop|slide\.uz|telegram)", re.I)


def sample_image() -> bytes:
    im = Image.new("RGB", (1200, 800), (90, 140, 120))
    d = ImageDraw.Draw(im)
    d.polygon([(0, 800), (450, 300), (800, 800)], fill=(60, 100, 90))
    d.ellipse((850, 120, 1010, 280), fill=(245, 200, 90))
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


def template_texts(path: Path) -> list[str]:
    """Shablon faylining o'zidagi (slayd, maket, master) begona ko'rinadigan yozuvlar."""
    found = set()
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not (name.endswith(".xml") and name.startswith("ppt/")):
                continue
            xml = z.read(name).decode("utf-8", "ignore")
            for text in re.findall(r"<a:t>([^<]+)</a:t>", xml):
                if SUSPICIOUS.search(text):
                    found.add(text.strip()[:60])
            for link in re.findall(r'Target="(https?://[^"]+)"', xml):
                if "schemas." not in link and "purl.org" not in link and "w3.org" not in link:
                    found.add(link[:60])
    return sorted(found)


def theme_fonts(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        fonts = set()
        for name in z.namelist():
            if name.startswith("ppt/theme/") and name.endswith(".xml"):
                xml = z.read(name).decode("utf-8", "ignore")
                for tag in ("majorFont", "minorFont"):
                    m = re.search(rf"<a:{tag}><a:latin typeface=\"([^\"]+)\"", xml)
                    if m:
                        fonts.add(m.group(1))
    return sorted(fonts)


SMALL_TEXT = 0.03  # so'z qutisi sahifaning 3 % idan past (~11 pt shrift) — zalda o'qish qiyin


def text_problems(pdf: Path) -> tuple[list[str], list[int]]:
    """(slayddan tashqariga chiqqan so'zlar, matni juda mayda bo'lib qolgan slaydlar)."""
    html = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"], capture_output=True, text=True).stdout
    out, small = [], {}
    page_no, w, h = 0, 0.0, 0.0
    for line in html.splitlines():
        if m := re.search(r'<page width="([\d.]+)" height="([\d.]+)"', line):
            page_no += 1
            w, h = float(m.group(1)), float(m.group(2))
        elif m := re.search(r'xMin="([-\d.]+)" yMin="([-\d.]+)" xMax="([-\d.]+)" yMax="([-\d.]+)">([^<]*)<', line):
            x0, y0, x1, y1 = map(float, m.groups()[:4])
            if x0 < -1 or y0 < -1 or x1 > w + 1 or y1 > h + 1:
                out.append(f"{page_no}-slayd: «{m.group(5)}»")
            if y1 - y0 < h * SMALL_TEXT:
                small[page_no] = small.get(page_no, 0) + 1
    # Diagramma va infografika izohlari kichik bo'lishi tabiiy — faqat ko'p mayda so'zli slaydlar
    return out, sorted(p for p, n in small.items() if n >= 25)


def contact_sheet(files: list[Path], target: Path) -> None:
    thumbs = [Image.open(f).convert("RGB") for f in files]
    if not thumbs:
        return
    tw = 320
    th = int(thumbs[0].height * tw / thumbs[0].width)
    cols = 5
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 8) + 8, rows * (th + 8) + 8), (235, 237, 232))
    for i, im in enumerate(thumbs):
        sheet.paste(im.resize((tw, th)), (8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + 8)))
    sheet.save(target, "JPEG", quality=80)


async def check(tpl, img: bytes) -> dict:
    work = OUT / "work" / tpl.id
    work.mkdir(parents=True, exist_ok=True)
    row = {"id": tpl.id, "category": tpl.category, "ok": False, "slides": 0, "overflow": [], "small": [],
           "suspicious": template_texts(tpl.path), "fonts": theme_fonts(tpl.path)}
    pics = [img if i in (0, 1, 6) else None for i in range(len(CONTENT["slides"]))]
    pptx = work / f"qa_{tpl.id}.pptx"
    try:
        pptx_builder.build(tpl.path, pptx, "uz", OUTLINE, CONTENT, pics)
    except Exception as e:  # noqa: BLE001 — hisobotga yoziladi
        row["error"] = f"yig'ilmadi: {e}"
        return row
    files = await preview.render(pptx, work / "render", dpi=40)
    row["slides"] = len(files)
    expected = len(CONTENT["slides"]) + 3  # muqova + reja + yakun
    if not files:
        row["error"] = "LibreOffice ochmadi"
        return row
    row["overflow"], row["small"] = text_problems(work / "render" / "deck.pdf")
    row["ok"] = len(files) == expected and not row["overflow"]
    if len(files) != expected:
        row["error"] = f"slaydlar soni {len(files)}, kutilgan {expected}"
    contact_sheet(files, OUT / f"{tpl.id}.jpg")
    return row


def report(rows: list[dict]) -> str:
    lines = ["# Shablonlar sifat nazorati", "",
             "Avtomatik tekshiruv: yig'ilish, slaydlar soni, slayddan chiqqan matn, shablondagi begona yozuvlar.",
             "Ko'z bilan tekshirish uchun har shablonning barcha slaydlari: `data/qa/<id>.jpg`.", "",
             "| № | Turkum | Holat | Chiqib ketgan matn | Mayda matnli slaydlar | Begona yozuv (litsenziya) | Shriftlar |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        state = "✅" if r["ok"] else "⚠️ " + r.get("error", "matn chiqib ketgan")
        over = "; ".join(r["overflow"][:3]) + (f" (+{len(r['overflow']) - 3})" if len(r["overflow"]) > 3 else "")
        small = ", ".join(map(str, r["small"])) or "—"
        lines.append(f"| {r['id']} | {r['category']} | {state} | {over or '—'} | {small} | "
                     f"{'; '.join(r['suspicious'][:3]) or '—'} | {', '.join(r['fonts']) or '—'} |")
    ok = sum(r["ok"] for r in rows)
    flagged = sum(bool(r["suspicious"]) for r in rows)
    lines += ["", f"Jami: {len(rows)}, texnik jihatdan toza: {ok}, begona yozuvli: {flagged}."]
    return "\n".join(lines) + "\n"


async def main(ids: list[str]) -> None:
    if not preview.available():
        sys.exit("LibreOffice (soffice) va pdftoppm kerak")
    OUT.mkdir(parents=True, exist_ok=True)
    img = sample_image()
    tpls = [t for t in templates.all_templates() if not ids or t.id in ids]
    tpls.sort(key=lambda t: t.id)
    rows = []
    for t in tpls:
        rows.append(await check(t, img))
        r = rows[-1]
        print(t.id, "OK" if r["ok"] else r.get("error", "overflow"), len(r["overflow"]), r["suspicious"][:2], flush=True)
    (OUT / "report.md").write_text(report(rows), encoding="utf-8")
    print("Hisobot:", OUT / "report.md")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))

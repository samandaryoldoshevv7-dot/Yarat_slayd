"""Bot ham, sayt ham ishlatadigan umumiy generatsiya jarayoni.

Har bir taqdimot "loyiha" sifatida saqlanadi (data/output/order_<id>/): project.json — matn, reja,
diagrammalar, shablon, shriftlar; img_<n>.jpg — rasmlar. Shu tufayli saytda keyin tahrirlab,
faylni qayta yig'ish mumkin (AI'ga qayta murojaat qilmasdan, bepul).
"""
import asyncio
import json
import os
import re
from pathlib import Path

from . import ai, config, images, pptx_builder, templates

# Bir vaqtda nechta taqdimot yig'ilishi (server va AI limitlarini himoya qiladi)
_slots = asyncio.Semaphore(int(os.getenv("MAX_PARALLEL", "3")))
MAX_IMAGES = 6


def safe_filename(topic: str) -> str:
    name = re.sub(r"[^\w\s-]", "", topic, flags=re.UNICODE).strip()
    name = re.sub(r"\s+", "_", name)[:60]
    return name or "taqdimot"


def project_dir(order_id: int) -> Path:
    return config.OUTPUT_DIR / f"order_{order_id}"


def load_project(order_id: int) -> dict | None:
    path = project_dir(order_id) / "project.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _image_path(order_id: int, index: int) -> Path:
    return project_dir(order_id) / f"img_{index}.jpg"


def load_images(order_id: int, count: int) -> list[bytes | None]:
    out = []
    for i in range(count):
        p = _image_path(order_id, i)
        out.append(p.read_bytes() if p.exists() else None)
    return out


def save_image(order_id: int, index: int, data: bytes | None) -> None:
    p = _image_path(order_id, index)
    if data is None:
        p.unlink(missing_ok=True)
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def _save_project(order_id: int, project: dict) -> None:
    d = project_dir(order_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "project.json").write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")


def build_project(order_id: int, project: dict) -> Path:
    """Saqlangan loyihadan .pptx yig'adi (sinxron — to_thread ichida chaqiriladi)."""
    tpl = templates.get(project["template"]) or templates.all_templates()[0]
    pics = load_images(order_id, len(project["content"]["slides"]))
    version = int(project.get("version", 1))
    name = safe_filename(project["outline"]["title"])
    out = project_dir(order_id) / (f"{name}.pptx" if version == 1 else f"{name}_v{version}.pptx")
    pptx_builder.build(tpl.path, out, project["lang"], project["outline"], project["content"], pics,
                       project.get("fonts"))
    return out


async def rebuild(order_id: int, project: dict) -> Path:
    """Tahrirlangan loyihani saqlab, faylni qayta yig'adi."""
    project["version"] = int(project.get("version", 1)) + 1
    _save_project(order_id, project)
    return await asyncio.to_thread(build_project, order_id, project)


async def generate(order_id: int, topic: str, lang: str, outline: dict, template_id: str, progress=None,
                   charts: bool = False, fonts: dict | None = None) -> Path:
    """Rejaga ko'ra to'liq matn, diagrammalar, rasmlar va .pptx faylni tayyorlaydi."""
    tpl = templates.get(template_id) or templates.all_templates()[0]

    async def step(text: str):
        if progress:
            await progress(text)

    async with _slots:
        await step("✍️ Matn yozilmoqda...")
        content = await ai.make_content(topic, lang, outline, charts)
        await step("🖼 Rasmlar tanlanmoqda...")
        # Rasm har ikkinchi slaydga (diagrammasi borlariga emas), ko'pi bilan MAX_IMAGES ta
        with_pic = [i for i, s in enumerate(content["slides"]) if i % 2 == 0 and not s.get("chart")][:MAX_IMAGES]
        fetched = await images.fetch_images([content["slides"][i]["image_query"] for i in with_pic])
        for i, img in zip(with_pic, fetched):
            save_image(order_id, i, img)
        await step("🎨 Slaydlar yig'ilmoqda...")
        project = {"topic": topic, "lang": lang, "outline": outline, "content": content,
                   "template": tpl.id, "fonts": fonts or {}, "charts": charts, "version": 1}
        _save_project(order_id, project)
        out = await asyncio.to_thread(build_project, order_id, project)
    return out

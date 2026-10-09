"""Bot ham, sayt ham ishlatadigan umumiy generatsiya jarayoni."""
import asyncio
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


async def generate(order_id: int, topic: str, lang: str, outline: dict, template_id: str, progress=None) -> Path:
    """Rejaga ko'ra to'liq matn, rasmlar va .pptx faylni tayyorlaydi."""
    tpl = templates.get(template_id) or templates.all_templates()[0]

    async def step(text: str):
        if progress:
            await progress(text)

    async with _slots:
        await step("✍️ Matn yozilmoqda...")
        content = await ai.make_content(topic, lang, outline)
        await step("🖼 Rasmlar tanlanmoqda...")
        # Har slaydga rasm emas — o'qish qulay bo'lishi uchun har ikkinchisiga (ko'pi bilan 6 ta)
        with_pic = [i for i in range(len(content["slides"])) if i % 2 == 0][:MAX_IMAGES]
        fetched = await images.fetch_images([content["slides"][i]["image_query"] for i in with_pic])
        pics = [None] * len(content["slides"])
        for i, img in zip(with_pic, fetched):
            pics[i] = img
        await step("🎨 Slaydlar yig'ilmoqda...")
        out = config.OUTPUT_DIR / f"{order_id}_{safe_filename(outline['title'])}.pptx"
        await asyncio.to_thread(pptx_builder.build, tpl.path, out, lang, outline, content, pics)
    return out

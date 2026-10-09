"""Slaydlar uchun rasmlar. Interfeys bitta: fetch_images(queries) -> [bytes | None].

Manbalar (config.IMAGE_PROVIDER):
  pollinations — bepul AI rasm chizish, kalit kerak emas (sekinroq, ~5–20 soniya)
  pexels       — bepul fotobank, PEXELS_API_KEY kerak
  none         — rasmsiz
Rasm olinmasa slayd rasmsiz chiqadi, taqdimot to'xtamaydi.
"""
import asyncio
import logging
import random
from urllib.parse import quote

import aiohttp

from . import config

log = logging.getLogger(__name__)

PEXELS_URL = "https://api.pexels.com/v1/search"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"


async def _pexels(session: aiohttp.ClientSession, query: str) -> bytes | None:
    async with session.get(
        PEXELS_URL,
        params={"query": query, "per_page": 1, "orientation": "landscape"},
        headers={"Authorization": config.PEXELS_API_KEY},
    ) as r:
        if r.status != 200:
            log.warning("Pexels %s: %s", r.status, query)
            return None
        photos = (await r.json()).get("photos") or []
    if not photos:
        return None
    async with session.get(photos[0]["src"]["large"]) as r:
        return await r.read() if r.status == 200 else None


async def _pollinations(session: aiohttp.ClientSession, query: str) -> bytes | None:
    prompt = f"{query}, professional photo, high quality, no text"
    params = {"width": 1024, "height": 768, "nologo": "true", "seed": random.randint(1, 10**6)}
    async with session.get(POLLINATIONS_URL.format(prompt=quote(prompt)), params=params) as r:
        if r.status != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
            log.warning("Pollinations %s: %s", r.status, query)
            return None
        return await r.read()


async def fetch_image(session: aiohttp.ClientSession, query: str) -> bytes | None:
    provider = {"pexels": _pexels, "pollinations": _pollinations}.get(config.IMAGE_PROVIDER)
    if provider is None or not query:
        return None
    try:
        return await provider(session, query)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        log.warning("Rasm yuklanmadi: %s", query)
        return None


async def fetch_images(queries: list[str]) -> list[bytes | None]:
    if config.IMAGE_PROVIDER not in ("pexels", "pollinations"):
        return [None] * len(queries)
    # Bepul AI xizmati bir vaqtda ko'p so'rovni yoqtirmaydi — 2 tadan yuboramiz
    limit = asyncio.Semaphore(2 if config.IMAGE_PROVIDER == "pollinations" else 6)
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def one(q: str):
            async with limit:
                return await fetch_image(session, q)

        return list(await asyncio.gather(*(one(q) for q in queries)))

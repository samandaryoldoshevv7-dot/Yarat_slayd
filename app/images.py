"""Slaydlar uchun rasmlar. Hozircha Pexels (bepul, litsenziyasi tijoratga ruxsat beradi).

Keyingi bosqichda bu yerga AI rasm chizish (masalan FLUX) qo'shiladi — interfeys o'zgarmaydi:
fetch_image(query) -> bytes yoki None.
"""
import asyncio
import logging

import aiohttp

from . import config

log = logging.getLogger(__name__)

PEXELS_URL = "https://api.pexels.com/v1/search"


async def fetch_image(session: aiohttp.ClientSession, query: str) -> bytes | None:
    if not config.PEXELS_API_KEY or not query:
        return None
    try:
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
    except (aiohttp.ClientError, asyncio.TimeoutError):
        log.warning("Rasm yuklanmadi: %s", query)
        return None


async def fetch_images(queries: list[str]) -> list[bytes | None]:
    if not config.PEXELS_API_KEY:
        return [None] * len(queries)
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        return await asyncio.gather(*(fetch_image(session, q) for q in queries))

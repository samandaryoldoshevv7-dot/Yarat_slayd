"""Saytdan Telegram'ga xabar yuborish (bot ishga tushganda `bot` o'rnatiladi)."""
import logging
from pathlib import Path

log = logging.getLogger(__name__)
bot = None  # aiogram.Bot


async def send_file(user_id: int, path: Path, caption: str) -> None:
    if bot is None:
        return
    from aiogram.types import FSInputFile

    try:
        await bot.send_document(user_id, FSInputFile(path), caption=caption)
    except Exception:
        log.warning("Faylni Telegram'ga yuborib bo'lmadi: %s", user_id)


async def send_message(user_id: int, text: str) -> None:
    if bot is None:
        return
    try:
        await bot.send_message(user_id, text)
    except Exception:
        log.warning("Xabarni Telegram'ga yuborib bo'lmadi: %s", user_id)

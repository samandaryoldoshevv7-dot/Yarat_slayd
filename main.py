"""Bot va saytni bitta jarayonda ishga tushiradi (Railway uchun). Ishga tushirish: python main.py"""
import asyncio
import logging

import uvicorn

import bot
from app import config
from app.web import app

log = logging.getLogger("main")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bot.log_setup_warnings()
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=config.PORT, proxy_headers=True,
                                           forwarded_allow_ips="*", log_level="info"))
    tasks = [server.serve()]
    if config.BOT_TOKEN:
        tasks.append(bot.run())
    else:
        log.warning("BOT_TOKEN yo'q — faqat sayt ishlaydi (Telegram orqali kirish o'chiq).")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())

"""Bot va saytni bitta jarayonda ishga tushiradi (Railway uchun). Ishga tushirish: python main.py"""
import asyncio
import html
import logging

import uvicorn

import bot
from app import config, notify, service
from app.web import app

log = logging.getLogger("main")


async def _notify_recovered(recovered: list[dict]):
    """Server qayta ishga tushganda to'xtab qolgan buyurtma egalariga xabar."""
    for _ in range(30):
        if notify.bot:
            break
        await asyncio.sleep(1)
    for r in recovered:
        await notify.send_message(
            r["user_id"],
            f"⚠️ «{html.escape(r['topic'])}» taqdimoti server qayta ishga tushgani sababli tayyorlanmadi.\n"
            f"{r['amount']:,} so'm balansingizga qaytarildi. Qaytadan yaratishingiz mumkin.".replace(",", " "),
        )


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bot.log_setup_warnings()
    recovered = service.recover_stuck_orders()
    for r in recovered:
        log.warning("Tugallanmagan buyurtma %s yopildi, %s so'm qaytarildi (user %s)",
                    r["order_id"], r["amount"], r["user_id"])
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=config.PORT, proxy_headers=True,
                                           forwarded_allow_ips="*", log_level="info"))
    tasks = [server.serve()]
    if config.BOT_TOKEN:
        tasks.append(bot.run())
        if recovered:
            tasks.append(_notify_recovered(recovered))
    else:
        log.warning("BOT_TOKEN yo'q — faqat sayt ishlaydi (Telegram orqali kirish o'chiq).")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())

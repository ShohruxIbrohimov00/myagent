"""
Shohrux AI agent — bosh fayl (orkestrator).

Hamma bo'lakni bir event loopda ulaydi:
  manba (Telethon)  →  AI processor  →  admin bot (tasdiq)  →  kanal

Ishga tushirish:
    python main.py
"""
import asyncio
import logging

import bot as admin_bot
import config
import database as db
import processor
from source_reader import SourceReader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


async def handle_new_post(post: dict) -> None:
    """Manbadan kelgan har bir yangi post shu yerdan o'tadi."""
    channel, mid = post["channel"], post["message_id"]

    # Bu xabarni avval ko'rganmizmi? (takror ishlamaslik uchun)
    if await db.is_seen(channel, mid):
        return
    await db.mark_seen(channel, mid)

    try:
        result = await processor.process(post)
    except Exception:
        log.exception("Processor xatosi")
        return

    if result:
        log.info("Tayyor post -> adminga tasdiqqa: %s", result.get("topic"))
        await admin_bot.send_for_approval(result)


async def main() -> None:
    config.validate()
    await db.init()

    reader = SourceReader(on_post=handle_new_post)
    await reader.start()

    log.info("Shohrux ishga tushdi. Admin bot va manba kuzatuvi faol.")
    await admin_bot.notify_admin("🚀 Shohrux ishga tushdi va kanallarni kuzatyapti.")

    # Bot polling va Telethon kuzatuvini parallel ishlatamiz
    await asyncio.gather(
        admin_bot.dp.start_polling(admin_bot.bot),
        reader.run_until_disconnected(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("To'xtatildi.")

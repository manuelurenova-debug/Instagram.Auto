import asyncio
import logging

from config import TELEGRAM_CHAT_ID
from utils import setup_logging
from bot import build_bot
from scheduler import build_scheduler, set_notifier


async def main() -> None:
    setup_logging()
    logging.info("Arrancando Instagram Auto...")

    app = build_bot()
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    async def notify(text: str) -> None:
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="Markdown",
        )

    set_notifier(notify)

    scheduler = build_scheduler()
    scheduler.start()
    logging.info("✅ Bot + scheduler arrancados. Revisando publicaciones cada minuto.")

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Apagando...")

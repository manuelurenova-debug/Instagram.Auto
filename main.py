import asyncio
import logging

from config import TELEGRAM_TOKEN  # noqa: F401 — valida .env al importar
from utils import setup_logging
from bot import build_bot

async def main() -> None:
    setup_logging()
    logging.info("Arrancando Instagram Auto...")
    application = build_bot()
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logging.info("✅ Bot arrancado. Esperando mensajes...")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Apagando...")

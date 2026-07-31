import asyncio
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Awaitable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import IG_ACCOUNTS
from database import obtener_pendientes_listos, reclamar_publicacion, marcar_publicado, marcar_error
from publisher import publish_video_full, PublishError

logger = logging.getLogger(__name__)

_telegram_notifier: Optional[Callable[[str], Awaitable[None]]] = None


def set_notifier(notifier_func: Callable[[str], Awaitable[None]]) -> None:
    global _telegram_notifier
    _telegram_notifier = notifier_func


async def _notify(text: str) -> None:
    if _telegram_notifier:
        try:
            await _telegram_notifier(text)
        except Exception as e:
            logger.warning("Error enviando notificación Telegram: %s", e)


async def _process_publication(pub: dict) -> None:
    pub_id = pub["id"]
    cuenta = pub["cuenta"]

    # Claim atómico (pendiente -> procesando): si otro proceso ya la cogió
    # primero (p.ej. dos contenedores solapados durante un redeploy de
    # Railway), esto devuelve False y no publicamos por duplicado.
    reclamada = await asyncio.to_thread(reclamar_publicacion, pub_id)
    if not reclamada:
        logger.info("[scheduler] %s ya reclamada por otro proceso, se omite.", pub_id[:8])
        return

    video_url = pub.get("video_url")

    if not video_url:
        msg = "video_url no encontrada — publicación creada antes de subir a Storage al editar"
        logger.error("[scheduler] %s: %s", pub_id[:8], msg)
        await asyncio.to_thread(marcar_error, pub_id, msg)
        await _notify(
            f"❌ Error en `{cuenta}`: publicación antigua sin video en Storage. "
            f"Cancélala y vuelve a programarla con /add."
        )
        return

    archivo_local = pub.get("archivo_local")
    file_name = Path(archivo_local).name if archivo_local else video_url.split("/")[-1].split("?")[0]

    try:
        logger.info("[scheduler] Publicando %s en %s...", pub_id[:8], cuenta)
        # publish_video_full es síncrono (requests + time.sleep) → ejecutar en thread
        media_id = await asyncio.to_thread(publish_video_full, video_url, file_name, cuenta)
        await asyncio.to_thread(marcar_publicado, pub_id, media_id)
        hora = datetime.now().strftime("%H:%M")
        await _notify(f"✅ Publicado en `{cuenta}` a las {hora}")

    except PublishError as e:
        logger.error("[scheduler] PublishError en %s: %s", pub_id[:8], e)
        await asyncio.to_thread(marcar_error, pub_id, str(e))
        await _notify(f"❌ Error publicando en `{cuenta}`:\n{str(e)[:300]}")

    except Exception as e:
        logger.exception("[scheduler] Error inesperado en publicación %s", pub_id[:8])
        await asyncio.to_thread(marcar_error, pub_id, str(e))
        await _notify(f"❌ Error inesperado en `{cuenta}`: {e}")


async def check_and_publish() -> None:
    """Revisa publicaciones pendientes cuya hora ya llegó y las publica."""
    try:
        pendientes = await asyncio.to_thread(obtener_pendientes_listos)
    except Exception as e:
        logger.error("[scheduler] Error consultando pendientes: %s", e)
        return

    if not pendientes:
        return

    logger.info("[scheduler] %d publicación(es) lista(s) para procesar.", len(pendientes))
    for pub in pendientes:
        await _process_publication(pub)


async def check_token_expiration() -> None:
    """Avisa por Telegram si algún token de Instagram está a 7 días o menos de caducar."""
    hoy = date.today()
    for cuenta, data in IG_ACCOUNTS.items():
        expires = data.get("expires")
        if not expires or expires.year == 2099:
            continue
        dias = (expires - hoy).days
        if dias < 0:
            await _notify(
                f"❌ Token de `{cuenta}` YA CADUCÓ hace {abs(dias)} día(s). "
                f"Renuévalo urgente en developers.facebook.com."
            )
        elif dias <= 7:
            await _notify(
                f"⚠️ Token de `{cuenta}` caduca en {dias} día(s) ({expires}). "
                f"Renuévalo en developers.facebook.com."
            )


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Madrid")
    scheduler.add_job(
        check_and_publish,
        trigger="interval",
        minutes=1,
        id="check_publications",
        max_instances=1,  # evitar solapamiento si una publicación tarda >1 min
    )
    scheduler.add_job(
        check_token_expiration,
        trigger="cron",
        hour=10,
        minute=0,
        id="check_tokens",
    )
    return scheduler

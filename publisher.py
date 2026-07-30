import logging
import time
from pathlib import Path

import requests

from config import IG_ACCOUNTS
from storage import upload_video, delete_video, StorageError

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.instagram.com/v19.0"

# El video siempre entra con un fade de 0.3s desde negro (editor.py) — la
# miniatura de portada saldría negra si se coge el primer frame. Se fija
# justo después del fade para evitarlo.
THUMB_OFFSET_MS = 800


class PublishError(Exception):
    pass


def _create_container(ig_user_id: str, access_token: str, video_url: str, caption: str) -> str:
    url = f"{GRAPH_API_BASE}/{ig_user_id}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "thumb_offset": THUMB_OFFSET_MS,
        "access_token": access_token,
    }
    try:
        r = requests.post(url, params=params, timeout=60)
    except requests.RequestException as e:
        raise PublishError(f"Error de red creando container: {e}") from e

    if r.status_code != 200:
        raise PublishError(f"Error creando container ({r.status_code}): {r.text[:300]}")

    data = r.json()
    if "id" not in data:
        raise PublishError(f"Respuesta inesperada al crear container: {data}")

    logger.info("Container creado: %s", data["id"])
    return data["id"]


def _wait_for_container_ready(container_id: str, access_token: str, max_wait: int = 180) -> None:
    """Espera hasta que la Graph API procese el Reel (suele tardar 30-90s)."""
    url = f"{GRAPH_API_BASE}/{container_id}"
    params = {"fields": "status_code,status", "access_token": access_token}
    start = time.time()

    while time.time() - start < max_wait:
        try:
            r = requests.get(url, params=params, timeout=30)
        except requests.RequestException as e:
            raise PublishError(f"Error de red checkeando estado: {e}") from e

        if r.status_code != 200:
            raise PublishError(f"Error checkeando estado del container: {r.text[:300]}")

        data = r.json()
        status = data.get("status_code")
        logger.info("Container %s estado: %s", container_id, status)

        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise PublishError(f"Container falló con estado '{status}': {data}")

        time.sleep(5)

    raise PublishError(f"Timeout esperando container {container_id} ({max_wait}s).")


def _publish_container(ig_user_id: str, access_token: str, container_id: str) -> str:
    url = f"{GRAPH_API_BASE}/{ig_user_id}/media_publish"
    params = {"creation_id": container_id, "access_token": access_token}
    try:
        r = requests.post(url, params=params, timeout=60)
    except requests.RequestException as e:
        raise PublishError(f"Error de red publicando: {e}") from e

    if r.status_code != 200:
        raise PublishError(f"Error publicando container ({r.status_code}): {r.text[:300]}")

    data = r.json()
    if "id" not in data:
        raise PublishError(f"Respuesta inesperada al publicar: {data}")

    logger.info("Reel publicado: ig_media_id=%s", data["id"])
    return data["id"]


def publish_reel(video_public_url: str, cuenta: str) -> str:
    """Crea container → espera → publica. Devuelve el ig_media_id."""
    account = IG_ACCOUNTS[cuenta]
    ig_user_id = account["id"]
    access_token = account["token"]
    caption = account.get("caption", "")

    container_id = _create_container(ig_user_id, access_token, video_public_url, caption)
    _wait_for_container_ready(container_id, access_token)
    return _publish_container(ig_user_id, access_token, container_id)


def publish_video_full(local_path: Path, cuenta: str) -> str:
    """
    Orquesta el flujo completo:
      1. Sube video a Supabase Storage (URL pública temporal)
      2. Publica como Reel vía Graph API
      3. Borra del Storage (liberar 1GB free) — siempre, haya o no error

    Devuelve el ig_media_id.
    """
    file_name = local_path.name
    public_url = None

    try:
        logger.info("[publisher] Subiendo %s a Storage...", file_name)
        public_url = upload_video(local_path)

        logger.info("[publisher] Publicando como Reel en %s...", cuenta)
        media_id = publish_reel(public_url, cuenta)
        logger.info("[publisher] ✅ ig_media_id=%s", media_id)
        return media_id

    except StorageError as e:
        raise PublishError(str(e)) from e

    finally:
        # Borrar del bucket SIEMPRE para no acumular en el 1GB free
        if public_url is not None:
            delete_video(file_name)

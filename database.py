import logging
from datetime import datetime, timezone
from typing import Optional

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


class DatabaseError(Exception):
    pass


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def insertar_publicacion(
    url_original: str,
    archivo_local: str,
    cuenta: str,
    hora_programada: datetime,
    video_url: str | None = None,
) -> str:
    try:
        response = (
            get_client()
            .table("publicaciones")
            .insert({
                "url_original": url_original,
                "archivo_local": archivo_local,
                "video_url": video_url,
                "cuenta": cuenta,
                "hora_programada": hora_programada.isoformat(),
                "estado": "pendiente",
            })
            .execute()
        )
        pub_id: str = response.data[0]["id"]
        logger.info("Publicación registrada: id=%s cuenta=%s hora=%s", pub_id[:8], cuenta, hora_programada)
        return pub_id
    except Exception as e:
        logger.error("Error insertando publicación: %s", e)
        raise DatabaseError(f"Error guardando en base de datos: {e}") from e


def actualizar_video_url(pub_id: str, video_url: str) -> None:
    """Enlaza la video_url tras subir a Storage. Se inserta la fila antes de
    subir para que un fallo/caída a mitad de camino deje un registro visible
    y gestionable (/programados, /cancelar) en vez de un archivo huérfano
    e invisible en Storage."""
    try:
        get_client().table("publicaciones").update(
            {"video_url": video_url}
        ).eq("id", pub_id).execute()
        logger.info("video_url enlazada: id=%s", pub_id[:8])
    except Exception as e:
        logger.error("Error actualizando video_url id=%s: %s", pub_id[:8], e)
        raise DatabaseError(f"Error actualizando video_url: {e}") from e


def reclamar_publicacion(pub_id: str) -> bool:
    """Marca pendiente -> procesando de forma atómica (UPDATE...WHERE con guarda
    de estado). Si devuelve False, otro proceso ya la reclamó primero — evita
    publicar dos veces lo mismo si hay un solape de contenedores en un
    redeploy de Railway."""
    try:
        response = (
            get_client()
            .table("publicaciones")
            .update({"estado": "procesando"})
            .eq("id", pub_id)
            .eq("estado", "pendiente")
            .execute()
        )
        return len(response.data) > 0
    except Exception as e:
        logger.error("Error reclamando publicación id=%s: %s", pub_id[:8], e)
        raise DatabaseError(f"Error reclamando publicación: {e}") from e


def obtener_pendientes_listos() -> list[dict]:
    try:
        now = datetime.now(timezone.utc).isoformat()
        response = (
            get_client()
            .table("publicaciones")
            .select("*")
            .eq("estado", "pendiente")
            .lte("hora_programada", now)
            .order("hora_programada", desc=False)
            .limit(5)
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error("Error obteniendo pendientes listos: %s", e)
        raise DatabaseError(f"Error consultando pendientes: {e}") from e


def obtener_programados() -> list[dict]:
    try:
        response = (
            get_client()
            .table("publicaciones")
            .select("id, cuenta, hora_programada, archivo_local, video_url")
            .eq("estado", "pendiente")
            .order("hora_programada", desc=False)
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error("Error obteniendo programados: %s", e)
        raise DatabaseError(f"Error consultando programados: {e}") from e


def obtener_historial(n: int = 10) -> list[dict]:
    try:
        response = (
            get_client()
            .table("publicaciones")
            .select("id, cuenta, published_at, ig_media_id")
            .eq("estado", "publicado")
            .order("published_at", desc=True)
            .limit(n)
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error("Error obteniendo historial: %s", e)
        raise DatabaseError(f"Error consultando historial: {e}") from e


def obtener_historial_dashboard(n: int = 30) -> list[dict]:
    """Publicados + errores, con archivo_local/video_url para preview/miniatura. Solo para el dashboard local."""
    try:
        response = (
            get_client()
            .table("publicaciones")
            .select("id, cuenta, archivo_local, video_url, estado, published_at, error_msg, created_at")
            .in_("estado", ["publicado", "error"])
            .order("created_at", desc=True)
            .limit(n)
            .execute()
        )
        return response.data
    except Exception as e:
        logger.error("Error obteniendo historial del dashboard: %s", e)
        raise DatabaseError(f"Error consultando historial: {e}") from e


def marcar_publicado(pub_id: str, ig_media_id: str) -> None:
    try:
        get_client().table("publicaciones").update({
            "estado": "publicado",
            "ig_media_id": ig_media_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", pub_id).execute()
        logger.info("Marcada como publicada: id=%s ig_media_id=%s", pub_id[:8], ig_media_id)
    except Exception as e:
        logger.error("Error marcando publicado id=%s: %s", pub_id[:8], e)
        raise DatabaseError(f"Error actualizando estado publicado: {e}") from e


def marcar_error(pub_id: str, error_msg: str) -> None:
    try:
        get_client().table("publicaciones").update({
            "estado": "error",
            "error_msg": error_msg[:500],
        }).eq("id", pub_id).execute()
        logger.error("Publicación con error: id=%s msg=%s", pub_id[:8], error_msg[:100])
    except Exception as e:
        logger.error("Error marcando error en DB id=%s: %s", pub_id[:8], e)
        raise DatabaseError(f"Error actualizando estado error: {e}") from e


def cancelar_publicacion(id_corto: str) -> dict | None:
    """Devuelve el registro cancelado (con archivo_local/video_url, para poder
    borrarlo también de Storage) o None si no se encontró ninguna pendiente."""
    try:
        # Traer solo las pendientes y filtrar por prefijo en Python (la tabla es pequeña)
        response = (
            get_client()
            .table("publicaciones")
            .select("id, estado, archivo_local, video_url")
            .eq("estado", "pendiente")
            .execute()
        )
        match = next((r for r in response.data if r["id"].startswith(id_corto)), None)
        if not match:
            return None

        get_client().table("publicaciones").update(
            {"estado": "cancelado"}
        ).eq("id", match["id"]).execute()
        logger.info("Publicación cancelada: id=%s", match["id"][:8])
        return match
    except Exception as e:
        logger.error("Error cancelando publicación id_corto=%s: %s", id_corto, e)
        raise DatabaseError(f"Error cancelando publicación: {e}") from e

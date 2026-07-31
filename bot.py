import asyncio
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import TELEGRAM_TOKEN, VALID_ACCOUNTS, BASE_DIR
from utils import is_valid_instagram_url, parse_time, parse_date_time, only_owner
from downloader import download_video, DownloadError
from editor import edit_video, EditorError
from storage import upload_video, delete_video, StorageError
from database import (
    insertar_publicacion,
    actualizar_video_url,
    obtener_programados,
    obtener_historial,
    cancelar_publicacion,
    marcar_error,
    DatabaseError,
)

logger = logging.getLogger(__name__)
MADRID_TZ = ZoneInfo("Europe/Madrid")


def _fmt_hora(iso_str: str) -> str:
    """Convierte ISO UTC de Supabase a hora Madrid formateada."""
    return datetime.fromisoformat(iso_str).astimezone(MADRID_TZ).strftime("%d/%m/%Y %H:%M")


@only_owner
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []

    if len(args) not in (3, 4):
        await update.message.reply_text(
            "❌ Uso correcto:\n"
            "/add <URL> <cuenta_1|cuenta_2|cuenta_3> <HH:MM>\n"
            "/add <URL> <cuenta_1|cuenta_2|cuenta_3> <YYYY-MM-DD> <HH:MM>\n\n"
            "Ejemplos:\n"
            "/add https://instagram.com/reel/ABC123/ cuenta_2 14:30\n"
            "/add https://instagram.com/reel/ABC123/ cuenta_2 2026-08-15 14:30"
        )
        return

    if len(args) == 3:
        url, cuenta, hora_str = args
        fecha_str = None
    else:
        url, cuenta, fecha_str, hora_str = args

    if not is_valid_instagram_url(url):
        await update.message.reply_text("❌ URL de Instagram inválida.")
        return

    if cuenta not in VALID_ACCOUNTS:
        await update.message.reply_text(
            f"❌ Cuenta no válida. Usa: {', '.join(VALID_ACCOUNTS)}."
        )
        return

    try:
        hora_dt = parse_date_time(fecha_str, hora_str) if fecha_str else parse_time(hora_str)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
        return

    logger.info("Comando /add recibido: url=%s cuenta=%s hora=%s", url, cuenta, hora_dt)
    msg = await update.message.reply_text("⏳ Descargando video...")

    try:
        video_path = await download_video(url)
        await msg.edit_text("⏳ Editando video (recorte + fade)...")

        edited_path = await edit_video(video_path, cuenta)
        await msg.edit_text("⏳ Guardando en base de datos...")

        archivo_local = str(edited_path.relative_to(BASE_DIR))
        file_name = edited_path.name

        # Se inserta ANTES de subir a Storage: si el proceso muere o falla a
        # partir de aquí, queda un registro visible y gestionable desde
        # Telegram (/programados, /cancelar) en vez de un archivo huérfano
        # e invisible en Storage que nada limpiaría nunca.
        pub_id = await asyncio.to_thread(
            insertar_publicacion, url, archivo_local, cuenta, hora_dt
        )

        await msg.edit_text("⏳ Subiendo a Supabase Storage...")
        try:
            video_url = await asyncio.to_thread(upload_video, edited_path)
        except StorageError as e:
            await asyncio.to_thread(marcar_error, pub_id, f"Fallo al subir a Storage: {e}")
            raise

        await asyncio.to_thread(actualizar_video_url, pub_id, video_url)

        # El disco es efímero en Railway — ya está a salvo en Storage, no hace falta conservarlo.
        try:
            edited_path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning("No se pudo borrar el archivo editado %s: %s", edited_path.name, e)

        await msg.edit_text(
            f"✅ *Programado*\n\n"
            f"📹 Cuenta: `{cuenta}`\n"
            f"⏰ Hora: `{hora_dt.strftime('%d/%m/%Y %H:%M')}`\n"
            f"🆔 ID: `{pub_id[:8]}`\n\n"
            f"_Usa /cancelar {pub_id[:8]} para cancelar._",
            parse_mode="Markdown",
        )

    except DownloadError as e:
        await msg.edit_text(str(e))
        logger.error("DownloadError para %s: %s", url, e)
    except EditorError as e:
        await msg.edit_text(f"❌ Error editando: {e}")
        logger.error("EditorError para %s: %s", url, e)
    except StorageError as e:
        await msg.edit_text(f"❌ Error subiendo a Storage: {e}")
        logger.error("StorageError en /add para %s: %s", url, e)
    except DatabaseError as e:
        await msg.edit_text(f"❌ Error guardando en base de datos: {e}")
        logger.error("DatabaseError en /add para %s: %s", url, e)
    except Exception as e:
        await msg.edit_text(f"❌ Error inesperado: {e}")
        logger.exception("Error inesperado en /add para %s", url)


@only_owner
async def cmd_programados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        pendientes = await asyncio.to_thread(obtener_programados)
    except DatabaseError as e:
        await update.message.reply_text(f"❌ Error consultando DB: {e}")
        return

    if not pendientes:
        await update.message.reply_text("📋 No hay publicaciones programadas.")
        return

    lines = ["📋 *Publicaciones programadas:*\n"]
    for p in pendientes:
        hora = _fmt_hora(p["hora_programada"])
        lines.append(f"`{p['id'][:8]}` — `{p['cuenta']}` — {hora}")
    lines.append("\n_Usa /cancelar \\<ID\\> para cancelar._")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@only_owner
async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        historial = await asyncio.to_thread(obtener_historial, 10)
    except DatabaseError as e:
        await update.message.reply_text(f"❌ Error consultando DB: {e}")
        return

    if not historial:
        await update.message.reply_text("📜 No hay publicaciones en el historial.")
        return

    lines = ["📜 *Últimas publicaciones:*\n"]
    for p in historial:
        hora = _fmt_hora(p["published_at"])
        lines.append(f"✅ `{p['cuenta']}` — {hora}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@only_owner
async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "❌ Uso: `/cancelar <ID>`\n\nEjemplo: `/cancelar a1b2c3d4`",
            parse_mode="Markdown",
        )
        return

    id_corto = context.args[0].strip().lower()
    if len(id_corto) < 4:
        await update.message.reply_text("❌ ID demasiado corto. Usa al menos 4 caracteres.")
        return

    try:
        cancelado = await asyncio.to_thread(cancelar_publicacion, id_corto)
    except DatabaseError as e:
        await update.message.reply_text(f"❌ Error en base de datos: {e}")
        return

    if cancelado:
        video_url = cancelado.get("video_url")
        if video_url:
            archivo_local = cancelado.get("archivo_local")
            file_name = Path(archivo_local).name if archivo_local else video_url.split("/")[-1].split("?")[0]
            await asyncio.to_thread(delete_video, file_name)

        await update.message.reply_text(
            f"🚫 Publicación `{id_corto}` cancelada.", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ No encontré una publicación pendiente con ID `{id_corto}`.",
            parse_mode="Markdown",
        )


@only_owner
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *Instagram Auto \\- Comandos*\n\n"
        "`/add <URL> <cuenta> <HH:MM>`\n"
        "`/add <URL> <cuenta> <YYYY\\-MM\\-DD> <HH:MM>`\n"
        "  Descarga, edita y programa un video\\.\n"
        "  Sin fecha: hoy, o mañana si la hora ya pasó\\.\n"
        "  Con fecha: cualquier día futuro\\.\n"
        "  Cuentas: cuenta\\_1, cuenta\\_2, cuenta\\_3\n\n"
        "`/programados`\n"
        "  Lista videos pendientes de publicar\\.\n\n"
        "`/historial`\n"
        "  Últimos 10 videos publicados\\.\n\n"
        "`/cancelar <ID>`\n"
        "  Cancela una publicación programada\\.\n\n"
        "`/ayuda`\n"
        "  Muestra este mensaje\\.",
        parse_mode="MarkdownV2",
    )


@only_owner
async def msg_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("ℹ️ Usa /ayuda para ver los comandos disponibles.")


def build_bot() -> Application:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("programados", cmd_programados))
    app.add_handler(CommandHandler("historial", cmd_historial))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_desconocido))
    logger.info("Handlers registrados: /add, /programados, /historial, /cancelar, /ayuda")
    return app

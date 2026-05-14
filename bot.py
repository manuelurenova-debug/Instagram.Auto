import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import TELEGRAM_TOKEN, VALID_ACCOUNTS
from utils import is_valid_instagram_url, parse_time, only_owner

logger = logging.getLogger(__name__)

@only_owner
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []

    if len(args) != 3:
        await update.message.reply_text(
            "❌ Uso correcto:\n"
            "/add <URL> <cuenta_1|cuenta_2|cuenta_3> <HH:MM>\n\n"
            "Ejemplo:\n"
            "/add https://instagram.com/reel/ABC123/ cuenta_2 14:30"
        )
        return

    url, cuenta, hora_str = args

    if not is_valid_instagram_url(url):
        await update.message.reply_text("❌ URL de Instagram inválida.")
        return

    if cuenta not in VALID_ACCOUNTS:
        await update.message.reply_text(
            f"❌ Cuenta no válida. Usa: {', '.join(VALID_ACCOUNTS)}."
        )
        return

    try:
        hora_dt = parse_time(hora_str)
    except ValueError:
        await update.message.reply_text("❌ Hora inválida. Formato HH:MM (ej: 14:30).")
        return

    hora_formateada = hora_dt.strftime("%d/%m/%Y a las %H:%M")
    logger.info("Comando /add recibido: url=%s cuenta=%s hora=%s", url, cuenta, hora_dt)

    await update.message.reply_text(
        f"✅ Comando recibido:\n"
        f"📹 URL: {url}\n"
        f"📅 Cuenta: {cuenta}\n"
        f"⏰ Hora: {hora_formateada}\n\n"
        f"⚠️ Descarga, edición y programación no implementadas todavía (Fase 1)."
    )

@only_owner
async def cmd_programados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("📋 Función no implementada todavía (Fase 4).")

@only_owner
async def cmd_historial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("📜 Función no implementada todavía (Fase 4).")

@only_owner
async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🚫 Función no implementada todavía (Fase 4).")

@only_owner
async def cmd_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 *Instagram Auto \\- Comandos*\n\n"
        "`/add <URL> <cuenta> <HH:MM>`\n"
        "  Descarga, edita y programa un video\\.\n"
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

"""Telegram Bot handlers and logic for Tana Auto-Tagger."""

from __future__ import annotations
import logging
from typing import Optional, TYPE_CHECKING

# Standard imports - these work at runtime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)

from .config import config
from .session_manager import session_manager
from .date_parser import parse_date_range
from .telegram_models import SessionState

logger = logging.getLogger(__name__)

# Conversation states
SYNC_INPUT = 1
REVIEWING = 2


def is_authorized(user) -> bool:
    """Check if user is in the whitelist by username or user ID."""
    if not config.telegram_enabled:
        return False
    
    allowed = config.telegram_allowed_username
    
    # Check if allowed is a user ID (numeric)
    if allowed.isdigit():
        return str(user.id) == allowed
    
    # Check by username (case insensitive)
    username = user.username
    if not username:
        return False
    
    return username.lower() == allowed.lower()


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    
    if not is_authorized(user):
        await update.message.reply_text(
            "⛔ No tienes permiso para usar este bot.\n"
            f"Tu username: @{user.username or 'desconocido'}"
        )
        return
    
    welcome_text = (
        f"👋 ¡Hola @{user.username}!\n\n"
        "Soy tu asistente de Tana Auto-Tagger.\n\n"
        "📋 *Comandos disponibles:*\n"
        "/sync <fechas> - Sincroniza y clasifica notas\n"
        "  Ejemplos: `hoy`, `ayer`, `últimos 3 días`, `2024-02-01 2024-02-05`\n\n"
        "/status - Ver estado de tu sesión actual\n"
        "/cancel - Cancelar operación en curso\n"
        "/help - Mostrar esta ayuda\n\n"
        "💡 *Tip:* Puedes escribir las fechas en lenguaje natural."
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown"
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await start_handler(update, context)


async def sync_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sync command - start the sync process."""
    user = update.effective_user
    
    if not is_authorized(user):
        await update.message.reply_text("⛔ No tienes permiso.")
        return
    
    # Get date range from command arguments
    args = context.args
    if not args:
        await update.message.reply_text(
            "📅 Por favor especifica un rango de fechas.\n\n"
            "Ejemplos:\n"
            "• `/sync hoy`\n"
            "• `/sync ayer`\n"
            "• `/sync últimos 3 días`\n"
            "• `/sync esta semana`\n"
            "• `/sync 2024-02-01 2024-02-05`"
        )
        return
    
    date_text = " ".join(args)
    date_result = parse_date_range(date_text)
    
    if not date_result.success:
        await update.message.reply_text(
            f"❌ {date_result.error_message}"
        )
        return
    
    # Create new session
    session = session_manager.create_session(user.id, user.username)
    session.date_range = (date_result.start_date, date_result.end_date)
    session.set_state(SessionState.SYNCING)
    
    # Send initial message
    date_str = f"{date_result.start_date} → {date_result.end_date}"
    message = await update.message.reply_text(
        f"⏳ *Procesando...*\n\n"
        f"📅 Rango: {date_str}\n"
        f"🆔 Sesión: `{session.session_id[:8]}...`\n\n"
        "Te aviso cuando termine.",
        parse_mode="Markdown"
    )
    
    # Store message ID for later updates
    session.message_id = message.message_id
    
    # Store session in context for background processing
    context.user_data["session_id"] = session.session_id
    
    logger.info(f"Started sync for user {user.username}, session {session.session_id}")
    
    # Return the session ID for API processing
    return session.session_id


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    user = update.effective_user
    
    if not is_authorized(user):
        await update.message.reply_text("⛔ No tienes permiso.")
        return
    
    session = session_manager.get_user_session(user.id)
    
    if not session:
        await update.message.reply_text(
            "📭 No tienes ninguna sesión activa.\n"
            "Usa /sync para empezar."
        )
        return
    
    # Format session info
    state_emoji = {
        SessionState.IDLE: "⏸️",
        SessionState.SYNCING: "🔄",
        SessionState.CLASSIFYING: "🤖",
        SessionState.REVIEWING: "👀",
        SessionState.APPLYING: "✅",
    }.get(session.state, "❓")
    
    date_range_str = "No definido"
    if session.date_range:
        start, end = session.date_range
        date_range_str = f"{start} → {end}"
    
    text = (
        f"📊 *Estado de tu sesión*\n\n"
        f"{state_emoji} Estado: {session.state.value}\n"
        f"📅 Rango: {date_range_str}\n"
        f"📝 Notas: {len(session.notes)}\n"
        f"☑️ Aprobadas: {len(session.approved)}\n"
        f"🕐 Creada: {session.created_at.strftime('%H:%M:%S')}\n"
        f"⏳ Expira: {session.expires_at.strftime('%H:%M:%S') if session.expires_at else 'N/A'}"
    )
    
    await update.message.reply_text(text, parse_mode="Markdown")


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    user = update.effective_user
    
    if not is_authorized(user):
        await update.message.reply_text("⛔ No tienes permiso.")
        return
    
    session = session_manager.get_user_session(user.id)
    
    if not session:
        await update.message.reply_text("📭 No hay sesión activa para cancelar.")
        return
    
    # Delete session
    session_manager.delete_session(session.session_id)
    
    await update.message.reply_text(
        "❌ Sesión cancelada.\n"
        "Todas las operaciones pendientes se han detenido."
    )


async def unknown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands."""
    await update.message.reply_text(
        "❓ Comando no reconocido.\n"
        "Usa /help para ver los comandos disponibles."
    )


def create_suggestions_keyboard(session, page: int = 0, per_page: int = 5):
    """Create inline keyboard for reviewing suggestions."""
    from .models import TagSuggestion
    
    buttons = []
    
    # Get suggestions for this page
    notes = session.notes[page * per_page:(page + 1) * per_page]
    
    for note in notes:
        note_suggestions = session.suggestions.get(note.id, [])
        top_suggestion = note_suggestions[0] if note_suggestions else None
        
        # Checkbox button
        is_approved = session.is_approved(note.id)
        checkbox = "☑️" if is_approved else "☐"
        
        note_text = note.name[:30] + "..." if len(note.name) > 30 else note.name
        
        if top_suggestion:
            tag_name = top_suggestion.tag.name
            score = int(top_suggestion.score * 100)
            btn_text = f"{checkbox} {note_text} → #{tag_name} ({score}%)"
        else:
            btn_text = f"{checkbox} {note_text} → ?"
        
        buttons.append([InlineKeyboardButton(
            btn_text,
            callback_data=f"toggle:{note.id}"
        )])
    
    # Navigation buttons
    nav_buttons = []
    total_pages = (len(session.notes) + per_page - 1) // per_page
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Anterior", callback_data=f"page:{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Siguiente ▶️", callback_data=f"page:{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Action buttons
    approved_count = session.get_approved_count()
    buttons.append([
        InlineKeyboardButton(
            f"✅ Aplicar {approved_count} seleccionados",
            callback_data="apply"
        ),
        InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
    ])
    
    return InlineKeyboardMarkup(buttons)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks."""
    query = update.callback_query
    user = update.effective_user
    
    if not is_authorized(user):
        await query.answer("⛔ No autorizado")
        return
    
    await query.answer()  # Acknowledge the callback
    
    data = query.data
    session = session_manager.get_user_session(user.id)
    
    if not session:
        await query.edit_message_text("⌛ Sesión expirada. Usa /sync para empezar de nuevo.")
        return
    
    if data == "noop":
        return
    
    if data == "cancel":
        session_manager.delete_session(session.session_id)
        await query.edit_message_text("❌ Operación cancelada.")
        return
    
    if data == "apply":
        await _handle_apply(update, context, session)
        return
    
    if data.startswith("toggle:"):
        note_id = data.split(":", 1)[1]
        await _handle_toggle(update, context, session, note_id)
        return
    
    if data.startswith("page:"):
        page = int(data.split(":", 1)[1])
        await _handle_page_change(update, context, session, page)
        return


async def _handle_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, session, note_id: str):
    """Handle toggle checkbox callback."""
    query = update.callback_query
    
    # Get top suggestion for this note
    suggestions = session.suggestions.get(note_id, [])
    
    if session.is_approved(note_id):
        # Unapprove
        session.unapprove_note(note_id)
    else:
        # Approve with top suggestion
        if suggestions:
            top_tag = suggestions[0].tag
            session.approve_suggestion(note_id, top_tag.id)
    
    # Refresh keyboard
    keyboard = create_suggestions_keyboard(session, page=0)
    
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Could not update keyboard: {e}")


async def _handle_page_change(update: Update, context: ContextTypes.DEFAULT_TYPE, session, page: int):
    """Handle page navigation."""
    query = update.callback_query
    
    keyboard = create_suggestions_keyboard(session, page=page)
    
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Could not update keyboard: {e}")


async def _handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handle apply button."""
    query = update.callback_query
    
    approved_count = len(session.approved)
    
    if approved_count == 0:
        await query.answer("⚠️ No has seleccionado ninguna nota")
        return
    
    session.set_state(SessionState.APPLYING)
    
    await query.edit_message_text(
        f"⏳ Aplicando {approved_count} tags a Tana...\n"
        "Esto puede tomar unos segundos."
    )
    
    # This will be handled by the API
    # Store that we're waiting for apply
    context.user_data["waiting_apply"] = session.session_id


def create_bot_application() -> Optional[Application]:
    """Create and configure the Telegram bot application."""
    if not config.telegram_enabled:
        logger.warning("Telegram bot not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USERNAME.")
        return None
    
    application = Application.builder().token(config.telegram_bot_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("sync", sync_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("cancel", cancel_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Unknown commands
    application.add_handler(CommandHandler("", unknown_handler))
    
    logger.info("Telegram bot application created successfully")
    return application


# Export handlers for use in API
__all__ = [
    'create_bot_application',
    'is_authorized',
    'start_handler',
    'sync_handler',
    'status_handler',
    'cancel_handler',
    'create_suggestions_keyboard',
]

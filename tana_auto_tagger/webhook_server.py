"""Webhook server for Telegram Bot on Render."""

import os
import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from tana_auto_tagger.config import config
from tana_auto_tagger.telegram_bot import (
    start_handler,
    sync_handler,
    status_handler,
    cancel_handler,
    callback_handler,
    is_authorized
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Tana Auto-Tagger Bot")

# Global bot application
bot_app = None


@app.on_event("startup")
async def startup():
    """Initialize bot on startup."""
    global bot_app
    
    logger.info("Starting Telegram Bot with Webhook...")
    
    # Create bot application
    bot_app = Application.builder().token(config.telegram_bot_token).build()
    
    # Add handlers
    bot_app.add_handler(CommandHandler("start", start_handler))
    bot_app.add_handler(CommandHandler("sync", sync_handler))
    bot_app.add_handler(CommandHandler("status", status_handler))
    bot_app.add_handler(CommandHandler("cancel", cancel_handler))
    
    # Initialize bot
    await bot_app.initialize()
    await bot_app.start()
    
    # Set webhook
    webhook_url = config.telegram_webhook_url
    if webhook_url:
        await bot_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        logger.warning("No webhook URL configured!")
    
    logger.info("Bot started successfully!")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    global bot_app
    
    if bot_app:
        await bot_app.stop()
        await bot_app.shutdown()
        logger.info("Bot stopped")


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates."""
    global bot_app
    
    # Parse update
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    
    # Process update
    await bot_app.process_update(update)
    
    return {"status": "ok"}


@app.get("/")
async def root():
    """Health check."""
    return {
        "service": "Tana Auto-Tagger Bot",
        "status": "running",
        "mode": "webhook"
    }


@app.get("/health")
async def health():
    """Health check for Render."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

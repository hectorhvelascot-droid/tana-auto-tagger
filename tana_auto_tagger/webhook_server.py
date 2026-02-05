"""Webhook server for Telegram Bot on Render - Simplified."""

import os
import sys
import logging

# Configure logging first
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("=" * 60)
logger.info("WEBHOOK SERVER STARTING")
logger.info("=" * 60)

# Import FastAPI
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Create app first (before any other imports that might fail)
app = FastAPI(title="Tana Auto-Tagger Bot")

# Global variables
bot_app = None
bot_token = None
allowed_user = None


@app.on_event("startup")
async def startup():
    """Initialize bot on startup."""
    global bot_app, bot_token, allowed_user
    
    logger.info("Loading configuration...")
    
    # Load config from environment
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    allowed_user = os.environ.get("TELEGRAM_ALLOWED_USERNAME", "")
    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
    
    logger.info(f"Token loaded: {bot_token[:20]}..." if bot_token else "ERROR: No token!")
    logger.info(f"Allowed user: {allowed_user}")
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return
    
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
        
        # Import handlers
        from tana_auto_tagger.telegram_bot import (
            start_handler, sync_handler, status_handler, cancel_handler
        )
        
        logger.info("Creating bot application...")
        bot_app = Application.builder().token(bot_token).build()
        
        # Add handlers
        bot_app.add_handler(CommandHandler("start", start_handler))
        bot_app.add_handler(CommandHandler("sync", sync_handler))
        bot_app.add_handler(CommandHandler("status", status_handler))
        bot_app.add_handler(CommandHandler("cancel", cancel_handler))
        
        logger.info("Initializing bot...")
        await bot_app.initialize()
        await bot_app.start()
        
        # Set webhook
        if webhook_url:
            await bot_app.bot.set_webhook(url=webhook_url)
            logger.info(f"✓ Webhook set: {webhook_url}")
        
        logger.info("✓ Bot started successfully!")
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise


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
    
    if not bot_app:
        return JSONResponse(
            status_code=503,
            content={"error": "Bot not initialized"}
        )
    
    try:
        from telegram import Update
        
        # Parse update
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        
        # Process update
        await bot_app.process_update(update)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/")
async def root():
    """Health check."""
    global bot_app
    
    return {
        "service": "Tana Auto-Tagger Bot",
        "status": "running" if bot_app else "initializing",
        "mode": "webhook"
    }


@app.get("/health")
async def health():
    """Health check for Render."""
    global bot_app
    
    if bot_app:
        return {"status": "healthy", "bot_initialized": True}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "initializing", "bot_initialized": False}
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

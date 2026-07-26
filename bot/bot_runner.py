"""Set up and run the Telegram bot (polling)."""
import asyncio
import logging
import database
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler
)
from bot.handlers import (
    cmd_start, cmd_status, cmd_help,
    callback_check_groups, build_buff_conversation
)
from bot.admin_handlers import get_admin_handlers

logger = logging.getLogger(__name__)

_app: Application | None = None


async def _run(token: str):
    global _app
    app = Application.builder().token(token).build()

    # User handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(build_buff_conversation())
    app.add_handler(CallbackQueryHandler(callback_check_groups, pattern="^check_groups$"))

    # Admin handlers (silently ignored for non-admins)
    for h in get_admin_handlers():
        app.add_handler(h)

    _app = app
    await app.initialize()
    await app.start()
    logger.info("Bot polling started.")
    await app.updater.start_polling(drop_pending_updates=True)

    # Block until stopped
    await asyncio.Event().wait()


def run_bot_thread():
    """Called from a daemon thread — runs its own asyncio event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        token = database.get_setting("bot_token", "")
        if not token:
            import time
            logger.info("Bot token not set — waiting 10s...")
            time.sleep(10)
            continue
        try:
            loop.run_until_complete(_run(token))
        except Exception as e:
            logger.error(f"Bot crashed: {e} — restarting in 10s")
            import time
            time.sleep(10)


async def reload_bot():
    """Stop the current bot so the loop restarts with the new token."""
    global _app
    if _app:
        try:
            await _app.updater.stop()
            await _app.stop()
            await _app.shutdown()
        except Exception as e:
            logger.warning(f"reload_bot shutdown error: {e}")
        _app = None

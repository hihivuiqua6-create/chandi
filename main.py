"""Entry point — starts FastAPI admin panel + Telegram bot thread."""
import os
import threading
import logging

import database
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ── Init DB ──────────────────────────────────────────────────────────────────
database.init_db()

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Buff Bot Admin Panel", docs_url=None, redoc_url=None)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from admin.routes import router as admin_router
app.include_router(admin_router)


@app.get("/")
def root():
    return {"status": "ok", "msg": "Buff Bot running. Admin panel at /admin"}


@app.get("/health")
def health():
    stats = database.get_stats()
    return {"status": "ok", **stats}


# ── Telegram Bot thread ────────────────────────────────────────────────────────
def _start_bot_thread():
    from bot.bot_runner import run_bot_thread
    t = threading.Thread(target=run_bot_thread, name="TelegramBot", daemon=True)
    t.start()
    logger.info("Telegram bot thread started.")


@app.on_event("startup")
async def on_startup():
    _start_bot_thread()


# ── Dev entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")

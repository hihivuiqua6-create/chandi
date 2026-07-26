"""FastAPI admin panel routes — cookie-based auth (no SessionMiddleware needed)."""
import hashlib
import os
import logging
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date

import database

logger = logging.getLogger(__name__)

router = APIRouter()

# Absolute path so it works regardless of working directory
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

COOKIE_NAME = "admin_token"


def _make_token(password: str) -> str:
    secret = os.environ.get("SECRET_KEY", "buffbot-secret-change-in-prod")
    return hashlib.sha256(f"{password}:{secret}".encode()).hexdigest()


def _check_auth(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME, "")
    if not token:
        return False
    correct = database.get_setting("admin_password", "admin123")
    return token == _make_token(correct)


def _redir_login(msg: str = "") -> RedirectResponse:
    return RedirectResponse(f"/admin/login?err={msg}", status_code=302)


# ── Auth ─────────────────────────────────────────────────────────────────────

@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request, err: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "err": err})


@router.post("/admin/login")
async def login_post(request: Request, password: str = Form(...)):
    correct = database.get_setting("admin_password", "admin123")
    if password == correct:
        token = _make_token(password)
        resp = RedirectResponse("/admin", status_code=302)
        resp.set_cookie(COOKIE_NAME, token, httponly=True, max_age=86400 * 7, samesite="lax")
        return resp
    return templates.TemplateResponse("login.html", {"request": request, "err": "Sai mật khẩu!"})


@router.get("/admin/logout")
async def logout(request: Request):
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
@router.get("/admin/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _check_auth(request):
        return _redir_login()
    stats = database.get_stats()
    settings = database.get_all_settings()
    logs = database.get_buff_logs(20)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "settings": settings,
        "logs": logs,
        "active": "dashboard",
    })


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/admin/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not _check_auth(request):
        return _redir_login()
    s = database.get_all_settings()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "s": s,
        "msg": request.query_params.get("msg", ""),
        "active": "settings",
    })


@router.post("/admin/settings")
async def settings_save(
    request: Request,
    bot_token: str = Form(""),
    admin_ids: str = Form(""),
    buff_api_url: str = Form(""),
    daily_limit: str = Form("10"),
    admin_password: str = Form(""),
    welcome_message: str = Form(""),
    bot_name: str = Form(""),
):
    if not _check_auth(request):
        return _redir_login()

    old_token = database.get_setting("bot_token", "")
    if bot_token.strip():
        database.set_setting("bot_token", bot_token.strip())
        if bot_token.strip() != old_token:
            try:
                import asyncio
                import bot.bot_runner as bot_runner
                asyncio.create_task(bot_runner.reload_bot())
            except Exception as e:
                logger.warning(f"reload_bot: {e}")

    database.set_setting("admin_ids", admin_ids.strip())
    database.set_setting("buff_api_url", buff_api_url.strip().rstrip("/"))
    try:
        database.set_setting("daily_limit", str(max(1, int(daily_limit or "10"))))
    except Exception:
        pass
    if admin_password.strip():
        database.set_setting("admin_password", admin_password.strip())
    if welcome_message.strip():
        database.set_setting("welcome_message", welcome_message.strip())
    if bot_name.strip():
        database.set_setting("bot_name", bot_name.strip())

    # If password changed, re-sign the cookie
    new_pass = admin_password.strip() if admin_password.strip() else database.get_setting("admin_password", "admin123")
    resp = RedirectResponse("/admin/settings?msg=saved", status_code=302)
    resp.set_cookie(COOKIE_NAME, _make_token(new_pass), httponly=True, max_age=86400 * 7, samesite="lax")
    return resp


# ── Groups ────────────────────────────────────────────────────────────────────

@router.get("/admin/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    if not _check_auth(request):
        return _redir_login()
    groups = database.get_required_groups()
    return templates.TemplateResponse("groups.html", {
        "request": request,
        "groups": groups,
        "msg": request.query_params.get("msg", ""),
        "active": "groups",
    })


@router.post("/admin/groups/add")
async def group_add(
    request: Request,
    group_id: str = Form(...),
    group_title: str = Form(""),
    group_username: str = Form(""),
    group_link: str = Form(""),
):
    if not _check_auth(request):
        return _redir_login()
    database.add_required_group(
        group_id.strip(), group_title.strip(), group_username.strip(), group_link.strip()
    )
    return RedirectResponse("/admin/groups?msg=added", status_code=302)


@router.post("/admin/groups/delete")
async def group_delete(request: Request, db_id: int = Form(...)):
    if not _check_auth(request):
        return _redir_login()
    database.remove_required_group_by_db_id(db_id)
    return RedirectResponse("/admin/groups?msg=deleted", status_code=302)


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/admin/users", response_class=HTMLResponse)
async def users_page(request: Request):
    if not _check_auth(request):
        return _redir_login()
    users = database.get_all_users()
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users,
        "today": date.today().isoformat(),
        "msg": request.query_params.get("msg", ""),
        "active": "users",
    })


@router.post("/admin/users/ban")
async def user_ban(request: Request, user_id: int = Form(...)):
    if not _check_auth(request):
        return _redir_login()
    database.ban_user(user_id)
    return RedirectResponse("/admin/users?msg=banned", status_code=302)


@router.post("/admin/users/unban")
async def user_unban(request: Request, user_id: int = Form(...)):
    if not _check_auth(request):
        return _redir_login()
    database.unban_user(user_id)
    return RedirectResponse("/admin/users?msg=unbanned", status_code=302)


# ── Broadcast ──────────────────────────────────────────────────────────────────

@router.get("/admin/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request):
    if not _check_auth(request):
        return _redir_login()
    history = database.get_broadcasts(20)
    raw_msg = request.query_params.get("msg", "")
    # Parse sent:N:M safely
    sent_ok = sent_fail = 0
    broadcast_sent = False
    if raw_msg.startswith("sent:"):
        parts = raw_msg.split(":")
        broadcast_sent = True
        try:
            sent_ok = int(parts[1])
            sent_fail = int(parts[2])
        except Exception:
            pass
    return templates.TemplateResponse("broadcast.html", {
        "request": request,
        "history": history,
        "raw_msg": raw_msg,
        "broadcast_sent": broadcast_sent,
        "sent_ok": sent_ok,
        "sent_fail": sent_fail,
        "active": "broadcast",
    })


@router.post("/admin/broadcast/send")
async def broadcast_send(request: Request, message: str = Form(...)):
    if not _check_auth(request):
        return _redir_login()
    if not message.strip():
        return RedirectResponse("/admin/broadcast?msg=empty", status_code=302)

    token = database.get_setting("bot_token", "")
    if not token:
        return RedirectResponse("/admin/broadcast?msg=notoken", status_code=302)

    users = database.get_all_users()
    from telegram import Bot
    sent = failed = 0
    bot = Bot(token=token)
    for u in users:
        if u["is_banned"]:
            continue
        try:
            await bot.send_message(
                chat_id=u["user_id"],
                text=f"📢 <b>Thông báo từ Admin:</b>\n\n{message.strip()}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1

    database.add_broadcast(message.strip(), sent, failed)
    return RedirectResponse(f"/admin/broadcast?msg=sent:{sent}:{failed}", status_code=302)


# ── Logs ─────────────────────────────────────────────────────────────────────

@router.get("/admin/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    if not _check_auth(request):
        return _redir_login()
    logs = database.get_buff_logs(200)
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": logs,
        "active": "logs",
    })

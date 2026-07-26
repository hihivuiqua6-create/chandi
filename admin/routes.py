"""FastAPI admin panel routes."""
import os
from fastapi import APIRouter, Request, Form, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import database
import bot.bot_runner as bot_runner

router = APIRouter()
BASE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

_ADMIN_SESSION_KEY = "admin_logged_in"


def _check_auth(request: Request) -> bool:
    return request.session.get(_ADMIN_SESSION_KEY) is True


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
        request.session[_ADMIN_SESSION_KEY] = True
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "err": "Sai mật khẩu!"})


@router.get("/admin/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)


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
        "active": "dashboard"
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
        "active": "settings"
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

    if bot_token:
        old_token = database.get_setting("bot_token", "")
        database.set_setting("bot_token", bot_token.strip())
        if bot_token.strip() != old_token:
            # Restart bot with new token
            try:
                import asyncio
                asyncio.create_task(bot_runner.reload_bot())
            except Exception:
                pass

    if admin_ids is not None:
        database.set_setting("admin_ids", admin_ids.strip())
    if buff_api_url is not None:
        database.set_setting("buff_api_url", buff_api_url.strip().rstrip("/"))
    try:
        database.set_setting("daily_limit", str(max(1, int(daily_limit))))
    except Exception:
        pass
    if admin_password:
        database.set_setting("admin_password", admin_password.strip())
    if welcome_message:
        database.set_setting("welcome_message", welcome_message.strip())
    if bot_name:
        database.set_setting("bot_name", bot_name.strip())

    return RedirectResponse("/admin/settings?msg=saved", status_code=302)


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
        "active": "groups"
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
    database.add_required_group(group_id.strip(), group_title.strip(), group_username.strip(), group_link.strip())
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
        "msg": request.query_params.get("msg", ""),
        "active": "users"
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
    return templates.TemplateResponse("broadcast.html", {
        "request": request,
        "history": history,
        "msg": request.query_params.get("msg", ""),
        "active": "broadcast"
    })


@router.post("/admin/broadcast/send")
async def broadcast_send(request: Request, message: str = Form(...)):
    if not _check_auth(request):
        return _redir_login()
    if not message.strip():
        return RedirectResponse("/admin/broadcast?msg=empty", status_code=302)

    users = database.get_all_users()
    import asyncio
    from telegram import Bot
    token = database.get_setting("bot_token", "")
    if not token:
        return RedirectResponse("/admin/broadcast?msg=notoken", status_code=302)

    sent = 0
    failed = 0
    bot = Bot(token=token)
    for u in users:
        if u["is_banned"]:
            continue
        try:
            await bot.send_message(
                chat_id=u["user_id"],
                text=f"📢 <b>Thông báo từ Admin:</b>\n\n{message.strip()}",
                parse_mode="HTML"
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
        "active": "logs"
    })

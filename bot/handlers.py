"""User-facing Telegram bot handlers."""
import asyncio
import base64
import io
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputFile
)
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
import database
import buff_api

logger = logging.getLogger(__name__)

# Conversation states
WAITING_CAPTCHA = 1
WAITING_SERVICE = 2

# Per-user in-memory session state
_user_sessions: dict[int, dict] = {}


def _is_admin(user_id: int) -> bool:
    return user_id in database.get_admin_ids()


async def _check_groups(bot, user_id: int) -> tuple[bool, list[dict]]:
    """Returns (all_joined, list_of_not_joined_groups)."""
    groups = database.get_required_groups()
    if not groups:
        return True, []
    not_joined = []
    for g in groups:
        try:
            member = await bot.get_chat_member(chat_id=int(g["group_id"]), user_id=user_id)
            if member.status in ("left", "kicked", "banned"):
                not_joined.append(g)
        except Exception:
            not_joined.append(g)
    return len(not_joined) == 0, not_joined


def _join_groups_keyboard(not_joined: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for g in not_joined:
        label = g["group_title"] or g["group_username"] or f"Nhóm {g['group_id']}"
        link = g["group_link"] or (f"https://t.me/{g['group_username'].lstrip('@')}" if g["group_username"] else "#")
        buttons.append([InlineKeyboardButton(f"➕ Tham gia: {label}", url=link)])
    buttons.append([InlineKeyboardButton("✅ Đã tham gia tất cả", callback_data="check_groups")])
    return InlineKeyboardMarkup(buttons)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.upsert_user(user.id, user.username or "", user.first_name or "", user.last_name or "")

    db_user = database.get_user(user.id)
    if db_user and db_user["is_banned"]:
        await update.message.reply_text("🚫 Tài khoản của bạn đã bị cấm sử dụng bot.")
        return ConversationHandler.END

    all_joined, not_joined = await _check_groups(context.bot, user.id)
    if not all_joined:
        await update.message.reply_text(
            f"👋 Xin chào {user.first_name}!\n\n"
            "🔒 Bạn cần tham gia <b>tất cả nhóm bên dưới</b> để sử dụng bot:\n\n"
            + "\n".join(f"• {g['group_title'] or g['group_username'] or g['group_id']}" for g in not_joined)
            + "\n\nSau khi tham gia, nhấn <b>✅ Đã tham gia tất cả</b>",
            parse_mode="HTML",
            reply_markup=_join_groups_keyboard(not_joined)
        )
        return

    welcome = database.get_setting("welcome_message", "Chào mừng {name}! Dùng /buff <link TikTok> để buff.")
    welcome = welcome.replace("{name}", user.first_name or user.username or "bạn")

    limit = int(database.get_setting("daily_limit", "10"))
    remaining = database.get_user_daily_remaining(user.id, limit)

    await update.message.reply_text(
        f"{welcome}\n\n"
        f"📊 Lượt buff hôm nay còn lại: <b>{remaining}/{limit}</b>\n\n"
        f"📌 Lệnh:\n"
        f"• /buff &lt;link TikTok&gt; — Buff video/profile\n"
        f"• /status — Xem lượt buff còn lại\n"
        f"• /help — Hướng dẫn",
        parse_mode="HTML"
    )


async def callback_check_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    database.upsert_user(user.id, user.username or "", user.first_name or "", user.last_name or "")

    all_joined, not_joined = await _check_groups(context.bot, user.id)
    if not all_joined:
        await query.edit_message_text(
            "❌ Bạn chưa tham gia đủ nhóm!\n\n"
            + "\n".join(f"• {g['group_title'] or g['group_id']}" for g in not_joined)
            + "\n\nHãy tham gia và thử lại.",
            reply_markup=_join_groups_keyboard(not_joined)
        )
        return

    welcome = database.get_setting("welcome_message", "Chào mừng {name}!")
    welcome = welcome.replace("{name}", user.first_name or "bạn")
    limit = int(database.get_setting("daily_limit", "10"))
    remaining = database.get_user_daily_remaining(user.id, limit)

    await query.edit_message_text(
        f"✅ Xác nhận tham gia thành công!\n\n"
        f"{welcome}\n\n"
        f"📊 Lượt buff hôm nay còn lại: <b>{remaining}/{limit}</b>\n\n"
        f"Dùng /buff &lt;link TikTok&gt; để bắt đầu!",
        parse_mode="HTML"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.upsert_user(user.id, user.username or "", user.first_name or "")
    limit = int(database.get_setting("daily_limit", "10"))
    remaining = database.get_user_daily_remaining(user.id, limit)
    db_user = database.get_user(user.id)
    total = db_user["total_buffs"] if db_user else 0
    await update.message.reply_text(
        f"📊 <b>Trạng thái buff của bạn</b>\n\n"
        f"• Lượt hôm nay còn lại: <b>{remaining}/{limit}</b>\n"
        f"• Tổng buff đã thực hiện: <b>{total}</b>",
        parse_mode="HTML"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>Hướng dẫn sử dụng Bot Buff TikTok</b>\n\n"
        "1️⃣ Tham gia đủ nhóm yêu cầu\n"
        "2️⃣ Dùng lệnh: /buff &lt;link TikTok&gt;\n"
        "3️⃣ Nhập captcha được gửi từ bot\n"
        "4️⃣ Chọn loại buff (views, likes, followers...)\n"
        "5️⃣ Đợi kết quả!\n\n"
        "⚠️ <b>Lưu ý:</b>\n"
        "• Rời nhóm = bị khóa buff\n"
        "• Mỗi ngày có giới hạn lượt buff\n"
        "• Phải nhập captcha đúng\n\n"
        "📌 <b>Lệnh:</b>\n"
        "/buff &lt;link&gt; — Buff TikTok\n"
        "/status — Xem lượt còn lại\n"
        "/start — Bắt đầu lại",
        parse_mode="HTML"
    )


# ─── Buff Conversation ────────────────────────────────────────────────────────

async def cmd_buff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    database.upsert_user(user.id, user.username or "", user.first_name or "")
    db_user = database.get_user(user.id)

    if db_user and db_user["is_banned"]:
        await update.message.reply_text("🚫 Tài khoản của bạn đã bị cấm.")
        return ConversationHandler.END

    # Check groups
    all_joined, not_joined = await _check_groups(context.bot, user.id)
    if not all_joined:
        await update.message.reply_text(
            "🔒 Bạn cần tham gia đủ nhóm để buff!\n\n"
            + "\n".join(f"• {g['group_title'] or g['group_id']}" for g in not_joined),
            reply_markup=_join_groups_keyboard(not_joined)
        )
        return ConversationHandler.END

    # Check daily limit
    limit = int(database.get_setting("daily_limit", "10"))
    remaining = database.get_user_daily_remaining(user.id, limit)
    if remaining <= 0:
        await update.message.reply_text(
            f"⏰ Bạn đã hết lượt buff hôm nay! ({limit}/{limit})\nQuay lại vào ngày mai nhé."
        )
        return ConversationHandler.END

    # Get URL from args
    args = context.args
    tiktok_url = " ".join(args).strip() if args else ""
    if not tiktok_url or not ("tiktok.com" in tiktok_url or "vm.tiktok" in tiktok_url):
        await update.message.reply_text(
            "❌ Vui lòng cung cấp link TikTok hợp lệ!\n"
            "Ví dụ: /buff https://www.tiktok.com/@user/video/123456"
        )
        return ConversationHandler.END

    # Check buff API configured
    if not database.get_setting("buff_api_url"):
        await update.message.reply_text("⚠️ Buff API chưa được cài đặt. Liên hệ admin!")
        return ConversationHandler.END

    msg = await update.message.reply_text("⏳ Đang lấy captcha, vui lòng chờ...")

    try:
        result = buff_api.start_session()
        session_id = result.get("session_id")
        captcha_b64 = result.get("captcha_b64") or result.get("captcha")
        if not session_id or not captcha_b64:
            await msg.edit_text(f"❌ Lỗi khi lấy captcha: {result.get('message', 'Không rõ')}")
            return ConversationHandler.END

        _user_sessions[user.id] = {
            "session_id": session_id,
            "tiktok_url": tiktok_url,
            "services": [],
        }

        img_data = base64.b64decode(captcha_b64)
        await msg.delete()
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=InputFile(io.BytesIO(img_data), filename="captcha.png"),
            caption=(
                f"🖼 <b>Nhập captcha bên dưới để buff:</b>\n\n"
                f"🔗 URL: <code>{tiktok_url[:60]}...</code>\n"
                f"📊 Còn lại: {remaining} lượt hôm nay\n\n"
                f"💬 Chỉ nhập chữ cái thường (ví dụ: abcde)"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Đổi captcha", callback_data=f"refresh_cap:{user.id}"),
                 InlineKeyboardButton("❌ Huỷ", callback_data="cancel_buff")]
            ])
        )
        return WAITING_CAPTCHA

    except Exception as e:
        await msg.edit_text(f"❌ Lỗi kết nối Buff API: {e}")
        return ConversationHandler.END


async def callback_refresh_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Đang lấy captcha mới...")
    user = update.effective_user
    sess = _user_sessions.get(user.id)
    if not sess:
        await query.edit_message_caption("❌ Phiên đã hết hạn. Dùng /buff lại.")
        return ConversationHandler.END
    try:
        result = buff_api.refresh_captcha(sess["session_id"])
        captcha_b64 = result.get("captcha_b64") or result.get("captcha")
        if captcha_b64:
            img_data = base64.b64decode(captcha_b64)
            await query.edit_message_media(
                media={"type": "photo", "media": InputFile(io.BytesIO(img_data), filename="captcha.png")},
            )
        await query.edit_message_caption(
            "🖼 <b>Captcha mới — nhập chữ cái:</b>\n💬 Chỉ nhập chữ thường (a-z)",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Đổi captcha", callback_data=f"refresh_cap:{user.id}"),
                 InlineKeyboardButton("❌ Huỷ", callback_data="cancel_buff")]
            ])
        )
    except Exception as e:
        await query.answer(f"Lỗi: {e}", show_alert=True)
    return WAITING_CAPTCHA


async def callback_cancel_buff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Đã huỷ.")
    _user_sessions.pop(update.effective_user.id, None)
    await query.edit_message_caption("❌ Đã huỷ buff. Dùng /buff để bắt đầu lại.")
    return ConversationHandler.END


async def receive_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    sess = _user_sessions.get(user.id)
    if not sess:
        await update.message.reply_text("❌ Phiên đã hết hạn. Dùng /buff lại.")
        return ConversationHandler.END

    answer = update.message.text.strip().lower()
    # Only keep letters
    import re
    answer = re.sub(r"[^a-z]", "", answer)
    if not answer:
        await update.message.reply_text("⚠️ Chỉ nhập chữ cái thường (a-z)!")
        return WAITING_CAPTCHA

    msg = await update.message.reply_text("⏳ Đang xác thực captcha...")

    try:
        result = buff_api.solve_captcha(sess["session_id"], answer)
        if not result.get("ok") and not result.get("success"):
            await msg.edit_text(
                f"❌ Captcha sai: {result.get('message', 'Thử lại!')}\n\nDùng /buff lại."
            )
            _user_sessions.pop(user.id, None)
            return ConversationHandler.END

        # Get services
        svc_result = buff_api.get_services(sess["session_id"])
        services = [s for s in svc_result.get("services", []) if s.get("available") and s.get("has_action")]
        if not services:
            await msg.edit_text("❌ Không có service nào khả dụng lúc này. Thử lại sau!")
            _user_sessions.pop(user.id, None)
            return ConversationHandler.END

        sess["services"] = services
        buttons = [[InlineKeyboardButton(f"🚀 {s['name']}", callback_data=f"svc:{s['name']}")] for s in services]
        buttons.append([InlineKeyboardButton("❌ Huỷ", callback_data="cancel_buff")])

        await msg.edit_text(
            "✅ Captcha đúng!\n\n📋 <b>Chọn loại buff:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return WAITING_SERVICE

    except Exception as e:
        await msg.edit_text(f"❌ Lỗi: {e}")
        _user_sessions.pop(user.id, None)
        return ConversationHandler.END


async def callback_select_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    sess = _user_sessions.get(user.id)
    if not sess:
        await query.edit_message_text("❌ Phiên hết hạn. Dùng /buff lại.")
        return ConversationHandler.END

    service = query.data.replace("svc:", "", 1)
    await query.edit_message_text(f"⏳ Đang buff <b>{service}</b>...", parse_mode="HTML")

    try:
        result = buff_api.run_buff(sess["session_id"], service, sess["tiktok_url"])
        limit = int(database.get_setting("daily_limit", "10"))
        allowed, remaining = database.check_and_increment_buff(user.id, limit)
        if not allowed:
            await query.edit_message_text("⏰ Bạn đã hết lượt buff hôm nay!")
            _user_sessions.pop(user.id, None)
            return ConversationHandler.END

        if result.get("ok") or result.get("success"):
            amount = result.get("amount", 0)
            database.add_buff_log(user.id, sess["tiktok_url"], service, amount, "ok", result.get("message", ""))
            cooldown = result.get("cooldown")
            cd_text = f"\n⏱ Cooldown: {cooldown}s" if cooldown else ""
            await query.edit_message_text(
                f"🎉 <b>Buff thành công!</b>\n\n"
                f"🚀 Service: {service}\n"
                f"📈 Đã buff: {amount:,}\n"
                f"🔗 URL: <code>{sess['tiktok_url'][:50]}...</code>"
                f"{cd_text}\n\n"
                f"📊 Lượt còn lại hôm nay: <b>{remaining}</b>",
                parse_mode="HTML"
            )
        else:
            database.add_buff_log(user.id, sess["tiktok_url"], service, 0, "fail", result.get("message", ""))
            # Don't count failed buff against limit — revert
            await query.edit_message_text(
                f"❌ Buff thất bại: {result.get('message', 'Lỗi không rõ')}\n\nDùng /buff lại!"
            )

    except Exception as e:
        database.add_buff_log(user.id, sess["tiktok_url"], service, 0, "error", str(e))
        await query.edit_message_text(f"❌ Lỗi khi buff: {e}")
    finally:
        _user_sessions.pop(user.id, None)

    return ConversationHandler.END


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Đã huỷ. Dùng /buff để bắt đầu lại.")
    _user_sessions.pop(update.effective_user.id, None)
    return ConversationHandler.END


def build_buff_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("buff", cmd_buff)],
        states={
            WAITING_CAPTCHA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_captcha),
                CallbackQueryHandler(callback_refresh_captcha, pattern=r"^refresh_cap:"),
                CallbackQueryHandler(callback_cancel_buff, pattern="^cancel_buff$"),
            ],
            WAITING_SERVICE: [
                CallbackQueryHandler(callback_select_service, pattern=r"^svc:"),
                CallbackQueryHandler(callback_cancel_buff, pattern="^cancel_buff$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", fallback)],
        allow_reentry=True,
    )

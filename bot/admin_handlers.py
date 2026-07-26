"""Admin-only Telegram commands — hidden from regular users."""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
import database

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id in database.get_admin_ids()


async def _admin_only(update: Update) -> bool:
    if not _is_admin(update.effective_user.id):
        # Silently ignore non-admin invocations
        return False
    return True


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return
    stats = database.get_stats()
    settings = database.get_all_settings()
    await update.message.reply_text(
        "🔐 <b>Admin Panel Telegram</b>\n\n"
        f"👥 Tổng users: <b>{stats['total_users']}</b>\n"
        f"🟢 Active hôm nay: <b>{stats['active_today']}</b>\n"
        f"📈 Buff hôm nay: <b>{stats['buffs_today']}</b>\n"
        f"📊 Tổng buff: <b>{stats['total_buffs']}</b>\n"
        f"🚫 Banned: <b>{stats['banned_users']}</b>\n"
        f"🔗 Nhóm yêu cầu: <b>{stats['total_groups']}</b>\n\n"
        f"⚙️ API URL: <code>{settings.get('buff_api_url','Chưa đặt')[:40]}</code>\n"
        f"📅 Giới hạn/ngày: <b>{settings.get('daily_limit','10')}</b>\n\n"
        "<b>Lệnh admin:</b>\n"
        "/stats — Thống kê\n"
        "/broadcast &lt;tin nhắn&gt; — Gửi đại chúng\n"
        "/ban &lt;user_id&gt; — Cấm user\n"
        "/unban &lt;user_id&gt; — Bỏ cấm user\n"
        "/setlimit &lt;số&gt; — Đặt giới hạn ngày\n"
        "/setapi &lt;url&gt; — Đặt buff API URL\n"
        "/listusers — Danh sách user",
        parse_mode="HTML"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return
    stats = database.get_stats()
    logs = database.get_buff_logs(10)
    log_text = "\n".join(
        f"• {l['first_name'] or l['username'] or l['user_id']} — {l['service']} +{l['amount']} [{l['status']}]"
        for l in logs
    ) or "Chưa có"
    await update.message.reply_text(
        f"📊 <b>Thống kê hệ thống</b>\n\n"
        f"👥 Tổng users: {stats['total_users']}\n"
        f"🟢 Active hôm nay: {stats['active_today']}\n"
        f"📈 Buff hôm nay: {stats['buffs_today']}\n"
        f"📊 Tổng buff all-time: {stats['total_buffs']}\n"
        f"🚫 Banned: {stats['banned_users']}\n"
        f"🔗 Nhóm yêu cầu: {stats['total_groups']}\n\n"
        f"📋 <b>10 Buff gần nhất:</b>\n{log_text}",
        parse_mode="HTML"
    )


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text("❌ Cú pháp: /broadcast &lt;tin nhắn&gt;", parse_mode="HTML")
        return
    users = database.get_all_users()
    sent = 0
    failed = 0
    msg = await update.message.reply_text(f"📢 Đang gửi tới {len(users)} users...")
    for u in users:
        if u["is_banned"]:
            continue
        try:
            await context.bot.send_message(
                chat_id=u["user_id"],
                text=f"📢 <b>Thông báo từ Admin:</b>\n\n{text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1
    database.add_broadcast(text, sent, failed)
    await msg.edit_text(
        f"✅ Đã gửi thông báo!\n\n✔ Thành công: {sent}\n✖ Thất bại: {failed}"
    )


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Cú pháp: /ban &lt;user_id&gt;", parse_mode="HTML")
        return
    try:
        uid = int(context.args[0])
        database.ban_user(uid)
        await update.message.reply_text(f"🚫 Đã cấm user <code>{uid}</code>", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ User ID phải là số.")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Cú pháp: /unban &lt;user_id&gt;", parse_mode="HTML")
        return
    try:
        uid = int(context.args[0])
        database.unban_user(uid)
        await update.message.reply_text(f"✅ Đã bỏ cấm user <code>{uid}</code>", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ User ID phải là số.")


async def cmd_setlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return
    if not context.args:
        current = database.get_setting("daily_limit", "10")
        await update.message.reply_text(
            f"📅 Giới hạn buff hiện tại: <b>{current}/ngày</b>\nDùng /setlimit &lt;số&gt; để thay đổi.",
            parse_mode="HTML"
        )
        return
    try:
        n = int(context.args[0])
        if n < 1:
            raise ValueError
        database.set_setting("daily_limit", str(n))
        await update.message.reply_text(f"✅ Đã đặt giới hạn: <b>{n} lượt/ngày</b>", parse_mode="HTML")
    except ValueError:
        await update.message.reply_text("❌ Phải là số nguyên dương.")


async def cmd_setapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return
    url = " ".join(context.args).strip() if context.args else ""
    if not url:
        current = database.get_setting("buff_api_url", "Chưa đặt")
        await update.message.reply_text(
            f"🔗 API URL hiện tại: <code>{current}</code>\nDùng /setapi &lt;url&gt;",
            parse_mode="HTML"
        )
        return
    database.set_setting("buff_api_url", url.rstrip("/"))
    await update.message.reply_text(f"✅ Đã đặt Buff API URL:\n<code>{url}</code>", parse_mode="HTML")


async def cmd_listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _admin_only(update):
        return
    users = database.get_all_users()
    if not users:
        await update.message.reply_text("Chưa có user nào.")
        return
    lines = []
    for u in users[:30]:
        name = u["first_name"] or u["username"] or "?"
        status = "🚫" if u["is_banned"] else "✅"
        lines.append(f"{status} {name} (ID: <code>{u['user_id']}</code>) — buff: {u['total_buffs']}")
    text = "\n".join(lines)
    if len(users) > 30:
        text += f"\n\n... và {len(users)-30} user khác. Xem đầy đủ tại Admin Panel."
    await update.message.reply_text(
        f"👥 <b>Danh sách {len(users)} users:</b>\n\n{text}",
        parse_mode="HTML"
    )


def get_admin_handlers() -> list:
    return [
        CommandHandler("admin", cmd_admin),
        CommandHandler("stats", cmd_stats),
        CommandHandler("broadcast", cmd_broadcast),
        CommandHandler("ban", cmd_ban),
        CommandHandler("unban", cmd_unban),
        CommandHandler("setlimit", cmd_setlimit),
        CommandHandler("setapi", cmd_setapi),
        CommandHandler("listusers", cmd_listusers),
    ]

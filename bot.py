import os
import sqlite3
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters,
)

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = os.environ.get("DB_PATH", "reports.sqlite3")

TARGET, REASON, EVIDENCE, CONFIRM = range(4)
REASONS = {
    "spam": "Спам",
    "scam": "Мошенничество",
    "threats": "Угрозы",
    "impersonation": "Выдаёт себя за другого",
    "other": "Другое",
}


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                target TEXT NOT NULL,
                reason TEXT NOT NULL,
                evidence TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я помогу подготовить и сохранить черновик обоснованного обращения.\n\n"
        "/report — создать черновик\n"
        "/history — история\n"
        "/cancel — отменить\n\n"
        "Бот не рассылает массовые жалобы и не подключает пользовательские аккаунты."
    )


async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Пришли @username или ссылку на публичный профиль, канал или группу.")
    return TARGET


async def target_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = (update.message.text or "").strip()
    if not target or len(target) > 200:
        await update.message.reply_text("Пришли корректный @username или ссылку.")
        return TARGET
    context.user_data["target"] = target
    buttons = [[InlineKeyboardButton(label, callback_data=key)] for key, label in REASONS.items()]
    await update.message.reply_text(
        "Выбери только ту причину, которая действительно соответствует ситуации:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return REASON


async def reason_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data
    if key not in REASONS:
        await query.edit_message_text("Неизвестная причина. Начни заново командой /report.")
        return ConversationHandler.END
    context.user_data["reason"] = REASONS[key]
    await query.edit_message_text(
        "Пришли доказательства: ссылки на конкретные сообщения, даты и краткое описание. "
        "Если доказательств пока нет, напиши «нет». Не отправляй пароли и коды входа."
    )
    return EVIDENCE


async def evidence_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["evidence"] = (update.message.text or "").strip()[:4000]
    text = (
        "Проверь черновик:\n\n"
        f"Объект: {context.user_data['target']}\n"
        f"Причина: {context.user_data['reason']}\n"
        f"Доказательства: {context.user_data['evidence']}\n\n"
        "Сохранить?"
    )
    keyboard = [[
        InlineKeyboardButton("Сохранить", callback_data="save"),
        InlineKeyboardButton("Отмена", callback_data="discard"),
    ]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM


async def confirm_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "discard":
        context.user_data.clear()
        await query.edit_message_text("Черновик отменён.")
        return ConversationHandler.END

    data = context.user_data
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO reports(user_id,target,reason,evidence,created_at) VALUES(?,?,?,?,?)",
            (
                query.from_user.id,
                data["target"],
                data["reason"],
                data["evidence"],
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
    context.user_data.clear()
    await query.edit_message_text(
        "Черновик сохранён. Жалоба не отправлена автоматически. "
        "Проверь факты и при необходимости используй официальную форму: "
        "https://telegram.org/support"
    )
    return ConversationHandler.END


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id,target,reason,created_at FROM reports "
            "WHERE user_id=? ORDER BY id DESC LIMIT 20",
            (update.effective_user.id,),
        ).fetchall()
    if not rows:
        await update.message.reply_text("Сохранённых черновиков пока нет.")
        return
    lines = ["Последние черновики:"]
    for rid, target, reason, created in rows:
        lines.append(f"#{rid} · {target} · {reason} · {created[:10]}")
    await update.message.reply_text("\n".join(lines))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def main():
    if not TOKEN:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN.")
    init_db()
    app = Application.builder().token(TOKEN).build()
    conversation = ConversationHandler(
        entry_points=[CommandHandler("report", report_start)],
        states={
            TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, target_received)],
            REASON: [CallbackQueryHandler(reason_received, pattern="^(spam|scam|threats|impersonation|other)$")],
            EVIDENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, evidence_received)],
            CONFIRM: [CallbackQueryHandler(confirm_received, pattern="^(save|discard)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(conversation)
    app.add_handler(CommandHandler("cancel", cancel))
    print("Bot polling started")
    app.run_polling()


if __name__ == "__main__":
    main()

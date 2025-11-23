from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_ID

# === ШПИОНСКИЙ МОДУЛЬ (SPY MODE) ===
async def log_action(update: Update, context, action_name: str):
    """Отправляет Семёну Юрьевичу уведомление о каждом шаге юзера"""
    user = update.effective_user
    # Не спамить действиями самого админа
    if user.id == ADMIN_ID: return
    
    msg = (
        f"🕵️‍♂️ <b>SPY LOG</b>\n"
        f"👤 <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username})\n"
        f"⚡️ Действие: <b>{action_name}</b>"
    )
    try:
        await context.bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
    except: pass

# === ГЕНЕРАТОР КНОПКИ "НАЗАД" ===
def back_btn(callback_data):
    return [InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]
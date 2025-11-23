from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from database import core as db
from keyboards import menu as kb
from config import ADMIN_ID

async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    
    u, o, m = await db.get_stats()
    txt = (
        f"👑 <b>КАБИНЕТ ВЛАДЕЛЬЦА</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👥 Людей в базе: {u}\n"
        f"📦 Всего заказов: {o}\n"
        f"💵 <b>Оборот: {m} ₽</b>\n"
        f"━━━━━━━━━━━━━━━━"
    )
    await query.edit_message_text(txt, reply_markup=kb.admin_kb(), parse_mode="HTML")

# --- РАССЫЛКА ---
async def broadcast_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("📝 <b>Напишите сообщение для рассылки:</b>\n(Можно с фото/видео)")
    return 1

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = await db.get_all_users()
    count = 0
    blocked = 0
    
    msg = await update.message.reply_text("⏳ <b>Запуск рассылки...</b>")
    
    for u in users:
        try:
            await update.message.copy(chat_id=u['user_id'])
            count += 1
        except: 
            blocked += 1
            
    await msg.edit_text(f"✅ <b>Рассылка завершена!</b>\nПолучили: {count}\nЗаблочили: {blocked}")
    return ConversationHandler.END
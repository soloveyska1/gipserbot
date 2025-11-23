from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from database import core as db
from database import pricing as logic
from keyboards import menu as kb
from config import ADMIN_IDS, SERVICES
from utils import log_action

# --- ENTRY ---
async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверка: если юзера НЕТ в списке админов - игнорируем
    if update.effective_user.id not in ADMIN_IDS: return
    await update.callback_query.edit_message_text("💀 <b>GOD MODE ACTIVATED</b>", reply_markup=kb.admin_main(), parse_mode="HTML")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u, o, m = await db.get_stats()
    txt = f"📊 <b>СТАТИСТИКА</b>\n\n👤 Юзеров: {u}\n📦 Заказов: {o}\n💵 Оборот: {m} ₽"
    await update.callback_query.edit_message_text(txt, reply_markup=kb.admin_main(), parse_mode="HTML")

# --- ORDER MANAGEMENT ---
async def list_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    page = 0
    if "page_" in query.data:
        page = int(query.data.split("_")[-1])
    
    orders = await db.get_all_orders(limit=100) # Get last 100
    await query.edit_message_text(
        f"📦 <b>АКТИВНЫЕ ЗАКАЗЫ (Стр. {page+1})</b>", 
        reply_markup=kb.admin_orders_list_kb(orders, page),
        parse_mode="HTML"
    )

async def order_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("set_status_"):
        parts = data.split("_")
        oid = int(parts[2])
    else:
        oid = int(data.split("_")[-1])
    o = await db.get_order(oid)
    
    txt = (
        f"📦 <b>ЗАКАЗ #{oid}</b>\n"
        f"👤 Юзер: {o['user_id']}\n"
        f"📚 Тип: {o['service_type']}\n"
        f"💰 Цена: {o['price']} ₽\n"
        f"📊 Статус: {o['status']}\n"
        f"📝 Тема: {o['topic']}\n"
    )
    await query.edit_message_text(txt, reply_markup=kb.admin_order_actions(oid, o['status']), parse_mode="HTML")

async def set_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    oid = int(parts[2])
    status = parts[3]
    
    await db.update_order_status(oid, status)
    
    # Notify User
    o = await db.get_order(oid)
    status_msg = {
        "work": "⚙️ <b>Ваш заказ #{oid} взят в работу!</b>\nМы начали. Ожидайте.",
        "done": "✅ <b>Заказ #{oid} ГОТОВ!</b>\nПринимайте работу.",
        "pending_pay": "💳 <b>По заказу #{oid} ожидается оплата.</b>",
        "cancel": "❌ <b>Заказ #{oid} отменен.</b>"
    }
    if status in status_msg:
        try: await context.bot.send_message(o['user_id'], status_msg[status], parse_mode="HTML")
        except: pass

    await query.answer(f"Статус изменен на {status}")
    await order_action(update, context) # Refresh view

# --- USER MANAGEMENT ---
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    page = 0
    if "page_" in query.data:
        page = int(query.data.split("_")[-1])
    
    users = await db.get_all_users()
    await query.edit_message_text(
        f"👥 <b>ПОЛЬЗОВАТЕЛИ (Стр. {page+1})</b>", 
        reply_markup=kb.admin_users_list_kb(users, page),
        parse_mode="HTML"
    )

async def user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = int(query.data.split("_")[-1])
    u = await db.get_user(uid)
    
    txt = (
        f"👤 <b>ЮЗЕР: {u['full_name']}</b>\n"
        f"🆔 ID: <code>{u['user_id']}</code>\n"
        f"💰 Баланс: {u['balance']} ₽\n"
        f"🚫 Бан: {'ДА' if u['is_banned'] else 'НЕТ'}\n"
        f"🔗 Реферрер: {u['referrer_id']}\n"
    )
    await query.edit_message_text(txt, reply_markup=kb.admin_user_actions(uid, u['is_banned']), parse_mode="HTML")

async def toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    action = parts[0] # ban or unban
    uid = int(parts[1])
    
    val = 1 if action == "ban" else 0
    await db.update_user_field(uid, "is_banned", val)
    
    await query.answer(f"Юзер {action}ned")
    # Refresh view by simulating callback
    query.data = f"adm_user_{uid}"
    await user_action(update, context)

# --- SETTINGS ---
SET_PRICE_STEP = 1
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("⚙️ <b>НАСТРОЙКИ ЦЕН</b>\nВыберите, что изменить:", reply_markup=kb.settings_kb(), parse_mode="HTML")

async def set_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    print(f"DEBUG: set_price_start triggered with data: {query.data}") # LOGGING
    
    key = query.data.replace("set_price_", "")
    context.user_data['price_key'] = key
    
    current = await logic.get_price(key)
    await query.edit_message_text(f"💰 <b>Изменение цены [{key}]</b>\nТекущая: {current} ₽\n\nВведите новую цену:", parse_mode="HTML")
    return SET_PRICE_STEP

async def set_price_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text)
        key = context.user_data['price_key']
        await logic.set_price(key, val)
        await update.message.reply_text(f"✅ Цена {key} установлена: {val} ₽")
    except:
        await update.message.reply_text("❌ Ошибка. Введите число.")
    return ConversationHandler.END

# SEARCH
SEARCH_STEP = 1
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("🔍 <b>Введите ID или @username пользователя:</b>", parse_mode="HTML")
    return SEARCH_STEP

async def search_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.replace("@", "")
    # Try to find by ID
    if q.isdigit():
        u = await db.get_user(int(q))
    else:
        # Find by username (inefficient but works for small db)
        users = await db.get_all_users()
        u = next((x for x in users if x['username'] and x['username'].lower() == q.lower()), None)
    
    if u:
        txt = (
            f"👤 <b>ЮЗЕР: {u['full_name']}</b>\n"
            f"🆔 ID: <code>{u['user_id']}</code>\n"
            f"💰 Баланс: {u['balance']} ₽\n"
            f"🚫 Бан: {'ДА' if u['is_banned'] else 'НЕТ'}\n"
            f"🔗 Реферрер: {u['referrer_id']}\n"
        )
        await update.message.reply_text(txt, reply_markup=kb.admin_user_actions(u['user_id'], u['is_banned']), parse_mode="HTML")
    else:
        await update.message.reply_text("❌ Не найден.")
    return ConversationHandler.END
from telegram import Update
from telegram.ext import ContextTypes
from database import requests as db
from keyboards import builders as kb
from config import TEXTS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_id = int(args[0]) if args and args[0].isdigit() else None
    
    is_new = await db.register_user(user.id, user.username, user.full_name, ref_id)
    
    if is_new and ref_id:
        await db.update_balance(ref_id, 0, "add") # Просто уведомляем, деньги после оплаты
        try: await context.bot.send_message(ref_id, f"🎣 <b>Клюнул!</b>\nНовый реферал: {user.full_name}")
        except: pass

    msg = TEXTS["welcome_new"] if is_new else TEXTS["welcome_old"]
    await update.message.reply_text(msg, reply_markup=kb.main_menu(user.id), parse_mode="HTML")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await db.get_user(update.effective_user.id)
    
    # Ранговая система с унижением/возвышением
    if u['orders_count'] == 0: status = "👶 Турист (0 заказов)"
    elif u['orders_count'] < 3: status = "👔 Свой человек"
    else: status = "👑 Элита Синдиката"

    txt = (
        f"👤 <b>ДОСЬЕ: {u['full_name']}</b>\n"
        f"💳 Баланс: <b>{u['balance']} ₽</b>\n"
        f"🎗 Статус: {status}\n"
        f"💸 Потрачено: {u['total_spent']} ₽\n\n"
        "<i>Используйте баланс для оплаты до 50% стоимости заказов.</i>"
    )
    await update.callback_query.edit_message_text(txt, reply_markup=kb.main_menu(update.effective_user.id), parse_mode="HTML")

async def partners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_user = await context.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start={update.effective_user.id}"
    
    txt = (
        "🤑 <b>СХЕМА ЗАРАБОТКА</b>\n\n"
        "Твои друзья все равно закажут работу. Вопрос — заработаешь ли ты на этом?\n\n"
        "1. Кидай им ссылку ниже.\n"
        "2. Они делают заказ.\n"
        "3. Ты получаешь <b>15%</b> от чека НАВСЕГДА.\n\n"
        f"🔗 Твоя ссылка:\n<code>{link}</code>"
    )
    await update.callback_query.edit_message_text(txt, reply_markup=kb.main_menu(update.effective_user.id), parse_mode="HTML")
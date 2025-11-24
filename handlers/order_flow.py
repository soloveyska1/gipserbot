from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import logging
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from database import db as catalog_db
from keyboards import builders as kb
from config import ADMIN_IDS, URGENCY_MULTIPLIER
import json

# STATES
TYPE, TOPIC, DEADLINE, UPSELL, PAY_CHOICE, PAY_CUSTOM, CONFIRM, CONSULT = range(8)

# PHOTO ID FOR STEP 1
MENU_PHOTO = "AgACAgIAAxkBAAEFG0hpI9Pfsi5VGfwKuZSrGQFsslxf0wACeQtrG_RHIEk67aeU_toGxwEAAwIAA3kAAzYE"

async def _safe_edit(query, text, markup=None):
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    except:
        await query.message.reply_text(text, reply_markup=markup, parse_mode="HTML")

# === 1. START & SHOWCASE ===
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: 
        await query.answer()
        # If we have a photo, we might need to delete old msg and send new photo
        try: await query.message.delete()
        except: pass

    # Init Session
    context.user_data['order'] = {'upsells': {'speech': False, 'pres': False, 'vip': False}}
    
    caption = (
        "🌵 <b>БАР ОТКРЫТ. СТВОЛЫ СМАЗАНЫ.</b>\n\n"
        "Что будем готовить сегодня, партнер?\n"
        "Выбирай калибр. У нас есть всё: от легких эссе до тяжелой артиллерии."
    )
    
    chat_id = update.effective_chat.id
    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=MENU_PHOTO,
            caption=caption,
            reply_markup=kb.service_showcase_kb(),
            parse_mode="HTML"
        )
    except Exception as exc:
        logging.warning("Failed to send showcase photo, falling back to text: %s", exc)
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=kb.service_showcase_kb(),
            parse_mode="HTML"
        )
    return TYPE

async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "home":
        # Logic to return to main menu (client.start) - handled in main.py fallback
        return ConversationHandler.END
        
    # Save Service Info
    srv_map = {
        "srv_diploma": ("Диплом", 15000), "srv_term": ("Курсовая", 3500),
        "srv_essay": ("Эссе", 1500), "srv_practice": ("Отчет", 2500),
        "srv_exam": ("Экзамен", 1000), "srv_speech": ("Речь", 1500),
        "srv_pres": ("Презентация", 2000), "srv_vip": ("VIP", 5000)
    }
    
    choice = srv_map.get(query.data, ("Услуга", 0))
    context.user_data['order']['service_name'] = choice[0]
    context.user_data['order']['base_price'] = choice[1]
    
    # Move to Step 2
    txt = (
        "🎯 <b>ШАГ 2: ДОСЬЕ НА ЦЕЛЬ</b>\n\n"
        "Принимаю данные в любом виде. Не трать время на перепечатку.\n\n"
        "📥 <b>Кидай сюда:</b>\n"
        "• 🎙 <b>Голосовое</b> (расскажи суть)\n"
        "• 📸 <b>Фото</b> (методички, записки)\n"
        "• 🔄 <b>Пересланные сообщения</b>\n"
        "• 📎 <b>Файлы</b> (Word/PDF)\n"
        "• ✍️ <b>Текст</b>\n\n"
        "👇 <i>Жду улики...</i>"
    )
    # We send a new message because previous was a photo caption
    await query.message.reply_text(txt, reply_markup=kb.dossier_kb(), parse_mode="HTML")
    return TOPIC

# === 2. TOPIC INTAKE ===
async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check for "No Topic" button
    if update.callback_query and update.callback_query.data == "topic_help":
        await update.callback_query.answer()
        context.user_data['order']['topic'] = "⚠️ НУЖЕН МОЗГОВОЙ ШТУРМ (Подбор темы)"
        context.user_data['order']['source'] = "help_needed"
        # Go to step 3
        await _safe_edit(update.callback_query, _deadline_text(), kb.deadline_kb())
        return DEADLINE
        
    if update.callback_query and update.callback_query.data == "srv_back":
        return await start_order(update, context)

    # Handle Inputs
    msg = update.message
    context.user_data['order']['source'] = "organic"
    
    if msg.voice:
        context.user_data['order']['voice_id'] = msg.voice.file_id
        context.user_data['order']['topic'] = "🎤 Голосовое сообщение"
    elif msg.document or msg.photo:
        context.user_data['order']['files'] = "files_attached" # Simplified marker
        context.user_data['order']['topic'] = msg.caption or "📎 Файлы/Материалы"
    else:
        context.user_data['order']['topic'] = msg.text

    await msg.reply_text(_deadline_text(), reply_markup=kb.deadline_kb(), parse_mode="HTML")
    return DEADLINE

def _deadline_text():
    return "⏳ <b>ШАГ 3: ШКАЛА АДРЕНАЛИНА</b>\n\nПосмотри на календарь. Насколько сильно горят мосты?"

# === 3. DEADLINE ===
async def get_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_topic":
        await _safe_edit(query, "🎯 <b>Возврат к досье.</b> Жду новую тему или файлы...", kb.dossier_kb())
        return TOPIC
    
    # Save multiplier
    mult_map = {"time_urgent": 1.4, "time_fast": 1.15, "time_normal": 1.0}
    name_map = {"time_urgent": "🔥 ОГОНЬ (1-3 дня)", "time_fast": "⚡️ В ТЕМПЕ", "time_normal": "🐢 Спокойно"}
    
    context.user_data['order']['multiplier'] = mult_map.get(query.data, 1.0)
    context.user_data['order']['deadline_name'] = name_map.get(query.data, "Норма")
    
    await _render_upsell(query, context)
    return UPSELL

# === 4. UPSELLS (TOGGLES) ===
async def _render_upsell(query, context):
    o = context.user_data['order']
    base = o['base_price']
    mult = o['multiplier']
    
    # Calc current total
    current_total = int(base * mult)
    ups = o['upsells']
    if ups['speech']: current_total += 1500
    if ups['pres']: current_total += 2000
    if ups['vip']: current_total += 2500
    
    txt = (
        f"🧳 <b>ШАГ 4: СБОРКА ИНВЕНТАРЯ</b>\n\n"
        f"База: {base} ₽\n"
        f"Коэфф. срочности: x{mult}\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"💰 <b>ТЕКУЩАЯ СУММА: {current_total} ₽</b>\n"
        f"➖➖➖➖➖➖➖➖\n\n"
        f"👇 <i>Добавь патронов, если нужно:</i>"
    )
    await _safe_edit(query, txt, markup=kb.upsell_kb(ups))

async def get_upsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "upsell_done":
        return await init_payment(query, context)
        
    # Toggle logic
    ups = context.user_data['order']['upsells']
    key = data.replace("toggle_", "")
    if key in ups:
        ups[key] = not ups[key] # Flip True/False
        
    await _render_upsell(query, context)
    return UPSELL

# === 5. PAYMENT ===
async def init_payment(query, context):
    o = context.user_data['order']
    
    # Final calc before discounts
    price = int(o['base_price'] * o['multiplier'])
    if o['upsells']['speech']: price += 1500
    if o['upsells']['pres']: price += 2000
    if o['upsells']['vip']: price += 2500
    
    o['price_before_discount'] = price
    
    # Get Balance
    user = await db.get_user(query.from_user.id)
    balance = user.get('balance', 0)
    max_discount = int(price * 0.5)
    
    context.user_data['order']['balance'] = balance
    context.user_data['order']['max_discount'] = max_discount
    
    txt = (
        f"💎 <b>ШАГ 5: КАЗНА</b>\n\n"
        f"К оплате: <b>{price} ₽</b>\n"
        f"Твой баланс: 💎 {balance}\n"
        f"Можно списать до: 💎 {max_discount}\n\n"
        f"👇 <i>Сколько спишем?</i>"
    )
    await _safe_edit(query, txt, markup=kb.payment_kb(balance, max_discount))
    return PAY_CHOICE

async def handle_payment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    o = context.user_data['order']
    points = 0
    
    if data == "pay_zero": points = 0
    elif data == "pay_all": points = min(o['balance'], o['max_discount'])
    elif data == "pay_1000": points = 1000
    elif data == "pay_500": points = 500
    elif data == "pay_custom":
        await _safe_edit(query, "✍️ <b>Введите сумму баллов</b> (числом):")
        return PAY_CUSTOM
        
    return await show_contract(query, context, points)

async def custom_points_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        points = int(update.message.text)
        o = context.user_data['order']
        if points < 0: raise ValueError
        if points > o['balance']:
            await update.message.reply_text(f"❌ У вас всего {o['balance']} баллов.")
            return PAY_CUSTOM
        if points > o['max_discount']:
            await update.message.reply_text(f"❌ Максимум можно списать {o['max_discount']}.")
            return PAY_CUSTOM
            
        # Valid
        return await show_contract(None, context, points, message=update.message)
    except ValueError:
        await update.message.reply_text("❌ Введите целое число.")
        return PAY_CUSTOM

# === 6. CONTRACT ===
async def show_contract(query, context, points_used, message=None):
    o = context.user_data['order']
    o['points_used'] = points_used
    o['final_price'] = o['price_before_discount'] - points_used
    
    # List upsells
    ups_list = []
    if o['upsells']['vip']: ups_list.append("VIP")
    if o['upsells']['speech']: ups_list.append("Речь")
    if o['upsells']['pres']: ups_list.append("Слайды")
    ups_str = ", ".join(ups_list) if ups_list else "—"
    
    txt = (
        f"🧾 <b>КВИТАНЦИЯ #DRAFT</b>\n"
        f"<pre>\n"
        f"УСЛУГА:.......{o['service_name']}\n"
        f"СРОЧНОСТЬ:....{o['deadline_name']}\n"
        f"ДОПЫ:.........{ups_str}\n"
        f"------------------------------\n"
        f"ПОДЫТОГ:......{o['price_before_discount']} ₽\n"
        f"СКИДКА:.......-{points_used} ₽\n"
        f"==============================\n"
        f"ИТОГО:        {o['final_price']} ₽\n"
        f"</pre>\n"
        f"⚠️ <i>Нажимая кнопку, вы заключаете джентльменское соглашение.</i>"
    )
    
    if query:
        await _safe_edit(query, txt, markup=kb.contract_kb())
    else:
        await message.reply_text(txt, reply_markup=kb.contract_kb(), parse_mode="HTML")
    return CONFIRM

# === 7. SUBMIT ===
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "order_start":
        return await start_order(update, context)
        
    o = context.user_data['order']
    user = query.from_user
    
    # Save to DB
    order_data = {
        'uid': user.id,
        'type': o['service_name'],
        'topic': o['topic'],
        'deadline': o['deadline_name'],
        'final_price': o['final_price'],
        'original_price': o['price_before_discount'],
        'points_used': o['points_used'],
        'promo_code': None
    }
    oid = await db.create_order(order_data)
    
    # Deduct points
    if o['points_used'] > 0:
        await db.adjust_balance(user.id, -o['points_used'], f"Заказ #{oid}")
        
    # Admin Notify (Simplified for now)
    for admin_id in ADMIN_IDS:
        try: await context.bot.send_message(admin_id, f"🚨 <b>НОВЫЙ ЗАКАЗ #{oid}</b>\n💰 {o['final_price']} ₽", parse_mode="HTML")
        except: pass
        
    # Client Success
    txt = (
        f"🤝 <b>Сделка скреплена!</b>\n\n"
        f"Заказ <b>#{oid}</b> лежит на столе у менеджера. В течение 15 минут он постучится к тебе в личку.\n\n"
        f"<i>Пока ждешь, можешь расслабиться:</i>"
    )
    await _safe_edit(query, txt, markup=kb.success_kb(oid))
    return ConversationHandler.END


# === CONSULTATION (SOS) ===
async def cancel_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow users to stop the consultation flow gracefully."""
    query = update.callback_query
    if query:
        await query.answer()
        await _safe_edit(query, "❌ Консультация отменена.")
    else:
        await update.effective_message.reply_text("❌ Консультация отменена.")
    return ConversationHandler.END


async def handle_consultation_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect a freeform consultation request and notify admins."""
    message = update.effective_message
    user = update.effective_user

    # Forward the content to admins if possible
    for admin_id in ADMIN_IDS:
        try:
            await message.copy_to(admin_id)
        except Exception:
            try:
                await context.bot.send_message(admin_id, f"🆘 Запрос консультации от {user.id}")
            except Exception:
                pass

    await message.reply_text(
        "🆘 Сигнал получен. Менеджер свяжется в ближайшее время.",
        parse_mode="HTML",
    )
    return ConversationHandler.END

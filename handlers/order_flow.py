from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from database import db as catalog_db
from keyboards import client_kb as kb
from config import SERVICES, URGENCY_MULTIPLIER, ADMIN_IDS
import datetime

# Определение состояний (должно совпадать с main.py)
TYPE, SERVICE_CARD, TOPIC, DEADLINE, UPSELL, PAY_CHOICE, CONFIRM, CONSULT = range(8)

async def _safe_edit(query, text, **kwargs):
    try:
        await query.edit_message_text(text, **kwargs)
    except:
        await query.message.reply_text(text, **kwargs)

# === 1. НАЧАЛО ЗАКАЗА ===
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    # Сбрасываем данные заказа
    context.user_data['order'] = {}
    
    services = await catalog_db.get_all_services()
    if not services:
        txt = "⚠️ Сейчас нет доступных услуг. Напишите шерифу."
        if query: await _safe_edit(query, txt, reply_markup=kb.main_kb(update.effective_user.id))
        else: await update.message.reply_text(txt, reply_markup=kb.main_kb(update.effective_user.id))
        return ConversationHandler.END

    # Генерируем клавиатуру услуг
    keyboard = []
    for s in services:
        keyboard.append([InlineKeyboardButton(f"{s['name']}", callback_data=f"srv_{s['id']}")])
    keyboard.append([InlineKeyboardButton("🆘 Нужна консультация", callback_data="consultation_request")])
    keyboard.append([InlineKeyboardButton("🏠 В меню", callback_data="home")])
    
    txt = "💼 <b>ШАГ 1: ВЫБОР ДЕЛА</b>\nКакую работу нужно выполнить?"
    
    if query:
        await _safe_edit(query, txt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return TYPE

# === 2. ВЫБОР ТИПА И ПОКАЗ КАРТОЧКИ ===
async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "consultation_request":
        await _safe_edit(query, "👨‍✈️ <b>КОНСУЛЬТАЦИЯ</b>\n\nОпишите вашу проблему одним сообщением (можно прикрепить фото/файл). Шериф ответит лично.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="consult_cancel")]]), parse_mode="HTML")
        return CONSULT
    
    srv_id = int(data.split("_")[1])
    service = await catalog_db.get_service(srv_id)
    
    context.user_data['order']['service_id'] = srv_id
    context.user_data['order']['service_name'] = service['name']
    context.user_data['order']['base_price'] = service['price']
    
    # Карточка услуги
    txt = (
        f"✅ <b>{service['name']}</b>\n\n"
        f"{service.get('description', 'Описание отсутствует')}\n\n"
        f"💰 Базовая цена: <b>{service['price']} ₽</b>\n"
        f"👇 Подтвердите выбор, чтобы перейти к деталям."
    )
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Выбрать эту услугу", callback_data=f"srv_confirm_{srv_id}")],
        [InlineKeyboardButton("🔙 Назад к списку", callback_data="back_to_type")]
    ])
    
    await _safe_edit(query, txt, reply_markup=markup, parse_mode="HTML")
    return SERVICE_CARD

async def confirm_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if "srv_back" in query.data:
        return await start_order(update, context)
        
    await _safe_edit(
        query,
        "📝 <b>ШАГ 2: ЗАДАНИЕ</b>\n\nНапишите тему работы, прикрепите методичку или опишите требования.\n\n<i>Отправьте сообщение или файл...</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_to_type")]]),
        parse_mode="HTML"
    )
    return TOPIC

# === 3. ТЕМА И ФАЙЛЫ ===
async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.caption or update.message.text or "[Файл]"
    context.user_data['order']['topic'] = text
    
    # Если есть файл, можно сохранить его ID (логику сохранения опустим для простоты, берем текст)
    
    await update.message.reply_text(
        "⏳ <b>ШАГ 3: СРОКИ</b>\nНасколько это срочно?",
        reply_markup=kb.deadline_kb(),
        parse_mode="HTML"
    )
    return DEADLINE

# === 4. ДЕДЛАЙН ===
async def get_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_topic":
        await _safe_edit(query, "📝 Жду тему или файлы...", reply_markup=None)
        return TOPIC
        
    is_urgent = (query.data == "time_urgent")
    context.user_data['order']['is_urgent'] = is_urgent
    context.user_data['order']['deadline_text'] = "Срочно (1-3 дня)" if is_urgent else "В штатном режиме"
    
    # Инициализация допов
    context.user_data['order']['upsells'] = {'speech': False, 'pres': False, 'vip': False}
    
    await _update_upsell_message(query, context)
    return UPSELL

# === 5. UPSELL (ДОПЫ) ===
async def _update_upsell_message(query, context):
    ups = context.user_data['order']['upsells']
    
    # Цены допов (можно вынести в конфиг)
    P_SPEECH = 1500
    P_PRES = 2000
    P_VIP = 2500
    
    await _safe_edit(
        query,
        "➕ <b>ШАГ 4: ДОПОЛНИТЕЛЬНО</b>\nНужно что-то еще?",
        reply_markup=kb.upsell_kb(ups['speech'], ups['pres'], ups['vip'], P_SPEECH, P_PRES, P_VIP),
        parse_mode="HTML"
    )

async def get_upsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back_to_deadline":
        await _safe_edit(query, "⏳ Выберите срочность:", reply_markup=kb.deadline_kb())
        return DEADLINE
        
    if data == "upsell_done":
        return await calculate_final(query, context)
        
    # Переключатели
    ups = context.user_data['order']['upsells']
    if data == "toggle_speech": ups['speech'] = not ups['speech']
    elif data == "toggle_pres": ups['pres'] = not ups['pres']
    elif data == "toggle_vip": ups['vip'] = not ups['vip']
    
    await _update_upsell_message(query, context)
    return UPSELL

# === 6. РАСЧЕТ И ОПЛАТА ===
async def calculate_final(query, context):
    o = context.user_data['order']
    
    # Расчет цены
    price = o['base_price']
    if o['is_urgent']: price = int(price * URGENCY_MULTIPLIER)
    
    extras = 0
    if o['upsells']['speech']: extras += 1500
    if o['upsells']['pres']: extras += 2000
    if o['upsells']['vip']: extras += 2500
    
    total = price + extras
    o['price_calculated'] = total
    o['final_price'] = total
    o['points_used'] = 0
    
    # Проверка баллов
    user_db = await db.get_user(query.from_user.id)
    balance = user_db.get('balance', 0)
    
    # Логика: можно оплатить до 50% баллами
    max_discount = int(total * 0.5)
    can_use = min(balance, max_discount)
    
    context.user_data['order']['can_use_points'] = can_use
    
    if can_use > 0:
        await _safe_edit(
            query,
            f"💰 <b>К ОПЛАТЕ: {total} ₽</b>\n\n"
            f"У вас есть <b>{balance}</b> баллов.\n"
            f"Можно списать: <b>{can_use}</b> баллов.\n\n"
            f"Использовать их?",
            reply_markup=kb.points_choice_kb(can_use),
            parse_mode="HTML"
        )
        return PAY_CHOICE
    else:
        # Сразу к подтверждению
        return await show_confirm(query, context)

async def handle_payment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    o = context.user_data['order']
    if query.data == "use_points_yes":
        points = o['can_use_points']
        o['points_used'] = points
        o['final_price'] = o['price_calculated'] - points
    
    return await show_confirm(query, context)

async def show_confirm(query, context):
    o = context.user_data['order']
    
    ups_text = []
    if o['upsells']['speech']: ups_text.append("Речь")
    if o['upsells']['pres']: ups_text.append("Презентация")
    if o['upsells']['vip']: ups_text.append("VIP")
    ups_str = ", ".join(ups_text) if ups_text else "Нет"
    
    txt = (
        f"🧾 <b>ИТОГОВАЯ СМЕТА</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📚 Услуга: {o['service_name']}\n"
        f"⏳ Срок: {o['deadline_text']}\n"
        f"➕ Допы: {ups_str}\n"
        f"📝 Тема: {o['topic'][:50]}...\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💵 Цена: {o['price_calculated']} ₽\n"
        f"💎 Списание баллов: -{o['points_used']}\n"
        f"💰 <b>ИТОГО: {o['final_price']} ₽</b>\n\n"
        f"🚀 <i>Подтвердите заказ, чтобы отправить его менеджеру.</i>"
    )
    
    await _safe_edit(query, txt, reply_markup=kb.confirm_kb(), parse_mode="HTML")
    return CONFIRM

# === 7. ФИНАЛИЗАЦИЯ ===
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "home":
        await _safe_edit(query, "🏠 Заказ отменен.", reply_markup=kb.main_kb(query.from_user.id))
        return ConversationHandler.END
        
    o = context.user_data['order']
    user = query.from_user
    
    # Сохраняем в БД
    order_data = {
        'uid': user.id,
        'type': o['service_name'], # Сохраняем имя услуги как тип
        'topic': o['topic'],
        'deadline': o['deadline_text'],
        'final_price': o['final_price'],
        'original_price': o['price_calculated'],
        'points_used': o['points_used'],
        'promo_code': None 
    }
    
    # Создаем заказ
    oid = await db.create_order(order_data)
    
    # Списываем баллы у юзера если использовал
    if o['points_used'] > 0:
        await db.adjust_balance(user.id, -o['points_used'], f"Оплата заказа #{oid}")

    # Уведомляем Админа
    admin_txt = (
        f"🚨 <b>НОВЫЙ ЗАКАЗ #{oid}</b>\n"
        f"👤 <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
        f"💵 Сумма: {o['final_price']} ₽\n"
        f"📚 Услуга: {o['service_name']}\n"
        f"⏳ Дедлайн: {o['deadline_text']}"
    )
    
    for admin_id in ADMIN_IDS:
        try: await context.bot.send_message(admin_id, admin_txt, parse_mode="HTML")
        except: pass

    await _safe_edit(
        query,
        f"✅ <b>ЗАКАЗ #{oid} ПРИНЯТ!</b>\n\nМенеджер уже изучает детали. Ожидайте сообщения.",
        reply_markup=kb.main_kb(user.id),
        parse_mode="HTML"
    )
    return ConversationHandler.END

# === КОНСУЛЬТАЦИЯ ===
async def handle_consultation_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or update.message.caption or "Файл/Фото"
    
    # Создаем "пустой" заказ типа Консультация
    order_data = {
        'uid': user.id,
        'type': "Консультация",
        'topic': text[:200],
        'deadline': "Не указан",
        'final_price': 0,
        'original_price': 0,
        'points_used': 0,
        'promo_code': None
    }
    oid = await db.create_order(order_data)
    
    # Шлем админу
    msg = f"🆘 <b>ЗАПРОС КОНСУЛЬТАЦИИ #{oid}</b>\n👤 {user.full_name}\n❓ {text}"
    for admin_id in ADMIN_IDS:
        try: await context.bot.send_message(admin_id, msg, parse_mode="HTML")
        except: pass
        
    await update.message.reply_text(
        f"✅ <b>Запрос #{oid} отправлен.</b>\nШериф скоро свяжется с вами.",
        reply_markup=kb.main_kb(user.id),
        parse_mode="HTML"
    )
    return ConversationHandler.END

async def cancel_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _safe_edit(query, "🏠 Возвращаемся в Салун...", reply_markup=kb.main_kb(update.effective_user.id))
    return ConversationHandler.END
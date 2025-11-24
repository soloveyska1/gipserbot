from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from keyboards import menu as kb
from config import SERVICES, URGENCY_MULTIPLIER, MSG_UPSELL, ADMIN_ID

TYPE, TOPIC, DEADLINE, UPSELL, CONFIRM = range(5)

# 1. Выбор типа
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💼 <b>ШАГ 1/4: ОБЪЕКТ РАБОТЫ</b>\nВыберите тип задачи:", 
        reply_markup=kb.services_kb(), parse_mode="HTML"
    )
    return TYPE

# 2. Ввод темы
async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "home": return ConversationHandler.END
    
    sType = query.data.split("_")[1]
    context.user_data['o_type'] = sType
    srv = SERVICES[sType]
    
    await query.edit_message_text(
        f"✅ Выбрано: <b>{srv['name']}</b>\n\n"
        f"📝 <b>ШАГ 2/4: ТЕХНИЧЕСКОЕ ЗАДАНИЕ</b>\n"
        f"Напишите тему работы, прикрепите файл или перешлите сообщение преподавателя.",
        parse_mode="HTML"
    )
    return TOPIC

# 3. Дедлайн (Срочность)
async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ловим текст или файл
    content = update.message.text if update.message.text else "[Вложение/Файл]"
    context.user_data['o_topic'] = content
    
    await update.message.reply_text(
        "⏳ <b>ШАГ 3/4: ФАКТОР ВРЕМЕНИ</b>\n"
        "Насколько критична ситуация?",
        reply_markup=kb.deadlines_kb(), parse_mode="HTML"
    )
    return DEADLINE

# 4. Апселл (Допродажа)
async def get_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    is_urgent = 1 if query.data == "time_urgent" else 0
    context.user_data['o_urgent'] = is_urgent
    
    await query.edit_message_text(MSG_UPSELL, reply_markup=kb.upsell_kb(0), parse_mode="HTML")
    return UPSELL

# 5. Финальный расчет
async def get_upsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    has_upsell = 1 if query.data == "upsell_yes" else 0
    context.user_data['o_upsell'] = has_upsell
    
    # КАЛЬКУЛЯТОР
    data = context.user_data
    base = SERVICES[data['o_type']]['base']
    
    # Наценки
    price = base
    if data['o_urgent']: price *= URGENCY_MULTIPLIER
    if has_upsell: price += 2500
    
    price = int(price) # Округляем
    context.user_data['o_price'] = price
    
    # Формируем красивый чек
    srv_name = SERVICES[data['o_type']]['name']
    urg_txt = "⚡️ СРОЧНО" if data['o_urgent'] else "📅 Стандарт"
    ups_txt = "✅ ВКЛЮЧЕНА" if has_upsell else "❌ Отсутствует"
    
    txt = (
        f"🧾 <b>ПРЕДВАРИТЕЛЬНАЯ СМЕТА</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📎 Услуга: {srv_name}\n"
        f"⏳ Сроки: {urg_txt}\n"
        f"🛡 Защита «Броня»: {ups_txt}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>ИТОГО К ОПЛАТЕ: {price} ₽</b>\n\n"
        f"⚠️ <i>Нажимая «Подтвердить», вы отправляете заявку менеджеру. Оплата производится после согласования деталей.</i>"
    )
    
    await query.edit_message_text(txt, reply_markup=kb.final_confirm_kb(), parse_mode="HTML")
    return CONFIRM

# 6. Отправка
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    d = context.user_data
    
    # Сохраняем в БД
    order_data = {
        'uid': user.id, 'type': d['o_type'], 'topic': d['o_topic'],
        'deadline': "Urgent" if d['o_urgent'] else "Normal",
        'urgent': d['o_urgent'], 'vip': 0, 'upsell': d['o_upsell'],
        'final_price': d['o_price'],
        'original_price': d['o_price'],
        'points_used': 0,
    }
    oid = await db.create_order(order_data)
    
    # Уведомляем Админа (ТЕБЯ)
    adm_msg = (
        f"🚨 <b>НОВАЯ ЗАЯВКА #{oid}</b>\n"
        f"👤: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username})\n"
        f"💵: <b>{d['o_price']} ₽</b>\n"
        f"📝: {d['o_topic']}\n"
        f"⚡️: {d['o_urgent']} | 🛡: {d['o_upsell']}"
    )
    try: await context.bot.send_message(ADMIN_ID, adm_msg, parse_mode="HTML")
    except: pass
    
    await query.edit_message_text(
        f"✅ <b>ЗАЯВКА #{oid} ПРИНЯТА В РАБОТУ</b>\n\n"
        f"Менеджер (Семён Юрьевич) получил уведомление. Ожидайте сообщения в ближайшее время.\n\n"
        f"<i>Совет: Пока ждете, можете скинуть ссылку другу и заработать на его заказе.</i>",
        parse_mode="HTML"
    )
    return ConversationHandler.END
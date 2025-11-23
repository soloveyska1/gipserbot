from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from keyboards import menu as kb
from config import SERVICES, URGENCY_MULTIPLIER, PRICE_SPEECH, PRICE_PRES, PRICE_VIP, ADMIN_IDS

MSG_UPSELL = "🛡 <b>ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА</b>\nХотите добавить броню к вашему заказу?"

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
        reply_markup=kb.deadline_kb(), parse_mode="HTML"
    )
    return DEADLINE

# 4. Апселл (Допродажа)
async def get_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_topic":
        # Возврат назад не реализован для упрощения, просто просим тему заново
        await query.edit_message_text("📝 Введите тему заново:")
        return TOPIC

    is_urgent = 1 if query.data == "time_urgent" else 0
    context.user_data['o_urgent'] = is_urgent
    
    # Инициализируем апселлы
    context.user_data['upsell_speech'] = 0
    context.user_data['upsell_pres'] = 0
    context.user_data['upsell_vip'] = 0

    await query.edit_message_text(
        MSG_UPSELL, 
        reply_markup=kb.upsell_kb(0, 0, 0, PRICE_SPEECH, PRICE_PRES, PRICE_VIP), 
        parse_mode="HTML"
    )
    return UPSELL

# 5. Обработка кнопок апселла и финал
async def get_upsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_deadline":
        await query.edit_message_text("⏳ Выберите срочность:", reply_markup=kb.deadline_kb(), parse_mode="HTML")
        return DEADLINE

    if data == "upsell_done":
        # КАЛЬКУЛЯТОР
        d = context.user_data
        base = SERVICES[d['o_type']]['base']
        
        # Наценки
        price = base
        if d.get('o_urgent'): price *= URGENCY_MULTIPLIER
        
        # Допы
        if d.get('upsell_speech'): price += PRICE_SPEECH
        if d.get('upsell_pres'): price += PRICE_PRES
        if d.get('upsell_vip'): price += PRICE_VIP
        
        price = int(price) # Округляем
        context.user_data['o_price'] = price
        
        # Формируем красивый чек
        srv_name = SERVICES[d['o_type']]['name']
        urg_txt = "⚡️ СРОЧНО" if d.get('o_urgent') else "📅 Стандарт"
        
        # Список допов
        extras = []
        if d.get('upsell_speech'): extras.append("🎤 Речь")
        if d.get('upsell_pres'): extras.append("💻 Презентация")
        if d.get('upsell_vip'): extras.append("👑 VIP")
        extra_txt = ", ".join(extras) if extras else "Нет"
        
        txt = (
            f"🧾 <b>ПРЕДВАРИТЕЛЬНАЯ СМЕТА</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📎 Услуга: {srv_name}\n"
            f"⏳ Сроки: {urg_txt}\n"
            f"➕ Допы: {extra_txt}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>ИТОГО К ОПЛАТЕ: {price} ₽</b>\n\n"
            f"⚠️ <i>Нажимая «Подтвердить», вы отправляете заявку менеджеру. Оплата производится после согласования деталей.</i>"
        )
        await query.edit_message_text(txt, reply_markup=kb.confirm_kb(), parse_mode="HTML")
        return CONFIRM

    # Переключение галочек (Toggle)
    if data.startswith("toggle_"):
        what = data.split("_")[1] # speech, pres, vip
        key = f"upsell_{what}"
        # Инвертируем (0 -> 1, 1 -> 0)
        context.user_data[key] = 1 - context.user_data.get(key, 0)
        
        # Обновляем клавиатуру
        s = context.user_data.get('upsell_speech', 0)
        p = context.user_data.get('upsell_pres', 0)
        v = context.user_data.get('upsell_vip', 0)
        
        await query.edit_message_reply_markup(
            reply_markup=kb.upsell_kb(s, p, v, PRICE_SPEECH, PRICE_PRES, PRICE_VIP)
        )
        return UPSELL

# 6. Отправка
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    d = context.user_data
    
    if query.data == "home":
        await query.edit_message_text("❌ Отменено", reply_markup=kb.main_kb(user.id))
        return ConversationHandler.END

    # Сохраняем в БД
    order_data = {
        'uid': user.id, 'type': d['o_type'], 'topic': d['o_topic'],
        'deadline': "Urgent" if d.get('o_urgent') else "Normal",
        'price': d['o_price']
    }
    oid = await db.create_order(order_data)
    
    # Уведомляем Админов
    adm_msg = (
        f"🚨 <b>НОВАЯ ЗАЯВКА #{oid}</b>\n"
        f"👤: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username})\n"
        f"💵: <b>{d['o_price']} ₽</b>\n"
        f"📝: {d['o_topic']}\n"
        f"⚡️: {d['o_urgent']}"
    )
    for admin_id in ADMIN_IDS:
        try: await context.bot.send_message(admin_id, adm_msg, parse_mode="HTML")
        except: pass
    
    await query.edit_message_text(
        f"✅ <b>ЗАЯВКА #{oid} ПРИНЯТА В РАБОТУ</b>\n\n"
        f"Менеджер (Семён Юрьевич) получил уведомление. Ожидайте сообщения в ближайшее время.\n\n"
        f"<i>Совет: Пока ждете, можете скинуть ссылку другу и заработать на его заказе.</i>",
        parse_mode="HTML"
    )
    return ConversationHandler.END
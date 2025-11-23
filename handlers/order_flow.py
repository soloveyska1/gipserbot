from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from database import pricing as pricing
from keyboards import menu as kb
from config import SERVICES, URGENCY_MULTIPLIER, ADMIN_IDS

MSG_UPSELL = "🛡 <b>ДОПОЛНИТЕЛЬНАЯ ЗАЩИТА</b>\nХотите добавить броню к вашему заказу?"

TYPE, TOPIC, DEADLINE, UPSELL, PAY_CHOICE, CONFIRM = range(6)


async def _safe_edit(query, text, **kwargs):
    msg = query.message
    try:
        if msg and msg.text:
            return await query.edit_message_text(text, **kwargs)
        if msg and msg.caption:
            return await query.edit_message_caption(caption=text, **kwargs)
    except BadRequest as exc:
        if "not modified" in str(exc).lower():
            return msg
    return await query.message.reply_text(text, **kwargs)


def _calc_points_offer(price: int, balance: int):
    max_discount = int(price * 0.5)
    points_to_spend = min(balance, max_discount)
    final_price = max(price - points_to_spend, 0)
    return points_to_spend, final_price


async def _show_confirm(query, context):
    d = context.user_data
    srv_name = SERVICES[d['o_type']]['name']
    urg_txt = "⚡️ СРОЧНО" if d.get('o_urgent') else "📅 Стандарт"
    extra_txt = ", ".join(d.get('o_extras', [])) if d.get('o_extras') else "Нет"
    original_price = d.get('original_price', d.get('o_price', 0))
    points_used = d.get('points_used', 0)
    final_price = d.get('final_price', original_price)

    txt = (
        f"🧾 <b>ПРЕДВАРИТЕЛЬНАЯ СМЕТА</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📎 Услуга: {srv_name}\n"
        f"⏳ Сроки: {urg_txt}\n"
        f"➕ Допы: {extra_txt}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 База: {original_price} ₽\n"
        f"💎 Списываем баллы: -{points_used}\n"
        f"<b>ИТОГО К ОПЛАТЕ: {final_price} ₽</b>\n\n"
        f"⚠️ <i>Нажимая «Подтвердить», вы отправляете заявку менеджеру. Оплата производится после согласования деталей.</i>"
    )
    await _safe_edit(query, txt, reply_markup=kb.confirm_kb(), parse_mode="HTML")
    return CONFIRM

# 1. Выбор типа
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = await db.get_user(query.from_user.id)
    if not user or not user.get("agreed_to_rules"):
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=(
                "📜 Сначала ознакомься с Кодексом Чести салуна и подтверди согласие."
            ),
            reply_markup=kb.rules_accept_kb(),
            parse_mode="HTML",
        )
        return ConversationHandler.END
    await _safe_edit(
        query,
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
    
    await _safe_edit(
        query,
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
        await _safe_edit(query, "📝 Введите тему заново:")
        return TOPIC

    is_urgent = 1 if query.data == "time_urgent" else 0
    context.user_data['o_urgent'] = is_urgent
    
    # Инициализируем апселлы
    context.user_data['upsell_speech'] = 0
    context.user_data['upsell_pres'] = 0
    context.user_data['upsell_vip'] = 0

    speech_price = await pricing.get_price("speech")
    pres_price = await pricing.get_price("pres")
    vip_price = await pricing.get_price("vip")
    context.user_data['price_speech'] = speech_price
    context.user_data['price_pres'] = pres_price
    context.user_data['price_vip'] = vip_price

    await _safe_edit(
        query,
        MSG_UPSELL,
        reply_markup=kb.upsell_kb(0, 0, 0, speech_price, pres_price, vip_price),
        parse_mode="HTML"
    )
    return UPSELL

# 5. Обработка кнопок апселла и финал
async def get_upsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_deadline":
        await _safe_edit(query, "⏳ Выберите срочность:", reply_markup=kb.deadline_kb(), parse_mode="HTML")
        return DEADLINE

    if data == "upsell_done":
        # КАЛЬКУЛЯТОР
        d = context.user_data
        base = await pricing.get_price(f"srv_{d['o_type']}")
        
        # Наценки
        price = base
        if d.get('o_urgent'): price *= URGENCY_MULTIPLIER
        
        # Допы
        speech_price = d.get('price_speech') or await pricing.get_price("speech")
        pres_price = d.get('price_pres') or await pricing.get_price("pres")
        vip_price = d.get('price_vip') or await pricing.get_price("vip")

        if d.get('upsell_speech'): price += speech_price
        if d.get('upsell_pres'): price += pres_price
        if d.get('upsell_vip'): price += vip_price
        
        price = int(price) # Округляем
        context.user_data['o_price'] = price

        # Список допов
        extras = []
        if d.get('upsell_speech'): extras.append("🎤 Речь")
        if d.get('upsell_pres'): extras.append("💻 Презентация")
        if d.get('upsell_vip'): extras.append("👑 VIP")
        d['o_extras'] = extras
        d['original_price'] = price
        d['points_used'] = 0
        d['final_price'] = price

        user = await db.get_user(query.from_user.id)
        if user and user.get('balance', 0) > 0:
            points_to_spend, final_price = _calc_points_offer(price, user.get('balance', 0))
            d['final_price'] = final_price
            d['points_offer'] = points_to_spend
            txt_points = (
                "💰 <b>Использовать баллы?</b>\n"
                f"Цена заказа: {price} ₽\n"
                f"Твой баланс: {user['balance']}\n"
                f"Можем списать: {points_to_spend} (до 50%)\n"
                f"<b>К оплате будет: {final_price} ₽</b>"
            )
            await _safe_edit(
                query,
                txt_points,
                reply_markup=kb.points_choice_kb(points_to_spend),
                parse_mode="HTML",
            )
            return PAY_CHOICE

        return await _show_confirm(query, context)

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
        
        speech_price = context.user_data.get('price_speech') or await pricing.get_price("speech")
        pres_price = context.user_data.get('price_pres') or await pricing.get_price("pres")
        vip_price = context.user_data.get('price_vip') or await pricing.get_price("vip")

        await query.edit_message_reply_markup(
            reply_markup=kb.upsell_kb(s, p, v, speech_price, pres_price, vip_price)
        )
        return UPSELL

# 5b. Выбор оплаты баллами
async def handle_payment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = context.user_data
    price = d.get('original_price', d.get('o_price', 0))

    if query.data == "use_points_yes":
        user = await db.get_user(query.from_user.id)
        balance = user.get('balance', 0) if user else 0
        points_to_spend, final_price = _calc_points_offer(price, balance)
        if points_to_spend <= 0:
            d['points_used'] = 0
            d['final_price'] = price
            return await _show_confirm(query, context)

        await db.adjust_balance(query.from_user.id, -points_to_spend, "Оплата баллами")
        d['points_used'] = points_to_spend
        d['final_price'] = final_price
    else:
        d['points_used'] = 0
        d['final_price'] = price

    return await _show_confirm(query, context)


# 6. Отправка
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    d = context.user_data

    if query.data == "home":
        await _safe_edit(query, "❌ Отменено", reply_markup=kb.main_kb(user.id))
        return ConversationHandler.END

    original_price = d.get('original_price', d.get('o_price'))
    points_used = d.get('points_used', 0)
    final_price = d.get('final_price', original_price)

    # Сохраняем в БД
    order_data = {
        'uid': user.id, 'type': d['o_type'], 'topic': d['o_topic'],
        'deadline': "Urgent" if d.get('o_urgent') else "Normal",
        'final_price': final_price,
        'original_price': original_price,
        'points_used': points_used,
    }
    oid = await db.create_order(order_data)

    # Уведомляем Админов
    adm_msg = (
        f"🚨 <b>НОВАЯ ЗАЯВКА #{oid}</b>\n"
        f"👤: <a href='tg://user?id={user.id}'>{user.full_name}</a> (@{user.username})\n"
        f"💵: <b>{final_price} ₽</b> (база {original_price}₽, баллы -{points_used})\n"
        f"📝: {d['o_topic']}\n"
        f"⚡️: {d['o_urgent']}"
    )
    for admin_id in ADMIN_IDS:
        try: await context.bot.send_message(admin_id, adm_msg, parse_mode="HTML")
        except: pass

    await _safe_edit(
        query,
        f"✅ <b>ЗАЯВКА #{oid} ПРИНЯТА В РАБОТУ</b>\n\n"
        f"Менеджер (Семён Юрьевич) получил уведомление. Ожидайте сообщения в ближайшее время.\n\n"
        f"<i>Совет: Пока ждете, можете скинуть ссылку другу и заработать на его заказе.</i>",
        parse_mode="HTML",
    )
    return ConversationHandler.END

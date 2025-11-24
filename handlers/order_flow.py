import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from database import db as catalog_db
from keyboards import client_kb as kb
from keyboards import builders as build
from config import SERVICES, ADMIN_IDS
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
    if query:
        await query.answer()

    # Сбрасываем данные заказа
    context.user_data['order'] = {}

    services = await catalog_db.get_all_services()
    if not services:
        txt = "⚠️ Сейчас нет доступных услуг. Напишите шерифу."
        if query:
            await _safe_edit(query, txt, reply_markup=kb.main_kb(update.effective_user.id))
        else:
            await update.message.reply_text(txt, reply_markup=kb.main_kb(update.effective_user.id))
        return ConversationHandler.END

    menu_text = (
        "Бар открыт. Стволы смазаны. Что будем готовить сегодня, партнер? "
        "Выбирай калибр. У нас есть всё: от легких эссе до тяжелой артиллерии."
    )

    chat_id = update.effective_chat.id
    await context.bot.send_photo(
        chat_id,
        photo="AgACAgIAAxkBAAEFG0hpI9Pfsi5VGfwKuZSrGQFsslxf0wACeQtrG_RHIEk67aeU_toGxwEAAwIAA3kAAzYE",
        caption=None,
    )

    await context.bot.send_message(
        chat_id,
        menu_text,
        reply_markup=build.order_showcase_kb(services),
    )
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

    return await confirm_service(update, context)

async def confirm_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_services":
        return await start_order(update, context)

    txt = (
        "🎯 ДОСЬЕ НА ЦЕЛЬ\n\n"
        "Принимаю данные в любом виде. Не трать время на перепечатку.\n\n"
        "📥 Кидай сюда:\n"
        "• 🎙 Голосовое (расскажи суть)\n"
        "• 📸 Фото (методички, записки)\n"
        "• 🔄 Пересланные сообщения\n"
        "• 📎 Файлы (Word/PDF)\n\n"
        "👇 Жду улики..."
    )

    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🤷‍♂️ У меня нет темы (Помощь)", callback_data="topic_help")],
            [InlineKeyboardButton("🔙 Назад к выбору услуги", callback_data="back_to_services")],
        ]
    )

    await _safe_edit(query, txt, reply_markup=markup)
    return TOPIC

async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query and update.callback_query.data == "topic_help":
        await update.callback_query.answer()
        context.user_data['order']['topic'] = "⚠️ НУЖЕН МОЗГОВОЙ ШТУРМ (Подбор темы)"
        context.user_data['order']['source'] = "help_needed"
        context.user_data['order']['topic_source'] = "help_needed"
        await _safe_edit(
            update.callback_query,
            "👌 Принято. Улики подшиты к делу.\n\nПосмотри на календарь. Насколько сильно горят мосты?",
            reply_markup=build.deadline_heat_kb(),
        )
        return DEADLINE

    msg = update.message
    o = context.user_data.setdefault('order', {})
    o['source'] = "organic"

    if msg.voice:
        o['voice_id'] = msg.voice.file_id
        o['topic'] = "🎤 Голосовое сообщение"
        o['topic_source'] = "voice"
    elif msg.document or msg.photo:
        o.setdefault('files', [])
        fid = msg.document.file_id if msg.document else msg.photo[-1].file_id
        o['files'].append(fid)
        o['topic'] = o.get('topic', "📎 Файлы/Материалы")
        o['topic_source'] = "files"
    elif msg.text:
        o['topic'] = msg.text
        o['topic_source'] = "text"

    await msg.reply_text(
        "👌 Принято! Улики подшиты к делу.\n\nПосмотри на календарь. Насколько сильно горят мосты?",
        reply_markup=build.deadline_heat_kb(),
    )
    return DEADLINE
# === 4. ДЕДЛАЙН ===
async def get_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_topic":
        await _safe_edit(
            query,
            "🎯 ДОСЬЕ НА ЦЕЛЬ\n\nПринимаю данные в любом виде. Не трать время на перепечатку.\n\n📥 Кидай сюда:\n• 🎙 Голосовое (расскажи суть)\n• 📸 Фото (методички, записки)\n• 🔄 Пересланные сообщения\n• 📎 Файлы (Word/PDF)\n\n👇 Жду улики...",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🤷‍♂️ У меня нет темы (Помощь)", callback_data="topic_help")],
                    [InlineKeyboardButton("🔙 Назад к выбору услуги", callback_data="back_to_services")],
                ]
            ),
        )
        return TOPIC

    choice = query.data
    multiplier = 1.0
    deadline_label = "🐢 ЗАРАНЕЕ (Неделя+)"
    if choice == "deadline_hot":
        multiplier = 1.4
        deadline_label = "🔥 ОГОНЬ (1-3 дня)"
    elif choice == "deadline_fast":
        multiplier = 1.15
        deadline_label = "⚡️ В ТЕМПЕ (4-7 дней)"

    o = context.user_data['order']
    o['deadline_text'] = deadline_label
    o['deadline_multiplier'] = multiplier

    # Инициализация допов
    context.user_data['order']['upsells'] = {'speech': False, 'pres': False, 'vip': False}

    await _update_upsell_message(query, context)
    return UPSELL

# === 5. UPSELL (ДОПЫ) ===
async def _update_upsell_message(query, context):
    ups = context.user_data['order']['upsells']
    base = context.user_data['order']['base_price']
    multiplier = context.user_data['order'].get('deadline_multiplier', 1.0)

    extras = 0
    extras += 2500 if ups.get('vip') else 0
    extras += 1500 if ups.get('speech') else 0
    extras += 2000 if ups.get('pres') else 0

    subtotal = int(base * multiplier)
    current_total = subtotal + extras

    txt = (
        f"🧳 СБОРКА ИНВЕНТАРЯ\n\n"
        f"Базовая цена: {base} ₽\n"
        f"Срочность: {multiplier}x\n\n"
        f"💰 ТЕКУЩАЯ СУММА: {current_total} ₽\n\n"
        f"👇 Добавь патронов:"
    )

    await _safe_edit(query, txt, reply_markup=build.upsell_toggle_kb(ups))

async def get_upsell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_to_deadline":
        await _safe_edit(query, "Посмотри на календарь. Насколько сильно горят мосты?", reply_markup=build.deadline_heat_kb())
        return DEADLINE

    ups = context.user_data['order']['upsells']
    if data == "upsell_done":
        return await _prepare_payment_step(query, context)
    elif data == "upsell_toggle_vip":
        ups['vip'] = not ups.get('vip', False)
    elif data == "upsell_toggle_speech":
        ups['speech'] = not ups.get('speech', False)
    elif data == "upsell_toggle_pres":
        ups['pres'] = not ups.get('pres', False)

    await _update_upsell_message(query, context)
    return UPSELL

# === 6. РАСЧЕТ И ОПЛАТА ===
async def _prepare_payment_step(query, context):
    o = context.user_data['order']
    base = o['base_price']
    multiplier = o.get('deadline_multiplier', 1.0)
    ups = o.get('upsells', {})

    extras = 0
    extras += 2500 if ups.get('vip') else 0
    extras += 1500 if ups.get('speech') else 0
    extras += 2000 if ups.get('pres') else 0

    subtotal = int(base * multiplier)
    total = subtotal + extras
    o['price_calculated'] = total
    o['final_price'] = total
    o['points_used'] = 0

    user_db = await db.get_user(query.from_user.id)
    balance = int(user_db.get('balance', 0))
    max_discount = int(total * 0.5)

    o['can_use_points'] = min(balance, max_discount)
    o['balance'] = balance
    o['max_discount'] = max_discount

    text = (
        f"💳 КАССА\n\n"
        f"К оплате: {total} ₽\n"
        f"Твой баланс: 💎 {balance}\n"
        f"Можно списать до: 💎 {max_discount}\n\n"
        f"Сколько спишем?"
    )

    await _safe_edit(query, text, reply_markup=build.payment_smart_kb(balance, max_discount))
    context.user_data['awaiting_custom_points'] = False
    return PAY_CHOICE

async def handle_payment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    o = context.user_data['order']

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data

        if data == "pay_custom":
            context.user_data['awaiting_custom_points'] = True
            await _safe_edit(query, "Введи сумму списания (не больше 50% и не больше баланса):")
            return PAY_CHOICE
        elif data == "pay_skip":
            o['points_used'] = 0
        elif data == "pay_all":
            o['points_used'] = min(o.get('balance', 0), o.get('max_discount', 0))
        elif data.startswith("pay_minus_"):
            step = int(data.split("_")[-1])
            o['points_used'] = min(step, o.get('balance', 0), o.get('max_discount', 0))

        o['final_price'] = o['price_calculated'] - o.get('points_used', 0)
        return await confirm_order_view(query, context)

    msg = update.message
    if context.user_data.get('awaiting_custom_points') and msg and msg.text:
        try:
            value = int(msg.text.strip())
        except ValueError:
            await msg.reply_text("Введите число в рублях/баллах.")
            return PAY_CHOICE

        max_allowed = min(o.get('balance', 0), o.get('max_discount', 0))
        if value < 0 or value > max_allowed:
            await msg.reply_text(f"Нельзя списать больше {max_allowed} или меньше 0. Попробуй снова.")
            return PAY_CHOICE

        o['points_used'] = value
        o['final_price'] = o['price_calculated'] - value
        context.user_data['awaiting_custom_points'] = False
        await msg.reply_text("Списываем 💎 и готовим чек...")
        return await confirm_order_view(msg, context)

    await msg.reply_text("Выберите вариант на клавиатуре.")
    return PAY_CHOICE

async def confirm_order_view(trigger, context):
    o = context.user_data['order']

    ups_text = []
    if o['upsells'].get('vip'): ups_text.append("VIP")
    if o['upsells'].get('speech'): ups_text.append("Речь")
    if o['upsells'].get('pres'): ups_text.append("Презентация")
    ups_str = ", ".join(ups_text) if ups_text else "Нет"

    topic_preview = o.get('topic', '—')
    if len(topic_preview) > 50:
        topic_preview = topic_preview[:50] + "..."

    txt = "\n".join(
        [
            f"🧾 <b>КВИТАНЦИЯ #DRAFT-{trigger.from_user.id}</b>",
            "<pre>",
            f"УСЛУГА:.......{o['service_name']}",
            f"СРОЧНОСТЬ:....{o['deadline_text']}",
            f"ДОПЫ:.........{ups_str}",
            "------------------------------",
            f"ПОДЫТОГ:......{o['price_calculated']} ₽",
            f"СКИДКА:.......-{o.get('points_used', 0)} ₽",
            "==============================",
            f"ИТОГО:        {o['price_calculated'] - o.get('points_used', 0)} ₽",
            "</pre>",
            "⚠️ <i>Нажимая кнопку, вы заключаете джентльменское соглашение.</i>",
        ]
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✍️ ПОДПИСАТЬ КОНТРАКТ", callback_data="submit_order")]])
    if hasattr(trigger, "callback_query") or hasattr(trigger, "edit_message_text"):
        await _safe_edit(trigger, txt, reply_markup=markup, parse_mode="HTML")
    else:
        await trigger.reply_text(txt, reply_markup=markup, parse_mode="HTML")
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
        'topic_source': o.get('topic_source', ''),
        'voice_id': o.get('voice_id', ''),
        'files': o.get('files', []),
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

    final_text = (
        "🤝 Сделка скреплена!\n\n"
        f"Заказ #{oid} лежит на столе у менеджера. В течение 15 минут он постучится к тебе в личку.\n\n"
        "Пока ждешь, можешь расслабиться:"
    )

    final_kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎰 Испытать удачу", callback_data="daily_bonus")],
            [InlineKeyboardButton("💬 Чат заказа", callback_data=f"chat_order_{oid}")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="home")],
        ]
    )

    await _safe_edit(query, final_text, reply_markup=final_kb)
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
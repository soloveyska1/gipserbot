import asyncio
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from keyboards import menu as kb
from config import REVIEW_CHANNEL_ID
import utils  # Подключаем твои новые утилиты

# ТВОЯ НОВАЯ КАРТИНКА (САЛУН)
WELCOME_PHOTO_ID = "AgACAgIAAxkBAAIRBGkf3jybt7UiWBtsS4itzUfhWvceAALIC2sb7NgAAUkgNJP7MzMPsAEAAwIAA3kAAzYE"

# Состояние для отзыва
REVIEW_STATE = 1

CODE_OF_HONOR = (
    "📜 <b>КОДЕКС ЧЕСТИ САЛУНА</b>\n"
    "1. <b>Правки:</b> 3 пакета правок включены в цену (до сдачи научнику). Остальное — за доплату. Срок давности — 6 месяцев.\n"
    "2. <b>Возврат:</b> Возврат только если работа НЕ написана. Оценка на защите зависит от тебя. Претензии «Я получил 4, а хотел 5» не принимаются.\n"
    "3. <b>Антиплагиат:</b> Мы НЕ загружаем работу в вузовские системы (чтобы не было «дубля»). Если процент низкий — пришли PDF-отчет, перепишем бесплатно.\n"
    "4. <b>Сроки:</b> В сезон Шериф может отвечать не сразу. Не паникуй.\n"
    "5. <b>Анонимность:</b> Всё строго между нами."
)


async def _safe_edit(query, text, **kwargs):
    msg = query.message
    try:
        if msg and msg.text:
            return await query.edit_message_text(text, **kwargs)
        if msg and msg.caption:
            return await query.edit_message_caption(caption=text, **kwargs)
    except BadRequest as exc:
        # Игнорируем попытку редактирования неизменённого/неподходящего сообщения
        if "not modified" in str(exc).lower():
            return msg
    return await query.message.reply_text(text, **kwargs)


async def _send_rules_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await utils.send_typing(context, chat_id)
    await asyncio.sleep(1.5)
    if update.callback_query:
        await update.callback_query.answer()
    await context.bot.send_message(
        chat_id=chat_id,
        text=CODE_OF_HONOR,
        reply_markup=kb.rules_accept_kb(),
        parse_mode="HTML",
    )


async def _ensure_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await db.get_user(update.effective_user.id)
    if not user:
        return False
    if user.get("is_banned"):
        if update.effective_message:
            await update.effective_message.reply_text(
                "⛔️ Шериф закрыл двери салуна для этого ковбоя.", parse_mode="HTML"
            )
        return False
    if not user.get("agreed_to_rules"):
        await _send_rules_prompt(update, context)
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Имитация живого общения (печатает...)
    await utils.send_typing(context, update.effective_chat.id)
    await asyncio.sleep(1.5)

    args = context.args
    ref_id = int(args[0]) if args and args[0].isdigit() else 0

    is_new = await db.add_user(user.id, user.username, user.full_name, ref_id)
    if is_new and ref_id:
        try: await context.bot.send_message(ref_id, f"🤠 <b>Гость в салуне:</b> {user.full_name}")
        except: pass

    # ДИНАМИЧЕСКОЕ ПРИВЕТСТВИЕ (из utils.py)
    greeting = utils.get_greeting(user.first_name)

    caption = (
        f"{greeting}\n\n"
        "Вижу, ты устал с дороги. Эта академическая пустыня кого угодно сведет с ума. "
        "Дедлайны палят как солнце, а преподы злее гремучих змей.\n\n"
        "Паркуй лошадь и расслабься. Ты в <b>«Экспресс-Курсаче»</b>. "
        "Здесь джентльмены решают вопросы, пока ты пьешь свой виски и наслаждаешься жизнью.\n\n"
        "👇 <b>Что нальем для храбрости?</b>"
    )

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.message.delete()
        except:
            pass

        await context.bot.send_photo(
            chat_id=user.id,
            photo=WELCOME_PHOTO_ID,
            caption=caption,
            reply_markup=kb.main_kb(user.id),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_photo(
            photo=WELCOME_PHOTO_ID,
            caption=caption,
            reply_markup=kb.main_kb(user.id),
            parse_mode="HTML",
        )

    profile = await db.get_user(user.id)
    if not profile.get("agreed_to_rules"):
        await _send_rules_prompt(update, context)


async def accept_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.update_user_field(query.from_user.id, "agreed_to_rules", 1)
    await utils.send_typing(context, query.message.chat_id)
    await asyncio.sleep(1.5)
    await _safe_edit(
        query,
        "🤝 Шериф записал твое согласие. Добро пожаловать в салун!",
        reply_markup=kb.main_kb(query.from_user.id),
        parse_mode="HTML",
    )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END
    
    u = await db.get_user(query.from_user.id)
    if not u: return await start(update, context)
    
    txt = (
        f"👤 <b>ЛИЧНОЕ ДЕЛО</b>\n"
        f"🆔 ID: <code>{u['user_id']}</code>\n"
        f"💰 Баланс: <b>{u['balance']} ₽</b>\n"
        f"💸 Инвестировано в спокойствие: {u['total_spent']} ₽"
    )
    await _safe_edit(query, txt, reply_markup=kb.profile_kb(), parse_mode="HTML")

async def partners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END
    bot = await context.bot.get_me()
    link = f"https://t.me/{bot.username}?start={query.from_user.id}"
    text = (
        "🕸 <b>ЗОЛОТАЯ ЖИЛА</b>\n\n"
        "Приведи друга в Салун — получи <b>15%</b> от его золота (заказов).\n\n"
        "👇 <b>Твоя ссылка:</b>\n"
        f"<code>{link}</code>\n\n"
        "<i>Раздай её в универе.</i>"
    )
    await _safe_edit(query, text, reply_markup=kb.back_kb("home"), parse_mode="HTML")

async def my_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END
    orders = await db.get_user_orders(query.from_user.id)
    if not orders:
        await _safe_edit(query, "📂 <b>Архив пуст.</b>", reply_markup=kb.profile_kb(), parse_mode="HTML")
    else:
        await _safe_edit(query, "📂 <b>ВАШИ ДЕЛА:</b>", reply_markup=kb.history_kb(orders), parse_mode="HTML")

async def my_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    oid = int(query.data.split("_")[-1])
    o = await db.get_order(oid)
    status_map = {
        "checking": "🟡 На проверке",
        "work": "⚙️ В работе",
        "done": "✅ Готов",
        "cancel": "❌ Отмена",
    }
    txt = (
        f"📦 <b>ЗАКАЗ #{o['id']}</b>\n"
        f"📚 Тип: {o['service_type']}\n"
        f"💰 Цена: {o['price']} ₽\n"
        f"📊 Статус: {status_map.get(o['status'], o['status'])}\n"
        f"📝 Тема: {o['topic']}"
    )
    await _safe_edit(query, txt, reply_markup=kb.order_details_kb(oid, o['status']), parse_mode="HTML")

async def my_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    trans = await db.get_transactions(query.from_user.id)
    if not trans:
        return await _safe_edit(query, "💳 <b>Транзакций нет.</b>", reply_markup=kb.back_kb("profile"), parse_mode="HTML")
    txt = "💳 <b>ИСТОРИЯ ОПЕРАЦИЙ:</b>\n\n"
    for t in trans:
        sign = "+" if t['amount'] > 0 else ""
        txt += f"📅 {t['date'][:16]}\n💴 <b>{sign}{t['amount']} ₽</b> ({t['reason']})\n\n"
    await _safe_edit(query, txt, reply_markup=kb.back_kb("profile"), parse_mode="HTML")

# --- ОТЗЫВЫ ---
async def ask_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _safe_edit(
        query,
        "✍️ <b>Напиши пару слов:</b>\n\nМы прибьем твой отзыв на доску почета (в канал) анонимно.\nКидай текст или скрин.",
        reply_markup=kb.back_kb("home"),
        parse_mode="HTML"
    )
    return REVIEW_STATE

async def submit_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.caption if update.message.caption else update.message.text
    if not text: text = "Без текста"
    
    await db.add_review(user.id, text)
    
    channel_text = (
        "🌵 <b>ВЕСТОЧКА ИЗ САЛУНА</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"{text}\n"
        "━━━━━━━━━━━━━━\n"
        "<i>#отзыв #syndicate</i>"
    )
    
    try:
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            await context.bot.send_photo(chat_id=REVIEW_CHANNEL_ID, photo=file_id, caption=channel_text, parse_mode="HTML")
        else:
            await context.bot.send_message(chat_id=REVIEW_CHANNEL_ID, text=channel_text, parse_mode="HTML")
        
        # Используем рандомную фразу из utils
        thanks_text = "✅ " + utils.get_random_phrase("done") + "\n\nВаш отзыв опубликован."
        await update.message.reply_text(thanks_text, reply_markup=kb.main_kb(user.id), parse_mode="HTML")
    except Exception as e:
        # ВАЖНО: Если бот не админ в канале, он напишет ошибку здесь
        await update.message.reply_text(f"❌ Ошибка шерифа (права в канале): {e}", reply_markup=kb.main_kb(user.id))
    return ConversationHandler.END

# --- ДЕЙСТВИЯ ---
async def cli_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    oid = int(query.data.split("_")[-1])
    await db.update_order_status(oid, "done")
    await query.answer("✅ Заказ подтвержден!")
    await my_order(update, context)

async def cli_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    oid = int(query.data.split("_")[-1])
    await db.update_order_visibility(oid, False)
    await query.answer("🗑 Удалено")
    await my_history(update, context)

async def handle_thanks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text.lower()
    keywords = ["спасибо", "спс", "благодарю", "thanks"]
    if any(word in text for word in keywords):
        try: await update.message.set_reaction("🥃")
        except: pass
        await update.message.reply_text("🤝 Всегда пожалуйста, партнер.")

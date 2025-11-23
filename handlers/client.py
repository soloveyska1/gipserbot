import asyncio
from typing import Any

from telegram import Update, CallbackQuery
from telegram.ext import ConversationHandler

from database import core as db
from database import db as catalog_db
from keyboards import client_kb as kb
from keyboards import builders
from config import REVIEW_CHANNEL_ID
import utils  # Подключаем твои новые утилиты

# ТВОЯ НОВАЯ КАРТИНКА (САЛУН)
WELCOME_PHOTO_ID = "AgACAgIAAxkBAAIRBGkf3jybt7UiWBtsS4itzUfhWvceAALIC2sb7NgAAUkgNJP7MzMPsAEAAwIAA3kAAzYE"

# Состояния диалогов
REVIEW_STATE = 1
PROMO_STATE = 2

CODE_OF_HONOR = (
    "⚖️ <b>КОДЕКС ЧЕСТИ САЛУНА</b>\n\n"
    "1. <b>Репутация на Диком Западе.</b>\n"
    "Нам доверяют уже более <b>1000 партнеров</b>. Мы в этом городе надолго, и наше слово крепче виски.\n\n"
    "2. <b>Три полных обоймы (Правки).</b>\n"
    "В стоимость включено <b>3 пакета бесплатных правок</b>. Обычно этого хватает, чтобы уложить любого препода наповал. Если потребуется больше — обсудим по-джентльменски.\n\n"
    "3. <b>Твоя безопасность (Антиплагиат).</b>\n"
    "Мы <b>НЕ</b> загружаем твою работу в системы проверки (Антиплагиат.ру и др.).\n"
    "<i>Почему?</i> Чтобы не подставить тебя. Если мы проверим её раньше времени, система поставит метку 'Дубликат', и ты не пройдешь проверку в ВУЗе.\n"
    "Твой 'ствол' должен выстрелить только один раз — на защите.\n\n"
    "4. <b>Анонимность.</b>\n"
    "Никто не узнает, что мы вели дела. Тайна переписки охраняется законом прерий."
)


class _StateWrapper:
    def __init__(self, context: Any):
        self.context = context

    async def clear(self):
        try:
            self.context.user_data.clear()
        except Exception:
            pass
        try:
            self.context.chat_data.clear()
        except Exception:
            pass


async def _safe_edit(query: CallbackQuery, text: str, **kwargs):
    msg = query.message
    try:
        if msg and msg.text:
            return await query.edit_message_text(text, **kwargs)
        if msg and msg.caption:
            return await query.edit_message_caption(caption=text, **kwargs)
    except Exception as exc:
        # Игнорируем попытку редактирования неизменённого/неподходящего сообщения
        if "not modified" in str(exc).lower() or "message is not modified" in str(exc).lower():
            return msg
        raise
    return await query.message.reply_text(text, **kwargs)


_RANKS = [
    {"threshold": 0, "name": "🤠 Новичок", "next_threshold": 5000},
    {"threshold": 5000, "name": "🎓 Профи", "next_threshold": 20000},
    {"threshold": 20000, "name": "📚 Власть Академии", "next_threshold": None},
]


def _rank_progress(total_spent: int) -> tuple[str, int | None, int, str]:
    current = _RANKS[0]
    for rank in _RANKS:
        if total_spent >= rank["threshold"]:
            current = rank

    next_threshold = current["next_threshold"]
    if next_threshold is None:
        progress_ratio = 1.0
        amount_needed = 0
    else:
        span = next_threshold - current["threshold"]
        progress_ratio = min(1.0, max(0.0, (total_spent - current["threshold"]) / span))
        amount_needed = max(0, next_threshold - total_spent)

    filled = min(10, max(0, int(round(progress_ratio * 10))))
    progress_bar = f"[{'■' * filled}{'□' * (10 - filled)}]"

    return current["name"], next_threshold, amount_needed, progress_bar


async def _send_rules_prompt(update: Update, context: Any):
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


async def _ensure_rules(update: Update, context: Any):
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

async def start(update: Update, context: Any):
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


async def accept_rules(update: Update, context: Any):
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


async def profile(update: Update, context: Any):
    query = update.callback_query
    await query.answer()

    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END

    u = await db.get_user(query.from_user.id)
    if not u: return await start(update, context)

    total_spent = u.get("total_spent", 0) or 0
    rank_name, _, amount_needed, progress_bar = _rank_progress(total_spent)

    txt = (
        f"👤 <b>ЛИЧНОЕ ДЕЛО</b>\n"
        f"🆔 ID: <code>{u['user_id']}</code>\n\n"
        f"💰 <b>Золотой запас:</b> {u['balance']} RUB\n"
        f"🏆 <b>Ранг:</b> {rank_name}\n"
        f"📊 <b>Прогресс:</b> {progress_bar}\n"
        f"До следующего звания: {amount_needed} RUB\n\n"
        f"<i>Всего инвестировано в спокойствие: {total_spent} RUB</i>"
    )
    await _safe_edit(query, txt, reply_markup=kb.profile_kb(), parse_mode="HTML")


async def ask_promo_code(update: Update, context: Any):
    query = update.callback_query
    await query.answer()

    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END

    prompt = (
        "🎟 <b>Есть промокод?</b>\n"
        "Введи его ниже, чтобы пополнить баланс салуна."
    )
    await _safe_edit(query, prompt, reply_markup=kb.back_kb("open_profile"), parse_mode="HTML")
    return PROMO_STATE


async def submit_promo_code(update: Update, context: Any):
    user = update.effective_user
    code = (update.message.text or "").strip()
    if not code:
        await update.message.reply_text(
            "Введите текст промокода, партнер.",
            reply_markup=kb.back_kb("open_profile"),
            parse_mode="HTML",
        )
        return PROMO_STATE

    promo = await catalog_db.apply_promo_to_user(user.id, code)
    if not promo:
        await update.message.reply_text(
            "❌ Промокод не найден, истек или уже использован.",
            reply_markup=kb.back_kb("open_profile"),
            parse_mode="HTML",
        )
        return PROMO_STATE

    await update.message.reply_text(
        "💰 Промокод принят! Твой баланс пополнен.",
        reply_markup=kb.profile_kb(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def _render_price_menu(update: Update, context: Any, via_callback: bool = False):
    services = await catalog_db.get_all_services()
    if not services:
        if via_callback and update.callback_query:
            return await _safe_edit(
                update.callback_query,
                "⚠️ Технический перерыв: список услуг пуст. Сообщите шерифу.",
                reply_markup=kb.back_kb("home"),
            )
        return await update.message.reply_text(
            "⚠️ Технический перерыв: список услуг пуст. Сообщите шерифу.",
            reply_markup=kb.back_kb("home"),
        )

    text = "📜 <b>Прейскурант Салуна</b>\nНиже наши расценки, партнер."
    markup = builders.create_dynamic_service_keyboard(
        services,
        prefix="price_srv_",
        back_cb="back_to_main_menu",
        back_text="🏠 В главное меню",
    )

    if via_callback and update.callback_query:
        return await _safe_edit(
            update.callback_query, text, reply_markup=markup, parse_mode="HTML"
        )
    return await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def show_price_list(update: Update, context: Any):
    query = update.callback_query
    await query.answer()
    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END

    services = await catalog_db.get_all_services()
    text = "📜 <b>Прейскурант Салуна</b>\nНиже наши расценки, партнер."

    if not services:
        empty_text = "⚠️ Технический перерыв: список услуг пуст. Сообщите шерифу."
        if query.message and query.message.photo:
            await query.message.delete()
            return await query.message.reply_text(
                text=empty_text, reply_markup=kb.back_kb("home"), parse_mode="HTML"
            )
        try:
            return await query.message.edit_text(
                text=empty_text, reply_markup=kb.back_kb("home"), parse_mode="HTML"
            )
        except Exception:
            return await query.message.reply_text(
                text=empty_text, reply_markup=kb.back_kb("home"), parse_mode="HTML"
            )

    markup = builders.create_dynamic_service_keyboard(
        services,
        prefix="price_srv_",
        back_cb="back_to_main_menu",
        back_text="🏠 В главное меню",
    )

    if query.message and query.message.photo:
        await query.message.delete()
        return await query.message.reply_text(
            text=text, reply_markup=markup, parse_mode="HTML"
        )

    try:
        return await query.message.edit_text(
            text=text, reply_markup=markup, parse_mode="HTML"
        )
    except Exception:
        return await query.message.reply_text(
            text=text, reply_markup=markup, parse_mode="HTML"
        )


async def back_to_main_menu(update: Update, context: Any):
    query = update.callback_query
    await query.answer()

    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END

    chat_id = query.message.chat_id if query.message else update.effective_chat.id
    try:
        if query.message:
            await query.message.delete()
    except Exception:
        pass

    return await context.bot.send_message(
        chat_id=chat_id,
        text="🏠 Главное меню. Выбирай нужный раздел, партнер.",
        reply_markup=kb.main_kb(query.from_user.id),
        parse_mode="HTML",
    )


async def show_price_list_text(update: Update, context: Any):
    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END
    return await _render_price_menu(update, context, via_callback=False)


async def show_price_card(update: Update, context: Any):
    query = update.callback_query
    await query.answer()
    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END

    data = query.data or ""
    if not data.startswith("price_srv_"):
        return ConversationHandler.END
    try:
        service_id = int(data.replace("price_srv_", "", 1))
    except ValueError:
        return await _render_price_menu(update, context, via_callback=True)

    srv = await catalog_db.get_service(service_id)
    if not srv:
        return await _render_price_menu(update, context, via_callback=True)

    desc = srv.get("description") or "Описание готовится"
    price = srv.get("price", 0)
    txt = (
        f"🤠 <b>{srv.get('name')}</b>\n\n"
        f"{desc}\n\n"
        f"💰 <b>Цена:</b> {price} RUB"
    )
    return await _safe_edit(
        query,
        txt,
        reply_markup=kb.back_kb("price_list"),
        parse_mode="HTML",
    )

async def partners(update: Update, context: Any):
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
    await _safe_edit(query, text, reply_markup=kb.back_kb("open_profile"), parse_mode="HTML")

async def my_history(update: Update, context: Any):
    query = update.callback_query
    await query.answer()
    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END
    orders = await db.get_user_orders(query.from_user.id)
    if not orders:
        await _safe_edit(query, "📂 <b>Архив пуст.</b>", reply_markup=kb.profile_kb(), parse_mode="HTML")
    else:
        trimmed = orders[:5]
        history_markup = builders.create_orders_history_keyboard(trimmed)
        await _safe_edit(query, "📂 <b>ВАШИ ДЕЛА:</b>", reply_markup=history_markup, parse_mode="HTML")

async def my_order(update: Update, context: Any):
    query = update.callback_query
    await query.answer()
    oid = int(query.data.split("_")[-1])
    o = await db.get_order(oid)
    status_label = {
        "new": "⏳ Ждет шерифа",
        "checking": "⏳ Ждет шерифа",
        "pending_pay": "⏳ Ждет шерифа",
        "paid": "⏳ Ждет шерифа",
        "work": "🤠 В работе",
        "completed": "✅ Выполнено",
        "done": "✅ Выполнено",
        "cancel": "❌ Отмена",
        "canceled": "❌ Отмена",
        "cancelled": "❌ Отмена",
    }.get(o.get("status"), o.get("status", "?"))

    admin_comment = o.get("admin_comment") or o.get("comment") or "—"
    price_value = o.get("final_price") or o.get("price") or 0
    txt = (
        f"📦 <b>ЗАКАЗ #{o['id']}</b>\n"
        f"📚 Услуга: {o.get('service_type', 'Услуга')}\n"
        f"💰 Цена: {price_value} ₽\n"
        f"📊 Статус: {status_label}\n"
        f"📝 Тема: {o.get('topic', '—')}\n"
        f"💬 Комментарий шерифа: {admin_comment}"
    )
    await _safe_edit(query, txt, reply_markup=kb.order_details_kb(oid, o.get('status')), parse_mode="HTML")

async def my_transactions(update: Update, context: Any):
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


async def show_code_of_honor(update: Update, context: Any):
    query = update.callback_query
    allowed = await _ensure_rules(update, context)
    if not allowed:
        return ConversationHandler.END
    if query:
        await query.answer()
        return await _safe_edit(query, CODE_OF_HONOR, reply_markup=kb.back_kb("home"), parse_mode="HTML")
    return await update.message.reply_text(CODE_OF_HONOR, reply_markup=kb.back_kb("home"), parse_mode="HTML")

# --- ОТЗЫВЫ ---
async def ask_review(update: Update, context: Any):
    query = update.callback_query
    await query.answer()
    await _safe_edit(
        query,
        "✍️ <b>Напиши пару слов:</b>\n\nМы прибьем твой отзыв на доску почета (в канал) анонимно.\nКидай текст или скрин.",
        reply_markup=kb.back_kb("open_profile"),
        parse_mode="HTML"
    )
    return REVIEW_STATE


async def cancel_review(update: Update, context: Any):
    state = _StateWrapper(context)
    await state.clear()
    query = update.callback_query
    if query:
        await query.answer()
    await profile(update, context)
    return ConversationHandler.END

async def submit_review(update: Update, context: Any):
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
    state = _StateWrapper(context)
    await state.clear()
    return ConversationHandler.END

async def handle_thanks(update: Update, context: Any):
    if not update.message or not update.message.text: return
    text = update.message.text.lower()
    keywords = ["спасибо", "спс", "благодарю", "thanks"]
    if any(word in text for word in keywords):
        try: await update.message.set_reaction("🥃")
        except: pass
        await update.message.reply_text("🤝 Всегда пожалуйста, партнер.")

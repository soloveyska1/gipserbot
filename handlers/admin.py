import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters

from config import ADMIN_IDS
from database import core as db
from database import db as crm_db
from keyboards import admin_kb
from keyboards.admin_kb import OrderCallback, StatsCallback, UserCallback

PRICE_STATE = 1
BALANCE_STATE = 2
NOTE_STATE = 3
DM_STATE = 4
USER_REPLY_STATE = 5
CLIENT_BALANCE_STATE = 6
BROADCAST_CONTENT_STATE = 7
BROADCAST_AUDIENCE_STATE = 8
BROADCAST_CONFIRM_STATE = 9
SERVICE_ADD_NAME_STATE = 10
SERVICE_ADD_PRICE_STATE = 11
SERVICE_ADD_DESC_STATE = 12
SERVICE_EDIT_NAME_STATE = 13
SERVICE_EDIT_PRICE_STATE = 14
SERVICE_EDIT_DESC_STATE = 15
ALLOWED_STATUSES = {
    "checking",
    "pending_pay",
    "paid",
    "work",
    "norm_control",
    "edits",
    "suspended",
    "done",
    "cancel",
}


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class _StateWrapper:
    def __init__(self, context: ContextTypes.DEFAULT_TYPE):
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


async def _safe_edit(query, text, **kwargs):
    msg = query.message
    try:
        if msg and msg.text:
            return await query.edit_message_text(text, **kwargs)
        if msg and msg.caption:
            return await query.edit_message_caption(caption=text, **kwargs)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise
    return await query.message.reply_text(text, **kwargs)


async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    state = _StateWrapper(context)
    await state.clear()
    await update.message.reply_text("💀 <b>GOD MODE ACTIVATED</b>", reply_markup=admin_kb.main_menu(), parse_mode="HTML")


def _parse_order_callback(update: Update) -> OrderCallback | None:
    query = update.callback_query
    if not query or not query.data:
        return None
    return OrderCallback.parse(query.data)


def _parse_user_callback(update: Update) -> UserCallback | None:
    query = update.callback_query
    if not query or not query.data:
        return None
    return UserCallback.parse(query.data)


def _parse_stats_callback(update: Update) -> StatsCallback | None:
    query = update.callback_query
    if not query or not query.data:
        return None
    return StatsCallback.parse(query.data)


def _rank_by_spent(total_spent: int) -> str:
    if total_spent >= 20000:
        return "VIP"
    if total_spent >= 5000:
        return "Pro"
    return "Novice"


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = _StateWrapper(context)
    await state.clear()
    query = update.callback_query
    if query:
        await query.answer()
    if query:
        await _safe_edit(query, "💀 <b>GOD MODE ACTIVATED</b>", reply_markup=admin_kb.main_menu(), parse_mode="HTML")
    return ConversationHandler.END


# --- CLIENTS CRM ---
async def show_clients(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()

    users = await crm_db.get_all_users_paginated(page)
    start_index = page * 10 + 1
    lines = ["👥 <b>КЛИЕНТЫ</b>"]
    if not users:
        lines.append("Пользователей пока нет")
    else:
        for idx, user in enumerate(users, start=start_index):
            uname = f"@{user['username']}" if user.get("username") else "—"
            fullname = user.get("full_name") or "Без имени"
            balance = user.get("balance", 0)
            lines.append(f"{idx}. {fullname} ({uname}) | {balance} 💎")

    text = "\n".join(lines)
    markup = admin_kb.get_users_list_kb(users, page)
    if query:
        await _safe_edit(query, text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def show_client_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int | None = None, page: int = 0):
    cb = _parse_user_callback(update)
    target_id = user_id if user_id is not None else (cb.id if cb else None)
    if target_id is None:
        return
    if not _is_admin(update.effective_user.id):
        return

    query = update.callback_query
    if query:
        await query.answer()

    user = await crm_db.get_user_admin_profile(target_id)
    if not user:
        if query:
            await query.answer("Пользователь не найден", show_alert=True)
        else:
            await update.message.reply_text("Пользователь не найден")
        return

    uname = f"@{user['username']}" if user.get("username") else "—"
    link = f"<a href='tg://user?id={user['user_id']}'>{user.get('full_name') or user['user_id']}</a>"
    rank = _rank_by_spent(user.get("total_spent", 0))
    note = user.get("admin_note") or "—"
    text = (
        f"👤 Пользователь: {link} ({uname})\n"
        f"🆔 ID: {user['user_id']}\n"
        f"📅 Дата регистрации: {user.get('joined_at') or '—'}\n"
        f"🤝 Пригласил: {user.get('referrer_id') or '—'}\n"
        f"💰 Баланс: {user.get('balance', 0)} 💎\n"
        f"📦 Заказы: {user.get('orders_count', 0)} (Сумма: {user.get('total_spent', 0)} ₽)\n"
        f"🏆 Ранг: {rank}\n"
        f"📝 Заметка: {note}"
    )

    markup = admin_kb.get_user_profile_kb(user_id=target_id, is_banned=bool(user.get("is_banned")), page=cb.page if cb else page)
    if query:
        await _safe_edit(query, text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = _parse_user_callback(update)
    if not cb:
        return
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()

    user = await crm_db.get_user_admin_profile(cb.id)
    if not user:
        if query:
            await query.answer("Не найден", show_alert=True)
        return
    new_status = not bool(user.get("is_banned"))
    await crm_db.set_ban_status(cb.id, new_status)
    await show_client_profile(update, context, user_id=cb.id, page=cb.page)


async def start_note_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = _parse_user_callback(update)
    if not cb or not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data["target_user_id"] = cb.id
    context.user_data["target_page"] = cb.page
    cancel_cb = UserCallback(action="view", id=cb.id, page=cb.page).pack()
    await _safe_edit(
        query,
        "📝 Введите новую заметку:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=cancel_cb)]]),
    )
    return NOTE_STATE


async def process_note_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет админскую заметку и возвращает в профиль."""
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    target = context.user_data.get("target_user_id")
    page = context.user_data.get("target_page", 0)
    if not target:
        await update.message.reply_text("❌ Нет выбранного пользователя")
        return ConversationHandler.END
    await crm_db.update_admin_note(target, update.message.text or "")
    await update.message.reply_text("✅ Заметка сохранена")
    state = _StateWrapper(context)
    await state.clear()
    await show_client_profile(update, context, user_id=target, page=page)
    return ConversationHandler.END


async def cancel_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = _StateWrapper(context)
    await state.clear()
    cb = _parse_user_callback(update)
    if cb:
        await show_client_profile(update, context, user_id=cb.id, page=cb.page)
    return ConversationHandler.END


async def start_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = _parse_user_callback(update)
    if not cb or not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data["target_user_id"] = cb.id
    context.user_data["target_page"] = cb.page
    cancel_cb = UserCallback(action="view", id=cb.id, page=cb.page).pack()
    await _safe_edit(
        query,
        "✉️ Введите текст для отправки пользователю:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=cancel_cb)]]),
    )
    return DM_STATE


async def process_dm_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет личное сообщение и возвращает к профилю."""
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    target = context.user_data.get("target_user_id")
    page = context.user_data.get("target_page", 0)
    if not target:
        await update.message.reply_text("❌ Нет выбранного пользователя")
        return ConversationHandler.END

    reply_btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ Ответить", callback_data=UserCallback(action="reply", id=update.effective_user.id, page=0).pack())]]
    )
    try:
        await context.bot.send_message(target, f"✉️ Сообщение от Шерифа:\n{update.message.text}", reply_markup=reply_btn)
    except Exception:
        await update.message.reply_text("⚠️ Не удалось доставить сообщение")
    else:
        await update.message.reply_text("✅ Сообщение отправлено")

    state = _StateWrapper(context)
    await state.clear()
    await show_client_profile(update, context, user_id=target, page=page)
    return ConversationHandler.END


async def cancel_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = _StateWrapper(context)
    await state.clear()
    cb = _parse_user_callback(update)
    if cb:
        await show_client_profile(update, context, user_id=cb.id, page=cb.page)
    return ConversationHandler.END


async def start_points_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = _parse_user_callback(update)
    if not cb or cb.action not in {"points_add", "points_sub"} or not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data["target_user_id"] = cb.id
    context.user_data["target_page"] = cb.page
    context.user_data["points_action"] = "add" if cb.action == "points_add" else "remove"
    cancel_cb = UserCallback(action="view", id=cb.id, page=cb.page).pack()
    prompt = "💎 Введите количество баллов для начисления:" if cb.action == "points_add" else "💎 Введите количество баллов для списания:"
    await _safe_edit(
        query,
        prompt,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data=cancel_cb)]]),
    )
    return CLIENT_BALANCE_STATE


async def process_balance_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод баллов и обновляет баланс."""
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    target = context.user_data.get("target_user_id")
    page = context.user_data.get("target_page", 0)
    action = context.user_data.get("points_action")
    if not target or action not in {"add", "remove"}:
        await update.message.reply_text("❌ Нет выбранного пользователя")
        return ConversationHandler.END
    try:
        amount = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return CLIENT_BALANCE_STATE

    delta = amount if action == "add" else -abs(amount)
    await db.adjust_balance(target, delta, "Админ коррекция")
    fresh_user = await crm_db.get_user_admin_profile(target) or {}
    new_balance = fresh_user.get("balance", 0)
    await update.message.reply_text(f"✅ Баланс обновлён! Новый баланс: {new_balance} 💎")

    state = _StateWrapper(context)
    await state.clear()
    await show_client_profile(update, context, user_id=target, page=page)
    return ConversationHandler.END


async def cancel_points_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = _StateWrapper(context)
    await state.clear()
    cb = _parse_user_callback(update)
    if cb:
        await show_client_profile(update, context, user_id=cb.id, page=cb.page)
    return ConversationHandler.END


async def show_user_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = _parse_user_callback(update)
    if not cb or not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()
    orders = await db.get_user_orders(cb.id)
    back_cb = UserCallback(action="view", id=cb.id, page=cb.page).pack()
    markup = admin_kb.user_orders_kb(orders, back_cb)
    await _safe_edit(query, "📦 Заказы пользователя", reply_markup=markup, parse_mode="HTML")


async def start_user_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = _parse_user_callback(update)
    if not cb or cb.action != "reply":
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data["reply_admin"] = cb.id
    await _safe_edit(query, "✍️ Напишите ответ Шерифу:")
    return USER_REPLY_STATE


async def send_user_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = context.user_data.get("reply_admin")
    if not admin_id:
        await update.message.reply_text("❌ Админ не найден")
        return ConversationHandler.END
    text = update.message.text or ""
    user = update.effective_user
    link = f"<a href='tg://user?id={user.id}'>{user.full_name or user.id}</a>"
    try:
        await context.bot.send_message(admin_id, f"↩️ Ответ от {link}:\n{text}", parse_mode="HTML")
    except Exception:
        pass
    await update.message.reply_text("✅ Отправлено Шерифу")
    return ConversationHandler.END


# --- ORDERS ---
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()

    orders = await db.get_all_orders(limit=100)
    text = f"📦 <b>АКТИВНЫЕ ЗАКАЗЫ</b> (стр. {page+1})"
    if query:
        await _safe_edit(query, text, reply_markup=admin_kb.orders_list(orders, page), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=admin_kb.orders_list(orders, page), parse_mode="HTML")


async def show_order(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int | None = None):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()
    oid = order_id if order_id is not None else (_parse_order_callback(update).id if _parse_order_callback(update) else None)
    if oid is None:
        return
    order = await db.get_order(oid)

    status_label = {
        "checking": "🟡 На проверке",
        "pending_pay": "💳 Ждёт оплаты",
        "paid": "💸 Оплачено",
        "work": "⚙️ В работе",
        "norm_control": "🧭 Нормоконтроль",
        "edits": "✏️ Правки",
        "suspended": "⏸ Приостановлен",
        "done": "✅ Выполнен",
        "cancel": "❌ Отменён",
    }

    original_price = order.get("original_price", order["price"])
    points_used = order.get("points_used", 0)
    final_price = order.get("final_price", order["price"])
    user_link = f"<a href='tg://user?id={order['user_id']}'>{order['user_id']}</a>"

    txt = (
        f"📦 <b>ЗАКАЗ #{oid}</b>\n"
        f"👤 Юзер: {user_link}\n"
        f"📚 Тип: {order['service_type']}\n"
        f"📊 Статус: {status_label.get(order['status'], order['status'])}\n"
        f"📝 Тема: {order['topic']}\n\n"
        f"💵 <b>Финансы:</b>\n"
        f"Цена: {original_price} ₽\n"
        f"Списано баллов: -{points_used} 💎\n"
        f"<b>ИТОГО К ОПЛАТЕ: {final_price} ₽</b>\n"
    )
    await _safe_edit(query, txt, reply_markup=admin_kb.order_actions(oid, order['status'], order['user_id']), parse_mode="HTML")


async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, from_order: int | None = None):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()

    user = await db.get_user(user_id)
    balance = user.get("balance", 0) if user else 0
    txt = (
        f"👤 <b>Профиль пользователя</b>\n"
        f"ID: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
        f"Баланс: {balance} 💎\n"
    )

    kb = admin_kb.user_profile_kb(user_id, from_order)
    if query:
        await _safe_edit(query, txt, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")


async def start_balance_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    cb = _parse_order_callback(update)
    if not cb:
        return ConversationHandler.END
    await query.answer()
    context.user_data["balance_target"] = cb.id
    context.user_data["balance_direction"] = cb.action  # give or take
    order_id = int(cb.payload) if cb.payload else 0
    context.user_data["balance_order"] = order_id
    prompt = "💎 Введите количество баллов для начисления:" if cb.action == "give" else "💎 Введите количество баллов для списания:"
    cancel_cb = OrderCallback(action="user", id=cb.id, payload=str(order_id or 0)).pack()
    await _safe_edit(query, prompt, reply_markup=admin_kb.cancel_kb(cancel_cb))
    return BALANCE_STATE


async def save_balance_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    target = context.user_data.get("balance_target")
    direction = context.user_data.get("balance_direction")
    order_id = context.user_data.get("balance_order") or 0
    if not target or direction not in {"give", "take"}:
        await update.message.reply_text("❌ Нет выбранного пользователя")
        return ConversationHandler.END
    try:
        amount = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Введите число", reply_markup=admin_kb.cancel_kb(OrderCallback(action="user", id=target, payload=str(order_id)).pack()))
        return BALANCE_STATE

    delta = amount if direction == "give" else -amount
    await db.adjust_balance(target, delta, "Ручная корректировка")
    notice = f"✅ Баланс изменён на {delta}"
    await update.message.reply_text(notice, parse_mode="HTML")
    try:
        await context.bot.send_message(
            target,
            f"🏜️ Шериф поправил баланс на {delta}. Текущий баланс уточните в профиле.",
        )
    except Exception:
        pass

    await show_user_profile(update, context, target, order_id if order_id else None)
    return ConversationHandler.END


async def cancel_balance_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    cb = _parse_order_callback(update)
    state = _StateWrapper(context)
    await state.clear()
    if query:
        await query.answer("Отменено")
    if cb:
        order_id = int(cb.payload) if cb.payload else 0
        await show_user_profile(update, context, cb.id, order_id if order_id else None)
    return ConversationHandler.END


async def set_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE, oid: int, status: str):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()

    if status not in ALLOWED_STATUSES:
        if query:
            await query.answer("Недопустимый статус", show_alert=True)
        return

    order_before = await db.get_order(oid)
    if not order_before:
        if query:
            await query.answer("Заказ не найден", show_alert=True)
        return
    if status == "cancel":
        refunded = await db.refund_points_to_user(oid)
        if refunded:
            try:
                await context.bot.send_message(
                    order_before["user_id"],
                    f"❌ Заказ отменен. {refunded} баллов возвращены.",
                )
            except Exception:
                pass

    await db.update_order_status(oid, status)
    order = await db.get_order(oid)

    status_msg = {
        "work": f"⚙️ <b>Ваш заказ #{oid} взят в работу!</b>\nМы начали. Ожидайте.",
        "done": f"✅ <b>Заказ #{oid} ГОТОВ!</b>\nПринимайте работу.",
        "pending_pay": f"💳 <b>По заказу #{oid} ожидается оплата.</b>",
        "paid": f"💸 <b>Оплата по заказу #{oid} подтверждена.</b>",
        "norm_control": f"🧭 <b>Заказ #{oid} на нормоконтроле.</b>",
        "edits": f"✏️ <b>Заказ #{oid} на правках.</b>",
        "suspended": f"⏸ <b>Заказ #{oid} приостановлен.</b>",
        "cancel": f"❌ <b>Заказ #{oid} отменен.</b>",
    }
    if status in status_msg:
        try:
            await context.bot.send_message(order["user_id"], status_msg[status], parse_mode="HTML")
        except Exception:
            pass

    if status == "paid":
        user = await db.get_user(order["user_id"])
        referrer_id = user.get("referrer_id") if user else 0
        if referrer_id and not order.get("referral_bonus_paid"):
            reward = int((order.get("final_price") or order.get("price", 0)) * 0.10)
            if reward > 0:
                await db.adjust_balance(referrer_id, reward, "Реферальный бонус")
                await db.mark_referral_paid(oid)
                try:
                    await context.bot.send_message(
                        referrer_id,
                        f"🤝 Реферал оплатил заказ #{oid}. Тебе начислено {reward} баллов.",
                    )
                except Exception:
                    pass

    await query.answer("Статус обновлён")
    await show_order(update, context)


# --- SERVICES CRUD (PRICE LIST) ---
async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    crm_db.seed_services()
    query = update.callback_query
    if query:
        await query.answer()

    services = await crm_db.get_services()
    text_lines = ["⚙️ <b>ПРАЙС</b>", "Выберите услугу для редактирования или добавьте новую."]
    markup = admin_kb.get_services_editor_kb(services)
    if query:
        await _safe_edit(query, "\n".join(text_lines), reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text("\n".join(text_lines), reply_markup=markup, parse_mode="HTML")


async def show_service_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    try:
        service_id = int(query.data.replace("edit_svc_", ""))
    except ValueError:
        return

    service = await crm_db.get_service(service_id)
    if not service:
        await query.answer("Услуга не найдена", show_alert=True)
        return

    text = (
        f"💼 <b>{service['name']}</b>\n"
        f"💰 Цена: {service['price']} ₽\n"
        f"📝 Описание: {service.get('description') or '—'}"
    )
    await _safe_edit(query, text, reply_markup=admin_kb.service_actions_kb(service_id), parse_mode="HTML")


async def start_add_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
    state = _StateWrapper(context)
    await state.clear()
    await _safe_edit(query, "🆕 Введите название новой услуги:", reply_markup=admin_kb.cancel_kb("admin_prices"))
    return SERVICE_ADD_NAME_STATE


async def add_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("❌ Введите название")
        return SERVICE_ADD_NAME_STATE
    context.user_data["new_service_name"] = name
    await update.message.reply_text(
        "💰 Укажите цену (целое число в рублях):",
        reply_markup=admin_kb.cancel_kb("admin_prices"),
    )
    return SERVICE_ADD_PRICE_STATE


async def add_service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text)
    except (TypeError, ValueError):
        await update.message.reply_text("❌ Введите число", reply_markup=admin_kb.cancel_kb("admin_prices"))
        return SERVICE_ADD_PRICE_STATE
    context.user_data["new_service_price"] = price
    await update.message.reply_text(
        "📝 Добавьте описание услуги:",
        reply_markup=admin_kb.cancel_kb("admin_prices"),
    )
    return SERVICE_ADD_DESC_STATE


async def add_service_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get("new_service_name")
    price = context.user_data.get("new_service_price")
    desc = update.message.text or ""
    if not name or price is None:
        await update.message.reply_text("❌ Данные не найдены, начните заново")
        return ConversationHandler.END
    await crm_db.add_service(name, int(price), desc)
    state = _StateWrapper(context)
    await state.clear()
    await update.message.reply_text("✅ Услуга добавлена")
    await show_services(update, context)
    return ConversationHandler.END


async def start_edit_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    try:
        svc_id = int(query.data.replace("svc_edit_name_", ""))
    except ValueError:
        return ConversationHandler.END
    context.user_data["edit_service_id"] = svc_id
    await _safe_edit(
        query,
        "✏️ Введите новое название:",
        reply_markup=admin_kb.cancel_kb(f"edit_svc_{svc_id}"),
    )
    return SERVICE_EDIT_NAME_STATE


async def start_edit_service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    try:
        svc_id = int(query.data.replace("svc_edit_price_", ""))
    except ValueError:
        return ConversationHandler.END
    context.user_data["edit_service_id"] = svc_id
    await _safe_edit(
        query,
        "💰 Новая цена (руб):",
        reply_markup=admin_kb.cancel_kb(f"edit_svc_{svc_id}"),
    )
    return SERVICE_EDIT_PRICE_STATE


async def start_edit_service_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    try:
        svc_id = int(query.data.replace("svc_edit_desc_", ""))
    except ValueError:
        return ConversationHandler.END
    context.user_data["edit_service_id"] = svc_id
    await _safe_edit(
        query,
        "📝 Новое описание:",
        reply_markup=admin_kb.cancel_kb(f"edit_svc_{svc_id}"),
    )
    return SERVICE_EDIT_DESC_STATE


async def save_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    svc_id = context.user_data.get("edit_service_id")
    if not svc_id:
        await update.message.reply_text("❌ Нет услуги")
        return ConversationHandler.END
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("❌ Введите название")
        return SERVICE_EDIT_NAME_STATE
    await crm_db.update_service_name(int(svc_id), name)
    await update.message.reply_text("✅ Название обновлено")
    state = _StateWrapper(context)
    await state.clear()
    await show_service_actions_from_message(update, context, int(svc_id))
    return ConversationHandler.END


async def save_service_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    svc_id = context.user_data.get("edit_service_id")
    if not svc_id:
        await update.message.reply_text("❌ Нет услуги")
        return ConversationHandler.END
    try:
        price = int(update.message.text)
    except (TypeError, ValueError):
        await update.message.reply_text("❌ Введите число")
        return SERVICE_EDIT_PRICE_STATE
    await crm_db.update_service_price(int(svc_id), price)
    await update.message.reply_text("✅ Цена обновлена")
    state = _StateWrapper(context)
    await state.clear()
    await show_service_actions_from_message(update, context, int(svc_id))
    return ConversationHandler.END


async def save_service_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    svc_id = context.user_data.get("edit_service_id")
    if not svc_id:
        await update.message.reply_text("❌ Нет услуги")
        return ConversationHandler.END
    desc = update.message.text or ""
    await crm_db.update_service_description(int(svc_id), desc)
    await update.message.reply_text("✅ Описание обновлено")
    state = _StateWrapper(context)
    await state.clear()
    await show_service_actions_from_message(update, context, int(svc_id))
    return ConversationHandler.END


async def delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if not query:
        return
    await query.answer()
    try:
        svc_id = int(query.data.replace("svc_delete_", ""))
    except ValueError:
        return
    await crm_db.delete_service(svc_id)
    await query.answer("Услуга удалена", show_alert=True)
    await show_services(update, context)


async def cancel_service_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = _StateWrapper(context)
    await state.clear()
    query = update.callback_query
    if query:
        await query.answer("Отменено")
    if query and query.data and query.data.startswith("edit_svc_"):
        await show_service_actions(update, context)
    else:
        await show_services(update, context)
    return ConversationHandler.END


async def show_service_actions_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE, svc_id: int):
    service = await crm_db.get_service(svc_id)
    if not service:
        await update.message.reply_text("❌ Услуга не найдена")
        return
    text = (
        f"💼 <b>{service['name']}</b>\n"
        f"💰 Цена: {service['price']} ₽\n"
        f"📝 Описание: {service.get('description') or '—'}"
    )
    await update.message.reply_text(text, reply_markup=admin_kb.service_actions_kb(svc_id), parse_mode="HTML")


# --- STATS / BROADCAST ---
async def _collect_stats():
    conn = await db.get_connection()
    try:
        new_today = conn.execute(
            "SELECT COUNT(*) FROM users WHERE date(joined_at) = date('now')"
        ).fetchone()[0]
        new_week = conn.execute(
            "SELECT COUNT(*) FROM users WHERE date(joined_at) >= date('now','-7 day')"
        ).fetchone()[0]
        revenue = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN final_price>0 THEN final_price ELSE price END),0) FROM orders WHERE status != 'cancel'"
        ).fetchone()[0]
        top_rows = conn.execute(
            "SELECT user_id, username, full_name, total_spent FROM users ORDER BY total_spent DESC LIMIT 3"
        ).fetchall()
    finally:
        conn.close()
    top = []
    for row in top_rows:
        uname = f"@{row[1]}" if row[1] else "—"
        name = row[2] or row[0]
        top.append(f"{name} ({uname}) — {row[3]} ₽")
    return {
        "new_today": new_today,
        "new_week": new_week,
        "revenue": revenue,
        "top": top,
    }


async def _reset_stats():
    conn = await db.get_connection()
    try:
        conn.execute("UPDATE users SET total_spent = 0, orders_count = 0")
        conn.execute("UPDATE orders SET price = 0, original_price = 0, final_price = 0, points_used = 0")
        conn.commit()
    finally:
        conn.close()


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()
    cb = _parse_stats_callback(update)
    if cb and cb.action == "confirm_reset":
        await _reset_stats()
    data = await _collect_stats()
    lines = [
        "📊 <b>СТАТИСТИКА</b>",
        f"👥 Новые сегодня: {data['new_today']}",
        f"📈 Новые за неделю: {data['new_week']}",
        f"💵 Оборот: {data['revenue']} ₽",
        "🏆 Топ-3 клиентов:",
    ]
    if data["top"]:
        lines.extend([f"{idx+1}. {row}" for idx, row in enumerate(data["top"])])
    else:
        lines.append("— пока пусто")
    text = "\n".join(lines)
    markup = admin_kb.stats_menu()
    if cb and cb.action == "reset":
        # show confirmation prompt
        confirm = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Сбросить", callback_data=StatsCallback(action="confirm_reset").pack())],
                [InlineKeyboardButton("⬅️ Назад", callback_data=StatsCallback(action="view").pack())],
            ]
        )
        await _safe_edit(query, "Подтвердите сброс статистики", reply_markup=confirm)
        return
    if query:
        await _safe_edit(query, text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
    state = _StateWrapper(context)
    await state.clear()
    context.user_data.pop("broadcast", None)
    await _safe_edit(
        query,
        "📢 Отправьте текст или фото для рассылки",
        reply_markup=admin_kb.cancel_kb("admin_main"),
    )
    return BROADCAST_CONTENT_STATE


async def capture_broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    message = update.message
    if message.photo:
        photo_id = message.photo[-1].file_id
        context.user_data["broadcast"] = {
            "type": "photo",
            "file_id": photo_id,
            "caption": message.caption or "",
        }
    elif message.text:
        context.user_data["broadcast"] = {"type": "text", "text": message.text}
    else:
        await message.reply_text("⚠️ Пришлите текст или фото")
        return BROADCAST_CONTENT_STATE

    await message.reply_text("Выберите аудиторию:", reply_markup=admin_kb.broadcast_audience_kb())
    return BROADCAST_AUDIENCE_STATE


async def choose_broadcast_audience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
    audience_map = {
        "bc_aud_all": "all",
        "bc_aud_active": "active",
        "bc_aud_silent": "silent",
    }
    kind = audience_map.get(query.data if query else "")
    if not kind:
        return BROADCAST_AUDIENCE_STATE
    context.user_data.setdefault("broadcast", {})["audience"] = kind
    await _safe_edit(
        query,
        "Подтвердите отправку?",
        reply_markup=admin_kb.broadcast_confirm_kb(),
    )
    return BROADCAST_CONFIRM_STATE


async def _get_broadcast_targets(kind: str):
    conn = await db.get_connection()
    try:
        if kind == "active":
            cur = conn.execute(
                "SELECT DISTINCT user_id FROM orders WHERE created_at >= date('now','-30 day')"
            )
        elif kind == "silent":
            cur = conn.execute("SELECT user_id FROM users WHERE orders_count = 0")
        else:
            cur = conn.execute("SELECT user_id FROM users WHERE is_banned = 0")
        rows = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    return rows


async def confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer()
    if query.data == "admin_main":
        state = _StateWrapper(context)
        await state.clear()
        await _safe_edit(query, "Отменено", reply_markup=admin_kb.main_menu())
        return ConversationHandler.END
    payload = context.user_data.get("broadcast") or {}
    if not payload.get("audience"):
        await _safe_edit(query, "⚠️ Сначала выберите аудиторию", reply_markup=admin_kb.broadcast_audience_kb())
        return BROADCAST_AUDIENCE_STATE
    targets = await _get_broadcast_targets(payload["audience"])
    sent = 0
    for uid in targets:
        try:
            if payload.get("type") == "photo":
                await query.bot.send_photo(uid, payload["file_id"], caption=payload.get("caption"))
            else:
                await query.bot.send_message(uid, payload.get("text", ""))
            sent += 1
        except Forbidden:
            continue
        except Exception:
            continue
        await asyncio.sleep(0.05)
    await _safe_edit(
        query,
        f"✅ Рассылка завершена. Доставлено: {sent}/{len(targets)}",
        reply_markup=admin_kb.main_menu(),
    )
    state = _StateWrapper(context)
    await state.clear()
    context.user_data.pop("broadcast", None)
    return ConversationHandler.END


async def order_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cb = _parse_order_callback(update)
    if not cb:
        return
    if cb.action == "list":
        await show_orders(update, context, page=cb.id)
    elif cb.action == "view":
        await show_order(update, context, order_id=cb.id)
    elif cb.action == "status":
        await set_order_status(update, context, oid=cb.id, status=cb.payload)
    elif cb.action == "user":
        from_order = int(cb.payload) if cb.payload else None
        await show_user_profile(update, context, user_id=cb.id, from_order=from_order)
    elif cb.action in {"give", "take"}:
        await start_balance_change(update, context)


def setup(app):
    app.add_handler(CommandHandler("admin", entry))

    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^admin_main$"))

    app.add_handler(CallbackQueryHandler(show_services, pattern="^admin_prices$"))
    app.add_handler(CallbackQueryHandler(show_service_actions, pattern=r"^edit_svc_\d+$"))
    app.add_handler(CallbackQueryHandler(delete_service, pattern=r"^svc_delete_\d+$"))
    service_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_service, pattern="^add_service$"),
            CallbackQueryHandler(start_edit_service_name, pattern=r"^svc_edit_name_\d+$"),
            CallbackQueryHandler(start_edit_service_price, pattern=r"^svc_edit_price_\d+$"),
            CallbackQueryHandler(start_edit_service_desc, pattern=r"^svc_edit_desc_\d+$"),
        ],
        states={
            SERVICE_ADD_NAME_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_name),
                CallbackQueryHandler(cancel_service_conversation, pattern=r"^admin_prices$|^edit_svc_"),
            ],
            SERVICE_ADD_PRICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_price),
                CallbackQueryHandler(cancel_service_conversation, pattern=r"^admin_prices$|^edit_svc_"),
            ],
            SERVICE_ADD_DESC_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_service_description),
                CallbackQueryHandler(cancel_service_conversation, pattern=r"^admin_prices$|^edit_svc_"),
            ],
            SERVICE_EDIT_NAME_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_service_name),
                CallbackQueryHandler(cancel_service_conversation, pattern=r"^admin_prices$|^edit_svc_"),
            ],
            SERVICE_EDIT_PRICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_service_price),
                CallbackQueryHandler(cancel_service_conversation, pattern=r"^admin_prices$|^edit_svc_"),
            ],
            SERVICE_EDIT_DESC_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_service_desc),
                CallbackQueryHandler(cancel_service_conversation, pattern=r"^admin_prices$|^edit_svc_"),
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel_service_conversation, pattern=r"^admin_prices$|^edit_svc_")],
        per_message=False,
    )
    app.add_handler(service_conv)

    balance_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_balance_change, pattern=r"^ord:(give|take):")],
        states={
            BALANCE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_balance_change),
                CallbackQueryHandler(cancel_balance_change, pattern=r"^ord:user:"),
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_balance_change, pattern=r"^ord:user:")],
        per_message=False,
    )
    app.add_handler(balance_conv)

    app.add_handler(CallbackQueryHandler(order_callback_router, pattern=r"^ord:(list|view|status|user|give|take):"))

    # CRM clients
    app.add_handler(CallbackQueryHandler(show_clients, pattern=r"^usr:list:"))
    app.add_handler(CallbackQueryHandler(show_client_profile, pattern=r"^usr:view:"))
    app.add_handler(CallbackQueryHandler(toggle_ban, pattern=r"^usr:ban:"))
    app.add_handler(CallbackQueryHandler(show_user_orders, pattern=r"^usr:orders:"))

    note_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_note_edit, pattern=r"^usr:note:")],
        states={
            NOTE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_note_message),
                CallbackQueryHandler(cancel_note, pattern=r"^usr:view:"),
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_note, pattern=r"^usr:view:")],
        per_message=False,
    )
    app.add_handler(note_conv)

    dm_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_dm, pattern=r"^usr:msg:")],
        states={
            DM_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_dm_message),
                CallbackQueryHandler(cancel_dm, pattern=r"^usr:view:"),
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_dm, pattern=r"^usr:view:")],
        per_message=False,
    )
    app.add_handler(dm_conv)

    points_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_points_change, pattern=r"^usr:points_(add|sub):")],
        states={
            CLIENT_BALANCE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_balance_change),
                CallbackQueryHandler(cancel_points_change, pattern=r"^usr:view:"),
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_points_change, pattern=r"^usr:view:")],
        per_message=False,
    )
    app.add_handler(points_conv)

    user_reply_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_user_reply, pattern=r"^usr:reply:")],
        states={
            USER_REPLY_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_user_reply),
            ]
        },
        fallbacks=[],
        per_message=False,
    )
    app.add_handler(user_reply_conv)

    app.add_handler(CallbackQueryHandler(show_stats, pattern=r"^stat:"))

    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern="^admin_broadcast$")],
        states={
            BROADCAST_CONTENT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, capture_broadcast_content),
                MessageHandler(filters.PHOTO, capture_broadcast_content),
                CallbackQueryHandler(back_to_main, pattern="^admin_main$"),
            ],
            BROADCAST_AUDIENCE_STATE: [
                CallbackQueryHandler(choose_broadcast_audience, pattern=r"^bc_aud_(all|active|silent)$"),
                CallbackQueryHandler(back_to_main, pattern="^admin_main$"),
            ],
            BROADCAST_CONFIRM_STATE: [
                CallbackQueryHandler(confirm_broadcast, pattern=r"^bc_confirm_yes$|^admin_main$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(back_to_main, pattern="^admin_main$")],
        per_message=False,
    )
    app.add_handler(broadcast_conv)


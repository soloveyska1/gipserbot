from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters

from config import ADMIN_IDS, SERVICES
from database import core as db
from database import pricing
from keyboards import admin_kb
from keyboards.admin_kb import OrderCallback

PRICE_STATE = 1
BALANCE_STATE = 2
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
    await update.message.reply_text("💀 <b>GOD MODE ACTIVATED</b>", reply_markup=admin_kb.main_menu(), parse_mode="HTML")


def _parse_order_callback(update: Update) -> OrderCallback | None:
    query = update.callback_query
    if not query or not query.data:
        return None
    return OrderCallback.parse(query.data)


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await _safe_edit(query, "💀 <b>GOD MODE ACTIVATED</b>", reply_markup=admin_kb.main_menu(), parse_mode="HTML")


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


# --- PRICES ---
async def show_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()

    prices = {}
    for key, meta in SERVICES.items():
        price_value = await pricing.get_price(f"srv_{key}")
        prices[f"srv_{key}"] = {"title": f"{meta['emoji']} {meta['name']}", "price": price_value}
    for extra_key, title in [("speech", "🎤 Речь"), ("pres", "💻 Презентация"), ("vip", "👑 VIP")]:
        price_value = await pricing.get_price(extra_key)
        prices[extra_key] = {"title": title, "price": price_value}

    text = "⚙️ <b>ПРАЙС</b>\nВыберите позицию для изменения"
    markup = admin_kb.prices_menu(prices)
    if query:
        await _safe_edit(query, text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    await query.answer()
    key = query.data.replace("admin_price_", "")
    context.user_data["price_key"] = key

    current = await pricing.get_price(key)
    prompt = f"💰 <b>Изменение цены</b>\nТекущая: {current} ₽\n\nВведите новую цену:"

    await _safe_edit(query, prompt, reply_markup=admin_kb.cancel_kb("admin_prices"), parse_mode="HTML")
    return PRICE_STATE


async def save_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    key = context.user_data.get("price_key")
    if not key:
        await update.message.reply_text("❌ Нет выбранной позиции")
        return ConversationHandler.END

    try:
        value = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ Введите число", reply_markup=admin_kb.cancel_kb("admin_prices"))
        return PRICE_STATE

    await pricing.set_price(key, value)
    await update.message.reply_text("✅ Цена сохранена!", parse_mode="HTML")
    await show_prices(update, context)
    return ConversationHandler.END


async def cancel_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return ConversationHandler.END
    query = update.callback_query
    if query:
        await query.answer("Отменено")
    await show_prices(update, context)
    return ConversationHandler.END


# --- STATS / BROADCAST PLACEHOLDERS ---
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()
    u, o, m = await db.get_stats()
    text = f"📊 <b>СТАТИСТИКА</b>\n👥 Юзеров: {u}\n📦 Заказов: {o}\n💵 Оборот: {m} ₽"
    markup = admin_kb.main_menu()
    if query:
        await _safe_edit(query, text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def broadcast_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer("Скоро", show_alert=False)
        await _safe_edit(query, "📢 РАССЫЛКА скоро будет доступна", reply_markup=admin_kb.main_menu())


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

    app.add_handler(CallbackQueryHandler(show_prices, pattern="^admin_prices$"))
    price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_price, pattern="^admin_price_")],
        states={
            PRICE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_price),
                CallbackQueryHandler(cancel_price, pattern="^admin_prices$|^admin_main$"),
            ]
        },
        fallbacks=[CallbackQueryHandler(cancel_price, pattern="^admin_prices$|^admin_main$")],
        per_message=False,
    )
    app.add_handler(price_conv)

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

    app.add_handler(CallbackQueryHandler(show_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(broadcast_placeholder, pattern="^admin_broadcast$"))


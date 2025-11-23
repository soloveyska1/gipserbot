from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, filters

from config import ADMIN_IDS, SERVICES
from database import core as db
from database import pricing
from keyboards import admin_kb

PRICE_STATE = 1
ALLOWED_STATUSES = {
    "checking",
    "pending_pay",
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


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await _safe_edit(query, "💀 <b>GOD MODE ACTIVATED</b>", reply_markup=admin_kb.main_menu(), parse_mode="HTML")


# --- ORDERS ---
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    if query:
        await query.answer()

    page = 0
    if query and query.data.startswith("admin_orders_page_"):
        page = int(query.data.split("_")[-1])

    orders = await db.get_all_orders(limit=100)
    text = f"📦 <b>АКТИВНЫЕ ЗАКАЗЫ</b> (стр. {page+1})"
    if query:
        await _safe_edit(query, text, reply_markup=admin_kb.orders_list(orders, page), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=admin_kb.orders_list(orders, page), parse_mode="HTML")


async def show_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    await query.answer()
    oid = int(query.data.split("_")[-1])
    order = await db.get_order(oid)

    status_label = {
        "checking": "🟡 На проверке",
        "pending_pay": "💳 Ждёт оплаты",
        "work": "⚙️ В работе",
        "norm_control": "🧭 Нормоконтроль",
        "edits": "✏️ Правки",
        "suspended": "⏸ Приостановлен",
        "done": "✅ Выполнен",
        "cancel": "❌ Отменён",
    }

    txt = (
        f"📦 <b>ЗАКАЗ #{oid}</b>\n"
        f"👤 Юзер: {order['user_id']}\n"
        f"📚 Тип: {order['service_type']}\n"
        f"💰 Цена: {order['price']} ₽\n"
        f"📊 Статус: {status_label.get(order['status'], order['status'])}\n"
        f"📝 Тема: {order['topic']}\n"
    )
    await _safe_edit(query, txt, reply_markup=admin_kb.order_actions(oid, order['status']), parse_mode="HTML")


async def set_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    oid = int(parts[3])
    status = "_".join(parts[4:])

    if status not in ALLOWED_STATUSES:
        await query.answer("Недопустимый статус", show_alert=True)
        return

    await db.update_order_status(oid, status)
    order = await db.get_order(oid)

    status_msg = {
        "work": f"⚙️ <b>Ваш заказ #{oid} взят в работу!</b>\nМы начали. Ожидайте.",
        "done": f"✅ <b>Заказ #{oid} ГОТОВ!</b>\nПринимайте работу.",
        "pending_pay": f"💳 <b>По заказу #{oid} ожидается оплата.</b>",
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


def setup(app):
    app.add_handler(CommandHandler("admin", entry))

    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^admin_main$"))
    app.add_handler(CallbackQueryHandler(show_orders, pattern="^admin_orders$|^admin_orders_page_"))
    app.add_handler(CallbackQueryHandler(show_order, pattern="^admin_order_"))
    app.add_handler(CallbackQueryHandler(set_order_status, pattern="^admin_set_status_"))

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

    app.add_handler(CallbackQueryHandler(show_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(broadcast_placeholder, pattern="^admin_broadcast$"))


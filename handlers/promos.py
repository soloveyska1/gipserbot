from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import ADMIN_IDS
from database import db as promo_db
from database import core as db


PROMO_CODE_STATE = 1
PROMO_AMOUNT_STATE = 2
PROMO_ACTIVATIONS_STATE = 3
PROMO_ENTER_STATE = 4


def setup(app):
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("promo", promo_start)],
            states={
                PROMO_ENTER_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, promo_apply)],
            },
            fallbacks=[],
            per_message=False,
        )
    )

    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("create_promo", start_create_promo)],
            states={
                PROMO_CODE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
                PROMO_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_activations)],
                PROMO_ACTIVATIONS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_promo)],
            },
            fallbacks=[],
            per_message=False,
        )
    )


async def promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите промокод:")
    return PROMO_ENTER_STATE


async def promo_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    promo = await promo_db.fetch_promo_code(code)
    if not promo or promo.get("activations_left", 0) <= 0:
        await update.message.reply_text("❌ Промокод не найден или закончился.")
        return ConversationHandler.END
    if await promo_db.has_used_promo(user_id, code):
        await update.message.reply_text("⚠️ Этот промокод уже активирован на вашем аккаунте.")
        return ConversationHandler.END

    await promo_db.apply_promo_to_user(user_id, code)
    await db.log_action(user_id, f"Использовал промокод {code}")
    await update.message.reply_text(
        f"✅ Промокод активирован. Баланс пополнен на {promo['discount_amount']} баллов.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def start_create_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    await update.message.reply_text("🔧 Название промокода?")
    return PROMO_CODE_STATE


async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["promo_code"] = update.message.text.strip()
    await update.message.reply_text("💰 Сумма баллов по промокоду?")
    return PROMO_AMOUNT_STATE


async def ask_activations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["promo_amount"] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите число")
        return PROMO_AMOUNT_STATE
    await update.message.reply_text("♻️ Количество активаций?")
    return PROMO_ACTIVATIONS_STATE


async def save_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        activations = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Введите число")
        return PROMO_ACTIVATIONS_STATE

    code = context.user_data.get("promo_code")
    amount = context.user_data.get("promo_amount")
    if not code or amount is None:
        await update.message.reply_text("❌ Нет данных по промокоду")
        return ConversationHandler.END

    await promo_db.create_promo_code(code, amount, activations)
    await update.message.reply_text(
        f"✅ Промокод {code} создан: {amount} баллов, активаций: {activations}"
    )
    return ConversationHandler.END

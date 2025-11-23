import logging
import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import BOT_TOKEN, LOGS_DIR
from database.core import init_db
from handlers import client, order_flow, chat, admin, promos
from handlers.error_handler import error_handler

# Настройка логов
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    print("🔌 Подключаем базу данных...")
    init_db()
    
    print("🚀 Запуск бота...")
    app = Application.builder().token(BOT_TOKEN).build()

    # === КЛИЕНТ ===
    app.add_handler(CommandHandler("start", client.start))
    app.add_handler(CallbackQueryHandler(client.start, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(client.accept_rules, pattern="^rules_accept$"))
    app.add_handler(CallbackQueryHandler(client.profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(client.partners, pattern="^partners$"))
    app.add_handler(CallbackQueryHandler(client.my_history, pattern="^my_history$"))
    app.add_handler(CallbackQueryHandler(client.my_transactions, pattern="^my_transactions$"))
    app.add_handler(CallbackQueryHandler(client.my_order, pattern="^my_order_"))
    app.add_handler(CallbackQueryHandler(client.cli_approve, pattern="^cli_approve_"))
    app.add_handler(CallbackQueryHandler(client.cli_delete, pattern="^cli_delete_"))

    # === ОТЗЫВЫ ===
    review_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(client.ask_review, pattern="^write_review$")],
        states={
            client.REVIEW_STATE: [MessageHandler(filters.TEXT | filters.PHOTO, client.submit_review)]
        },
        fallbacks=[CallbackQueryHandler(client.start, pattern="^home$")]
    )
    app.add_handler(review_conv)

    # === ОФОРМЛЕНИЕ ЗАКАЗА ===
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_flow.start_order, pattern="^order_start$")],
        states={
            order_flow.TYPE: [CallbackQueryHandler(order_flow.get_type, pattern="^srv_")],
            order_flow.TOPIC: [
                MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT & ~filters.COMMAND, order_flow.get_topic),
                CallbackQueryHandler(order_flow.start_order, pattern="^back_to_type$")
            ],
            order_flow.DEADLINE: [CallbackQueryHandler(order_flow.get_deadline, pattern="^time_|^back_to_topic$")],
            order_flow.UPSELL: [CallbackQueryHandler(order_flow.get_upsell, pattern="^toggle_|^upsell_done$|^back_to_deadline$")],
            order_flow.PAY_CHOICE: [CallbackQueryHandler(order_flow.handle_payment_choice, pattern="^use_points_yes$|^use_points_no$")],
            order_flow.CONFIRM: [CallbackQueryHandler(order_flow.confirm_order, pattern="^submit_order$|^home$")]
        },
        fallbacks=[
            CallbackQueryHandler(client.start, pattern="^home$"),
            CallbackQueryHandler(order_flow.start_order, pattern="^order_start$")
        ]
    )
    app.add_handler(order_conv)

    # === АДМИНКА ===
    admin.setup(app)
    promos.setup(app)

    # === ЧАТ ===
    chat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(chat.chat_start, pattern="^adm_chat_|^chat_order_|^ord:chat:")],
        states={
            1: [
                MessageHandler(filters.ALL & ~filters.COMMAND, chat.chat_process),
                CallbackQueryHandler(chat.chat_start, pattern="^adm_chat_|^chat_order_|^ord:chat:"),
                CallbackQueryHandler(chat.cancel_chat, pattern="^chat_close$")
            ]
        },
        fallbacks=[CallbackQueryHandler(chat.cancel_chat, pattern="^adm_order_|^my_order_|^chat_close$")]
    )
    app.add_handler(chat_conv)
    
    app.add_error_handler(error_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, client.handle_thanks))

    print("💀 SYSTEM READY. GOD MODE UNLOCKED.")
    app.run_polling()

if __name__ == "__main__":
    main()
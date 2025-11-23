import logging
import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import BOT_TOKEN, LOGS_DIR
from database.core import init_db
from database import db as catalog_db
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
    catalog_db.seed_services()
    
    print("🚀 Запуск бота...")
    app = Application.builder().token(BOT_TOKEN).build()

    # === АДМИНКА (регистрируем первой) ===
    admin.setup(app)

    # === ПРОМО (вторым) ===
    promos.setup(app)

    # === ОФОРМЛЕНИЕ ЗАКАЗА ===
    order_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_flow.start_order, pattern="^order_start$")],
        states={
            order_flow.TYPE: [
                CallbackQueryHandler(order_flow.get_type, pattern="^srv_"),
                CallbackQueryHandler(order_flow.get_type, pattern="^consultation_request$"),
                CallbackQueryHandler(order_flow.get_type, pattern="^order_consult$")
            ],
            order_flow.SERVICE_CARD: [CallbackQueryHandler(order_flow.confirm_service, pattern="^srv_confirm_|^srv_back$")],
            order_flow.TOPIC: [
                MessageHandler(filters.Document.ALL | filters.PHOTO | filters.TEXT & ~filters.COMMAND, order_flow.get_topic),
                CallbackQueryHandler(order_flow.start_order, pattern="^back_to_type$")
            ],
            order_flow.DEADLINE: [CallbackQueryHandler(order_flow.get_deadline, pattern="^time_|^back_to_topic$")],
            order_flow.UPSELL: [CallbackQueryHandler(order_flow.get_upsell, pattern="^toggle_|^upsell_done$|^back_to_deadline$")],
            order_flow.PAY_CHOICE: [CallbackQueryHandler(order_flow.handle_payment_choice, pattern="^use_points_yes$|^use_points_no$")],
            order_flow.CONFIRM: [CallbackQueryHandler(order_flow.confirm_order, pattern="^submit_order$|^home$")],
            order_flow.CONSULT: [
                CallbackQueryHandler(order_flow.cancel_consultation, pattern="^consult_cancel$"),
                MessageHandler(
                    filters.Document.ALL | filters.PHOTO | filters.TEXT & ~filters.COMMAND,
                    order_flow.handle_consultation_request,
                ),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(client.start, pattern="^home$"),
            CallbackQueryHandler(order_flow.start_order, pattern="^order_start$")
        ]
    )
    app.add_handler(order_conv)

    # === КЛИЕНТ ===
    app.add_handler(CommandHandler("start", client.start))
    app.add_handler(CallbackQueryHandler(client.start, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(client.accept_rules, pattern="^rules_accept$"))
    app.add_handler(CallbackQueryHandler(client.profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(client.profile, pattern="^open_profile$"))
    app.add_handler(CallbackQueryHandler(client.show_price_list, pattern="^price_list$"))
    app.add_handler(CallbackQueryHandler(client.back_to_main_menu, pattern="^back_to_main_menu$"))
    app.add_handler(CallbackQueryHandler(client.show_price_card, pattern="^price_srv_"))
    app.add_handler(CallbackQueryHandler(client.show_code_of_honor, pattern="^code_honor$"))
    app.add_handler(MessageHandler(filters.Regex(r"^📜 Меню \(Цены\)$"), client.show_price_list_text))
    app.add_handler(MessageHandler(filters.Regex(r"^⚖️ Кодекс Чести \(Гарантии\)$"), client.show_code_of_honor))
    app.add_handler(CallbackQueryHandler(client.partners, pattern="^partners$"))
    app.add_handler(CallbackQueryHandler(client.my_history, pattern="^my_history$"))
    app.add_handler(CallbackQueryHandler(client.my_transactions, pattern="^my_transactions$"))
    app.add_handler(CallbackQueryHandler(client.my_order, pattern="^my_order_"))

    # === ОТЗЫВЫ ===
    review_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(client.ask_review, pattern="^write_review$")],
        states={
            client.REVIEW_STATE: [MessageHandler(filters.TEXT | filters.PHOTO, client.submit_review)]
        },
        fallbacks=[
            CallbackQueryHandler(client.cancel_review, pattern="^home$"),
            CallbackQueryHandler(client.cancel_review, pattern="^open_profile$"),
        ]
    )
    app.add_handler(review_conv)

    promo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(client.ask_promo_code, pattern="^enter_promo$")],
        states={
            client.PROMO_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, client.submit_promo_code),
                CallbackQueryHandler(client.profile, pattern="^open_profile$"),
                CallbackQueryHandler(client.start, pattern="^home$"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(client.profile, pattern="^open_profile$"),
            CallbackQueryHandler(client.start, pattern="^home$"),
        ],
        allow_reentry=True,
    )
    app.add_handler(promo_conv)

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
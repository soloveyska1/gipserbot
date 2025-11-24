import logging
import os
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    JobQueue,
    MessageHandler,
    TypeHandler,
    filters,
)

# Настройка путей
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    os.chdir(BASE_DIR)
except Exception:
    pass

from config import BOT_TOKEN, LOGS_DIR
from database.core import init_db
from database import db as catalog_db
from handlers import client, order_flow, chat, admin, promos
from handlers.error_handler import error_handler
from services.dashboard import LiveDashboard
import utils

# Логи
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
    job_queue = None
    try:
        job_queue = JobQueue()
    except RuntimeError as exc:
        logging.warning("JobQueue unavailable: %s", exc)
    builder = Application.builder().token(BOT_TOKEN)
    if job_queue:
        builder = builder.job_queue(job_queue)
    app = builder.build()

    # --- OBSERVABILITY: глобальный проводник ---
    app.add_handler(TypeHandler(Update, utils.wiretap_logger, block=False), group=-1)

    # --- LIVE DASHBOARD ---
    LiveDashboard().attach(app)

    # === АДМИНКА ===
    admin.setup(app)

    # === ПРОМО ===
    promos.setup(app)

    # === ОФОРМЛЕНИЕ ЗАКАЗА И КОНСУЛЬТАЦИЯ ===
    order_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(order_flow.start_order, pattern="^order_start$"),
            # ИСПРАВЛЕНИЕ: Добавили кнопку SOS как точку входа
            CallbackQueryHandler(order_flow.get_type, pattern="^consultation_request$")
        ],
        states={
            order_flow.TYPE: [
                CallbackQueryHandler(order_flow.get_type, pattern="^srv_"),
                CallbackQueryHandler(order_flow.get_type, pattern="^consultation_request$"),
                CallbackQueryHandler(order_flow.get_type, pattern="^order_consult$")
            ],
            order_flow.SERVICE_CARD: [
                CallbackQueryHandler(order_flow.confirm_service, pattern="^srv_confirm_|^srv_back$|back_to_type")
            ],
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
    app.add_handler(CallbackQueryHandler(client.play_daily_bonus, pattern="^daily_bonus$"))
    app.add_handler(CallbackQueryHandler(client.start_duel, pattern="^duel_start$"))
    app.add_handler(CallbackQueryHandler(client.resolve_duel, pattern="^duel_pick_"))
    app.add_handler(CallbackQueryHandler(client.draw_deadline_oracle, pattern="^deadline_oracle$"))
    app.add_handler(CallbackQueryHandler(client.show_price_list, pattern="^price_list$"))
    app.add_handler(CallbackQueryHandler(client.back_to_main_menu, pattern="^back_to_main_menu$"))
    app.add_handler(CallbackQueryHandler(client.show_price_card, pattern="^price_srv_"))
    app.add_handler(CallbackQueryHandler(client.show_code_of_honor, pattern="^code_honor$"))
    app.add_handler(MessageHandler(filters.Regex(r"^📜 Меню \(Цены\)$"), client.show_price_list_text))
    app.add_handler(MessageHandler(filters.Regex(r"^⚖️ Кодекс Чести \(Гарантии\)$"), client.show_code_of_honor))
    app.add_handler(CallbackQueryHandler(client.partners, pattern="^partners$"))
    app.add_handler(CallbackQueryHandler(client.my_history, pattern="^my_history$"))
    app.add_handler(CallbackQueryHandler(client.open_safe, pattern="^my_safe$"))
    app.add_handler(CallbackQueryHandler(client.my_transactions, pattern="^my_transactions$"))
    app.add_handler(CallbackQueryHandler(client.my_order, pattern="^my_order_"))
    app.add_handler(CallbackQueryHandler(client.hide_order_confirm, pattern="^hide_order_"))
    app.add_handler(CallbackQueryHandler(client.send_safe_file, pattern="^get_file_msg_"))

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

    # === ПРОМО ВВОД (КЛИЕНТ) ===
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
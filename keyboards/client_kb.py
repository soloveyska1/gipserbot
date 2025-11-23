from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_IDS

# Клиентские клавиатуры вынесены отдельно, чтобы избежать конфликтов с админской частью


def main_kb(user_id):
    keyboard = [
        [InlineKeyboardButton("🔥 СДЕЛАТЬ ЗАКАЗ", callback_data="order_start")],
        [
            InlineKeyboardButton("📜 Меню (Цены)", callback_data="price_list"),
            InlineKeyboardButton("🤠 Мое Досье", callback_data="profile"),
        ],
        [InlineKeyboardButton("⚖️ Кодекс Чести (Гарантии)", callback_data="code_honor")],
        [
            InlineKeyboardButton("👀 Слухи (Отзывы)", url="https://t.me/+Cls1cEPgPcMyZDJi"),
            InlineKeyboardButton("⭐ Позвать Шерифа (Саппорт)", url=f"tg://user?id={ADMIN_IDS[0]}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def deadline_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔥 СРОЧНО (1-3 дня) [+40%]", callback_data="time_urgent")],
            [InlineKeyboardButton("📅 В штатном режиме", callback_data="time_normal")],
            [InlineKeyboardButton("🔙 Назад к теме", callback_data="back_to_topic")],
        ]
    )


def upsell_kb(speech, pres, vip, p_speech, p_pres, p_vip):
    c_speech = "✅" if speech else "⬜️"
    c_pres = "✅" if pres else "⬜️"
    c_vip = "✅" if vip else "⬜️"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"{c_speech} Речь (+{p_speech}₽)", callback_data="toggle_speech")],
            [InlineKeyboardButton(f"{c_pres} Презентация (+{p_pres}₽)", callback_data="toggle_pres")],
            [InlineKeyboardButton(f"{c_vip} VIP Сопровождение (+{p_vip}₽)", callback_data="toggle_vip")],
            [InlineKeyboardButton("➡️ ГОТОВО (РАСЧЕТ)", callback_data="upsell_done")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_deadline")],
        ]
    )


def confirm_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ ПОДТВЕРДИТЬ ЗАКАЗ", callback_data="submit_order")],
            [InlineKeyboardButton("❌ Отмена", callback_data="home")],
        ]
    )


def points_choice_kb(points: int):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"✅ Использовать {points} баллов", callback_data="use_points_yes")],
            [InlineKeyboardButton("❌ Нет, оплачу полностью", callback_data="use_points_no")],
        ]
    )


def profile_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📦 Мои заказы", callback_data="my_history")],
            [InlineKeyboardButton("📜 История золота", callback_data="my_transactions")],
            [InlineKeyboardButton("💰 Партнерка (15%)", callback_data="partners")],
            [InlineKeyboardButton("✍️ Написать отзыв", callback_data="write_review")],
            [InlineKeyboardButton("🔙 В главное меню", callback_data="home")],
        ]
    )


def history_kb(orders):
    kb = []
    status_emoji = {"review": "🟡", "pending_pay": "💳", "work": "⚙️", "done": "✅", "cancel": "❌"}
    for o in orders[:5]:
        kb.append([InlineKeyboardButton(f"{status_emoji.get(o['status'], '?')} Заказ #{o['id']}", callback_data=f"my_order_{o['id']}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="profile")])
    return InlineKeyboardMarkup(kb)


def order_details_kb(oid, status="review"):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💬 ЧАТ С МЕНЕДЖЕРОМ", callback_data=f"chat_order_{oid}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="my_history")],
        ]
    )


def back_kb(callback_data):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]])


def rules_accept_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ С правилами ознакомлен и согласен", callback_data="rules_accept")]]
    )

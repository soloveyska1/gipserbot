from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_ID, ORDER_TYPES

def main_menu(user_id):
    kb = [
        [InlineKeyboardButton("⚡️ РАССЧИТАТЬ ЗАКАЗ", callback_data="new_order")],
        [InlineKeyboardButton("👤 Мой сейф (Профиль)", callback_data="profile"), InlineKeyboardButton("💎 Партнерка", callback_data="partners")],
        [InlineKeyboardButton("💬 Отзывы", url="https://t.me/durov"), InlineKeyboardButton("🆘 Саппорт", url=f"tg://user?id={ADMIN_ID}")],
    ]
    return InlineKeyboardMarkup(kb)

def type_selector():
    kb = []
    for k, v in ORDER_TYPES.items():
        kb.append([InlineKeyboardButton(f"{v['icon']} {v['name']}", callback_data=f"type_{k}")])
    kb.append([InlineKeyboardButton("🔙 Отмена", callback_data="home")])
    return InlineKeyboardMarkup(kb)

def deadline_selector():
    # Психология: Срочно всегда дороже
    kb = [
        [InlineKeyboardButton("🔥 Горит (3 дня) [+30%]", callback_data="day_3")],
        [InlineKeyboardButton("⚡️ Неделя (7 дней)", callback_data="day_7")],
        [InlineKeyboardButton("📅 Спокойно (14+ дней)", callback_data="day_14")],
        [InlineKeyboardButton("🔙 Назад", callback_data="new_order")]
    ]
    return InlineKeyboardMarkup(kb)

def confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 ПОДТВЕРДИТЬ ЗАКАЗ", callback_data="submit_order")],
        [InlineKeyboardButton("✏️ Изменить", callback_data="new_order")]
    ])

def admin_dashboard():
    kb = [
        [InlineKeyboardButton("📦 Активные заказы", callback_data="adm_orders"), InlineKeyboardButton("💰 Пополнить юзера", callback_data="adm_balance")],
        [InlineKeyboardButton("📢 Рассылка всем", callback_data="adm_broadcast"), InlineKeyboardButton("🎫 Промокоды", callback_data="adm_promo")],
        [InlineKeyboardButton("🔙 Выход", callback_data="home")]
    ]
    return InlineKeyboardMarkup(kb)
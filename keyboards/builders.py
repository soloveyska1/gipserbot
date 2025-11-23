from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_ID

def main_menu(user_id):
    kb = [
        [InlineKeyboardButton("⚡️ РАССЧИТАТЬ ЗАКАЗ", callback_data="new_order")],
        [InlineKeyboardButton("👤 Мой сейф (Профиль)", callback_data="profile"), InlineKeyboardButton("💎 Партнерка", callback_data="partners")],
        [InlineKeyboardButton("💬 Отзывы", url="https://t.me/c/178428445/1"), InlineKeyboardButton("🆘 Саппорт", url=f"tg://user?id={ADMIN_ID}")],
    ]
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


def create_dynamic_service_keyboard(services, *, prefix: str = "srv_", back_cb: str = "home", back_text: str = "🔙 В меню"):
    """Собирает клавиатуру услуг из актуальных данных БД."""
    rows = []
    for srv in services:
        rows.append(
            [InlineKeyboardButton(f"{srv.get('name', 'Услуга')} — {srv.get('price', 0)}₽", callback_data=f"{prefix}{srv['id']}")]
        )
    rows.append([InlineKeyboardButton(back_text, callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_ID


def main_menu(user_id):
    kb = [
        [InlineKeyboardButton("⚡️ РАССЧИТАТЬ ЗАКАЗ", callback_data="new_order")],
        [
            InlineKeyboardButton("👤 Мой сейф (Профиль)", callback_data="profile"),
            InlineKeyboardButton("💎 Партнерка", callback_data="partners"),
        ],
        [
            InlineKeyboardButton("💬 Отзывы", url="https://t.me/c/178428445/1"),
            InlineKeyboardButton("🆘 Саппорт", url=f"tg://user?id={ADMIN_ID}"),
        ],
    ]
    return InlineKeyboardMarkup(kb)


def deadline_selector():
    # Психология: Срочно всегда дороже
    kb = [
        [InlineKeyboardButton("🔥 Горит (3 дня) [+30%]", callback_data="day_3")],
        [InlineKeyboardButton("⚡️ Неделя (7 дней)", callback_data="day_7")],
        [InlineKeyboardButton("📅 Спокойно (14+ дней)", callback_data="day_14")],
        [InlineKeyboardButton("🔙 Назад", callback_data="new_order")],
    ]
    return InlineKeyboardMarkup(kb)


def confirm_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🚀 ПОДТВЕРДИТЬ ЗАКАЗ", callback_data="submit_order")],
            [InlineKeyboardButton("✏️ Изменить", callback_data="new_order")],
        ]
    )


def admin_dashboard():
    kb = [
        [
            InlineKeyboardButton("📦 Активные заказы", callback_data="adm_orders"),
            InlineKeyboardButton("💰 Пополнить юзера", callback_data="adm_balance"),
        ],
        [
            InlineKeyboardButton("📢 Рассылка всем", callback_data="adm_broadcast"),
            InlineKeyboardButton("🎫 Промокоды", callback_data="adm_promo"),
        ],
        [InlineKeyboardButton("🔙 Выход", callback_data="home")],
    ]
    return InlineKeyboardMarkup(kb)


def create_dynamic_service_keyboard(
    services,
    *,
    prefix: str = "srv_",
    back_cb: str = "home",
    back_text: str = "🔙 В меню",
):
    """Собирает клавиатуру услуг с иерархией и кнопкой консультации."""

    def make_button(srv):
        name = srv.get("name", "Услуга")
        price = srv.get("price", 0)
        label = name
        if name.startswith("Курсовая"):
            label = f"🔥 {label}"
        elif name.startswith("Магистерская"):
            label = f"{label} — {price}₽"
        elif not name.startswith("Диплом"):
            priced = f"{label} — {price}₽"
            label = priced if len(priced) <= 40 else label
        return InlineKeyboardButton(label, callback_data=f"{prefix}{srv['id']}")

    rows = []

    priority_order = ["Диплом", "Магистерская", "Курсовая"]
    prioritized = []
    for target in priority_order:
        srv = next((s for s in services if s.get("name", "").startswith(target)), None)
        if srv:
            prioritized.append(srv)
            rows.append([make_button(srv)])

    standard_services = [
        srv for srv in services if srv not in prioritized
    ]

    for i in range(0, len(standard_services), 2):
        pair = standard_services[i : i + 2]
        row = [make_button(pair[0])]
        if len(pair) > 1:
            row.append(make_button(pair[1]))
        rows.append(row)

    rows.append(
        [InlineKeyboardButton("🆘 Не знаю, что выбрать (Спросить)", callback_data="consultation_request")]
    )
    rows.append([InlineKeyboardButton(back_text, callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def create_orders_history_keyboard(orders):
    """Строит список заказов с иконками статусов и сервисами."""
    status_icon = {
        "new": "⏳",
        "checking": "⏳",
        "pending_pay": "⏳",
        "paid": "⏳",
        "work": "🤠",
        "completed": "✅",
        "done": "✅",
        "cancel": "❌",
        "canceled": "❌",
        "cancelled": "❌",
    }

    rows = []
    for order in orders:
        icon = status_icon.get(order.get("status"), "?")
        label = f"{icon} Заказ #{order['id']} | {order.get('service_type', 'Услуга')}"
        rows.append([InlineKeyboardButton(label, callback_data=f"my_order_{order['id']}")])

    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="profile")])
    return InlineKeyboardMarkup(rows)

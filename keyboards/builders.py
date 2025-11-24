from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_IDS

def main_menu(user_id):
    kb = [
        [InlineKeyboardButton("🔥 СДЕЛАТЬ ЗАКАЗ", callback_data="order_start")],
        [
            InlineKeyboardButton("📜 Прайс", callback_data="price_list"),
            InlineKeyboardButton("🤠 Досье", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("⚖️ Гарантии", callback_data="code_honor"),
            InlineKeyboardButton("💬 Отзывы", url="https://t.me/c/178428445/1"),
        ],
        [InlineKeyboardButton("🆘 Позвать Шерифа", url=f"tg://user?id={ADMIN_IDS[0]}")]
    ]
    return InlineKeyboardMarkup(kb)

def deadline_selector():
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
    back_text: str = "🔙 В главное меню",
):
    """Эстетичная сборка клавиатуры услуг."""

    def format_price(p: int) -> str:
        """Делает цену компактной: 55000 -> 55к, 2500 -> 2,5к."""

        if p >= 1000:
            short = p / 1000
            if short >= 10:
                formatted = f"{int(round(short))}"
            else:
                formatted = f"{short:.1f}".rstrip("0").rstrip(".")
            return f"{formatted.replace('.', ',')}к"
        return str(p)

    def clean_service_name(raw_name: str) -> str:
        base = raw_name.split("(")[0].strip()
        return base

    def make_button(srv: dict, full_width: bool = False) -> InlineKeyboardButton:
        raw_name = srv.get("name", "Услуга")
        clean_name = clean_service_name(raw_name)

        emoji = ""
        if "Диплом" in raw_name:
            emoji = "🎓 "
        elif "Магистерская" in raw_name:
            emoji = "🎩 "
        elif "Курсовая" in raw_name:
            emoji = "🔥 "
        elif "Эссе" in raw_name:
            emoji = "✍️ "
        elif "Отчет" in raw_name:
            emoji = "📋 "
        elif "Экзамен" in raw_name:
            emoji = "🎲 "
        elif "Презентация" in raw_name:
            emoji = "💻 "
        elif "Речь" in raw_name:
            emoji = "🎤 "
        elif "VIP" in raw_name:
            emoji = "👑 "

        price = int(srv.get("price", 0) or 0)
        price_fmt = format_price(price)

        if full_width:
            label = f"{emoji}{clean_name} — {price_fmt}₽"
        else:
            label = f"{emoji}{clean_name} | {price_fmt}"

        return InlineKeyboardButton(label, callback_data=f"{prefix}{srv['id']}")

    rows: list[list[InlineKeyboardButton]] = []

    def is_high_ticket(svc: dict) -> bool:
        title = svc.get("name", "")
        return any(key in title for key in ("Диплом", "Курсовая", "VIP"))

    priority_items = [s for s in services if is_high_ticket(s)]
    for srv in priority_items:
        rows.append([make_button(srv, full_width=True)])

    standard_services = [s for s in services if s not in priority_items]

    current_row: list[InlineKeyboardButton] = []
    for srv in standard_services:
        current_row.append(make_button(srv, full_width=False))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    rows.append(
        [InlineKeyboardButton("🆘 Не знаю, что выбрать", callback_data="consultation_request")]
    )
    rows.append([InlineKeyboardButton(back_text, callback_data=back_cb)])

    return InlineKeyboardMarkup(rows)

def create_orders_history_keyboard(orders):
    """Строит список заказов: Иконка + Тип + Тема (обрез)"""

    status_icon = {
        "new": "🆕",  # Новый
        "checking": "🟡",  # На проверке
        "pending_pay": "💳",  # Ждет оплаты
        "paid": "💸",  # Оплачен
        "work": "⚙️",  # В работе
        "norm_control": "🧭",  # Нормоконтроль
        "edits": "✏️",  # Правки
        "completed": "✅",  # Готов
        "done": "✅",  # Готов
        "cancel": "❌",  # Отменен
    }

    rows = []
    for order in orders:
        icon = status_icon.get(order.get("status"), "📦")

        raw_type = order.get("service_type") or "Заказ"
        srv_type = raw_type.split("(")[0].strip()

        topic = order.get("topic", "Без темы")
        if len(topic) > 20:
            topic = topic[:20] + "..."

        label = f"{icon} {srv_type} | {topic}"

        rows.append([InlineKeyboardButton(label, callback_data=f"my_order_{order['id']}")])

    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="profile")])
    return InlineKeyboardMarkup(rows)

def back_kb(callback_data):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]])
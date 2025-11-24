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


# === PREMIUM ORDER SHOWCASE ===
def order_showcase_kb(services: list[dict]):
    """Builds the curated Wild West showcase keyboard with priority rows."""

    def find_by_keyword(keyword: str, used_ids: set[int]):
        for svc in services:
            if svc.get("id") in used_ids:
                continue
            if keyword.lower() in svc.get("name", "").lower():
                used_ids.add(svc["id"])
                return InlineKeyboardButton(label_for_service(svc), callback_data=f"srv_{svc['id']}")
        return None

    def find_next_unused(used_ids: set[int]):
        for svc in services:
            if svc.get("id") not in used_ids:
                used_ids.add(svc["id"])
                return InlineKeyboardButton(label_for_service(svc), callback_data=f"srv_{svc['id']}")
        return None

    def label_for_service(svc: dict) -> str:
        name = svc.get("name", "Услуга")
        clean = name.split("(")[0].strip()
        emoji = ""
        if "диплом" in name.lower():
            emoji = "🎓 "
        elif "курсов" in name.lower():
            emoji = "🔥 "
        elif "эссе" in name.lower():
            emoji = "✍️ "
        elif "отчет" in name.lower():
            emoji = "📋 "
        elif "речь" in name.lower():
            emoji = "🎤 "
        elif "презента" in name.lower():
            emoji = "💻 "
        return f"{emoji}{clean}" if emoji else clean

    used: set[int] = set()
    rows: list[list[InlineKeyboardButton]] = []

    dip_btn = find_by_keyword("диплом", used)
    if dip_btn:
        rows.append([dip_btn])

    kurs_btn = find_by_keyword("курсов", used)
    if kurs_btn:
        rows.append([kurs_btn])

    essay_btn = find_by_keyword("эссе", used) or find_next_unused(used)
    report_btn = find_by_keyword("отчет", used) or find_next_unused(used)
    grid_row1 = [btn for btn in (essay_btn, report_btn) if btn]
    if grid_row1:
        rows.append(grid_row1)

    speech_btn = find_by_keyword("речь", used) or find_next_unused(used)
    pres_btn = find_by_keyword("презента", used) or find_next_unused(used)
    grid_row2 = [btn for btn in (speech_btn, pres_btn) if btn]
    if grid_row2:
        rows.append(grid_row2)

    rows.append([InlineKeyboardButton("🔙 Назад в лобби", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def deadline_heat_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔥 ОГОНЬ (1-3 дня) x1.4", callback_data="deadline_hot")],
            [InlineKeyboardButton("⚡️ В ТЕМПЕ (4-7 дней) x1.15", callback_data="deadline_fast")],
            [InlineKeyboardButton("🐢 ЗАРАНЕЕ (Неделя+) x1.0", callback_data="deadline_calm")],
            [InlineKeyboardButton("🔙 Назад к теме", callback_data="back_to_topic")],
        ]
    )


def upsell_toggle_kb(state: dict):
    def button(label: str, key: str, price: int):
        prefix = "🟢 ✔" if state.get(key) else "🔴"
        return InlineKeyboardButton(f"{prefix} {label} (+{price})", callback_data=f"upsell_toggle_{key}")

    rows = [
        [button("VIP", "vip", 2500)],
        [button("Речь", "speech", 1500)],
        [button("Презентация", "pres", 2000)],
        [InlineKeyboardButton("➡️ ГОТОВО (К ОПЛАТЕ)", callback_data="upsell_done")],
        [InlineKeyboardButton("🔙 Назад к срокам", callback_data="back_to_deadline")],
    ]
    return InlineKeyboardMarkup(rows)


def payment_smart_kb(balance: int, max_discount: int):
    rows: list[list[InlineKeyboardButton]] = []
    if max_discount > 0 and balance >= max_discount:
        rows.append([InlineKeyboardButton(f"💎 Списать ВСЁ ({max_discount})", callback_data="pay_all")])

    partial_row: list[InlineKeyboardButton] = []
    for step in (1000, 500):
        if balance >= step and max_discount >= step:
            partial_row.append(InlineKeyboardButton(f"💎 -{step}", callback_data=f"pay_minus_{step}"))
    if partial_row:
        rows.append(partial_row)

    rows.append([InlineKeyboardButton("✍️ Своя сумма", callback_data="pay_custom")])
    rows.append([InlineKeyboardButton("❌ Не тратить (Коплю)", callback_data="pay_skip")])
    return InlineKeyboardMarkup(rows)

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
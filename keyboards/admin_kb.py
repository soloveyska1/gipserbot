from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📦 Заказы", callback_data="admin_orders")],
            [InlineKeyboardButton("⚙️ Прайс", callback_data="admin_prices")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("👀 Статистика", callback_data="admin_stats")],
        ]
    )


def orders_list(orders, page: int = 0):
    kb = []
    start = page * 5
    end = start + 5
    current = orders[start:end]

    status_emoji = {
        "checking": "🟡",
        "pending_pay": "💳",
        "paid": "💸",
        "work": "⚙️",
        "norm_control": "🧭",
        "edits": "✏️",
        "suspended": "⏸",
        "done": "✅",
        "cancel": "❌",
    }

    for o in current:
        kb.append(
            [
                InlineKeyboardButton(
                    f"{status_emoji.get(o['status'], '?')} #{o['id']} | {o.get('final_price', o['price'])}₽",
                    callback_data=f"admin_order_{o['id']}",
                )
            ]
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"admin_orders_page_{page-1}"))
    if end < len(orders):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"admin_orders_page_{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_main")])
    return InlineKeyboardMarkup(kb)


def order_actions(oid: int, status: str):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💬 Чат заказа", callback_data=f"adm_chat_{oid}")],
        [
            InlineKeyboardButton("⚙️ В работу", callback_data=f"admin_set_status_{oid}_work"),
            InlineKeyboardButton("✅ Выполнен", callback_data=f"admin_set_status_{oid}_done"),
        ],
        [
            InlineKeyboardButton("💳 Ждёт оплаты", callback_data=f"admin_set_status_{oid}_pending_pay"),
            InlineKeyboardButton("💸 Оплачен", callback_data=f"admin_set_status_{oid}_paid"),
        ],
        [
            InlineKeyboardButton("❌ Отменить", callback_data=f"admin_set_status_{oid}_cancel"),
        ],
        [
            InlineKeyboardButton("🧭 Нормконтроль", callback_data=f"admin_set_status_{oid}_norm_control"),
            InlineKeyboardButton("✏️ Правки", callback_data=f"admin_set_status_{oid}_edits"),
        ],
            [InlineKeyboardButton("⏸ Приостановить", callback_data=f"admin_set_status_{oid}_suspended")],
            [InlineKeyboardButton("⬅️ Назад к списку", callback_data="admin_orders")],
        ]
    )


def prices_menu(prices: dict):
    kb = []
    for key, val in prices.items():
        kb.append([InlineKeyboardButton(f"{val['title']} — {val['price']}₽", callback_data=f"admin_price_{key}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_main")])
    return InlineKeyboardMarkup(kb)


def cancel_kb(back_to: str):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("❌ Отмена", callback_data=back_to)],
        ]
    )

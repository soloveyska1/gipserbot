from dataclasses import dataclass
from typing import Iterable, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


@dataclass
class OrderCallback:
    action: str
    id: int = 0
    payload: str = ""

    prefix: str = "ord"

    def pack(self) -> str:
        payload = self.payload if self.payload is not None else ""
        safe_payload = payload.replace(":", "_") if payload else "-"
        return f"{self.prefix}:{self.action}:{self.id}:{safe_payload}"

    @classmethod
    def parse(cls, data: str):
        try:
            prefix, action, raw_id, payload = data.split(":", 3)
        except ValueError:
            return None
        if prefix != cls.prefix:
            return None
        try:
            oid = int(raw_id)
        except ValueError:
            return None
        if payload == "-":
            payload = ""
        return cls(action=action, id=oid, payload=payload)


@dataclass
class UserCallback:
    action: str
    id: int
    page: int = 0

    prefix: str = "usr"

    def pack(self) -> str:
        return f"{self.prefix}:{self.action}:{self.id}:{self.page}"

    @classmethod
    def parse(cls, data: str) -> Optional["UserCallback"]:
        try:
            prefix, action, raw_id, raw_page = data.split(":", 3)
        except ValueError:
            return None
        if prefix != cls.prefix:
            return None
        try:
            parsed_id = int(raw_id)
            page = int(raw_page)
        except ValueError:
            return None
        return cls(action=action, id=parsed_id, page=page)


@dataclass
class StatsCallback:
    action: str
    prefix: str = "stat"

    def pack(self) -> str:
        return f"{self.prefix}:{self.action}:0:0"

    @classmethod
    def parse(cls, data: str) -> Optional["StatsCallback"]:
        parts = data.split(":")
        if len(parts) < 2:
            return None
        prefix, action = parts[0], parts[1]
        if prefix != cls.prefix:
            return None
        return cls(action=action)


def main_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 Клиенты", callback_data=UserCallback(action="list", id=0, page=0).pack())],
            [InlineKeyboardButton("📦 Заказы", callback_data=OrderCallback(action="list", id=0).pack())],
            [InlineKeyboardButton("⚙️ Прайс", callback_data="admin_prices")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("👀 Статистика", callback_data=StatsCallback(action="view").pack())],
        ]
    )


def get_services_editor_kb(services: Iterable[dict]):
    kb: list[list[InlineKeyboardButton]] = []
    for svc in services:
        label = f"{svc['name']} — {svc['price']}₽"
        kb.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"edit_svc_{svc['id']}",
                )
            ]
        )
    kb.append([InlineKeyboardButton("➕ Добавить услугу", callback_data="add_service")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_main")])
    return InlineKeyboardMarkup(kb)


def service_actions_kb(service_id: int):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ Название", callback_data=f"svc_edit_name_{service_id}")],
            [InlineKeyboardButton("💰 Цена", callback_data=f"svc_edit_price_{service_id}")],
            [InlineKeyboardButton("📝 Описание", callback_data=f"svc_edit_desc_{service_id}")],
            [InlineKeyboardButton("🗑 Удалить", callback_data=f"svc_delete_{service_id}")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="admin_prices")],
        ]
    )


def orders_list(orders, page: int = 0, current_filter: str = "all"):
    kb = []
    start = page * 5
    end = start + 5
    current = orders[start:end]

    def _tab(label: str, key: str) -> InlineKeyboardButton:
        is_active = current_filter == key
        text = f"[✅ {label}]" if is_active else label
        cb = f"ord:filter:{key}" if key != "search" else "ord:search"
        return InlineKeyboardButton(text, callback_data=cb)

    kb.append(
        [
            _tab("📁 Все", "all"),
            _tab("⚡️ Актив", "active"),
            _tab("💰 Оплата", "payment"),
            _tab("🔍 Поиск", "search"),
        ]
    )

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
                    callback_data=OrderCallback(action="view", id=o["id"]).pack(),
                )
            ]
        )

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️", callback_data=OrderCallback(action="list", id=page - 1).pack()
            )
        )
    if end < len(orders):
        nav.append(
            InlineKeyboardButton(
                "➡️", callback_data=OrderCallback(action="list", id=page + 1).pack()
            )
        )
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_main")])
    return InlineKeyboardMarkup(kb)


def order_actions(oid: int, status: str, user_id: int | None = None):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 Чат заказа",
                    callback_data=OrderCallback(action="chat", id=oid).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    "⚙️ В работу", callback_data=OrderCallback(action="status", id=oid, payload="work").pack()
                ),
                InlineKeyboardButton(
                    "✅ Выполнен",
                    callback_data=OrderCallback(action="status", id=oid, payload="done").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    "💳 Ждёт оплаты",
                    callback_data=OrderCallback(action="status", id=oid, payload="pending_pay").pack(),
                ),
                InlineKeyboardButton(
                    "💸 Оплачен",
                    callback_data=OrderCallback(action="status", id=oid, payload="paid").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Отменить",
                    callback_data=OrderCallback(action="status", id=oid, payload="cancel").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    "🧭 Нормконтроль",
                    callback_data=OrderCallback(action="status", id=oid, payload="norm_control").pack(),
                ),
                InlineKeyboardButton(
                    "✏️ Правки",
                    callback_data=OrderCallback(action="status", id=oid, payload="edits").pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏸ Приостановить",
                    callback_data=OrderCallback(action="status", id=oid, payload="suspended").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    "👤 Профиль",
                    callback_data=OrderCallback(action="user", id=user_id or 0, payload=str(oid)).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    "💀 DELETE PERMANENTLY",
                    callback_data=OrderCallback(action="hard_delete", id=oid).pack(),
                )
            ],
            [InlineKeyboardButton("⬅️ Назад к списку", callback_data=OrderCallback(action="list", id=0).pack())],
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


def user_profile_kb(user_id: int, order_id: int | None = None):
    back_target = OrderCallback(action="view", id=order_id or 0).pack() if order_id else OrderCallback(action="list", id=0).pack()
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Начислить баллы",
                    callback_data=OrderCallback(action="give", id=user_id, payload=str(order_id or 0)).pack(),
                ),
                InlineKeyboardButton(
                    "➖ Списать баллы",
                    callback_data=OrderCallback(action="take", id=user_id, payload=str(order_id or 0)).pack(),
                ),
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data=back_target)],
        ]
    )


def get_users_list_kb(users: Iterable[dict], page: int = 0) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    users_list = list(users)
    for user in users_list:
        uname = f"@{user['username']}" if user.get("username") else "—"
        label = f"{user.get('full_name') or 'Без имени'} ({uname}) | {user.get('balance', 0)}"
        kb.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=UserCallback(action="view", id=user["user_id"], page=page).pack(),
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️", callback_data=UserCallback(action="list", id=0, page=page - 1).pack()
            )
        )
    if len(users_list) >= 10:
        nav.append(
            InlineKeyboardButton(
                "➡️", callback_data=UserCallback(action="list", id=0, page=page + 1).pack()
            )
        )
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin_main")])
    return InlineKeyboardMarkup(kb)


def user_orders_kb(orders: Iterable[dict], back_cb: str) -> InlineKeyboardMarkup:
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

    kb: list[list[InlineKeyboardButton]] = []
    has_orders = False
    for order in orders:
        has_orders = True
        price = order.get("final_price", order.get("price", 0))
        label = f"#{order['id']} | {status_emoji.get(order['status'], '?')} | {price}₽"
        kb.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=OrderCallback(action="view", id=order["id"]).pack(),
                )
            ]
        )

    if not has_orders:
        kb.append([InlineKeyboardButton("— Нет заказов —", callback_data=back_cb)])

    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(kb)


def get_user_profile_kb(user_id: int, is_banned: bool, page: int = 0) -> InlineKeyboardMarkup:
    ban_label = "✅ Разбанить" if is_banned else "🚫 Забанить"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✉️ DM", callback_data=UserCallback(action="msg", id=user_id, page=page).pack()
                ),
                InlineKeyboardButton(
                    "📦 Заказы", callback_data=UserCallback(action="orders", id=user_id, page=page).pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    "➕ Баллы", callback_data=UserCallback(action="points_add", id=user_id, page=page).pack()
                ),
                InlineKeyboardButton(
                    "➖ Баллы", callback_data=UserCallback(action="points_sub", id=user_id, page=page).pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    ban_label, callback_data=UserCallback(action="ban", id=user_id, page=page).pack()
                ),
                InlineKeyboardButton(
                    "📝 Заметка", callback_data=UserCallback(action="note", id=user_id, page=page).pack()
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад", callback_data=UserCallback(action="list", id=0, page=page).pack()
                )
            ],
        ]
    )


def stats_menu():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📉 Сбросить статистику", callback_data=StatsCallback(action="reset").pack()
                )
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="admin_main")],
        ]
    )


def broadcast_audience_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌐 Все", callback_data="bc_aud_all"),
                InlineKeyboardButton("🔥 Активные", callback_data="bc_aud_active"),
                InlineKeyboardButton("💤 Молчуны", callback_data="bc_aud_silent"),
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_main")],
        ]
    )


def broadcast_confirm_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Отправить", callback_data="bc_confirm_yes")],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_main")],
        ]
    )

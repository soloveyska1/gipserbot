from dataclasses import dataclass
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


def main_menu():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📦 Заказы", callback_data=OrderCallback(action="list", id=0).pack())],
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

from datetime import datetime

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


def _format_cooldown(seconds: int | float) -> str:
    if not seconds or seconds < 0:
        return "0ч 0м"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}ч {minutes}м"


def profile_kb(bonus_status: dict | None = None):
    btn_text = "🎰 Испытать удачу"
    if bonus_status:
        if bonus_status.get("available"):
            day = bonus_status.get("next_streak") or 1
            if day <= 0:
                day = 1
            btn_text = f"🎰 Испытать удачу (День {day})"
        else:
            cooldown = _format_cooldown(bonus_status.get("cooldown_seconds", 0))
            btn_text = f"⏳ Таймер: {cooldown}"

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📦 Мои заказы", callback_data="my_history")],
            [InlineKeyboardButton(btn_text, callback_data="daily_bonus")],
            [InlineKeyboardButton("🗄 Мой Сейф", callback_data="my_safe")],
            [InlineKeyboardButton("📜 История золота", callback_data="my_transactions")],
            [InlineKeyboardButton("🎟 Ввести промокод", callback_data="enter_promo")],
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
    rows = [[InlineKeyboardButton("💬 ЧАТ С МЕНЕДЖЕРОМ", callback_data=f"chat_order_{oid}")]]

    if status in {"done", "cancel", "completed"}:
        rows.append([InlineKeyboardButton("🗑 Убрать из истории", callback_data=f"hide_order_{oid}")])

    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="my_history")])

    return InlineKeyboardMarkup(rows)


def _format_safe_date(date_value):
    if not date_value:
        return "—"
    try:
        return datetime.fromisoformat(str(date_value)).strftime("%d.%m")
    except Exception:
        return str(date_value)[:10]


def safe_kb(files):
    rows = []
    for f in files:
        date_label = _format_safe_date(f.get("created_at"))
        rows.append(
            [
                InlineKeyboardButton(
                    f"📄 {f.get('service_type', 'Услуга')} | {date_label}",
                    callback_data=f"get_file_msg_{f.get('id')}",
                )
            ]
        )

    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="profile")])
    return InlineKeyboardMarkup(rows)


def back_kb(callback_data):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]])


def rules_accept_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ С правилами ознакомлен и согласен", callback_data="rules_accept")]]
    )

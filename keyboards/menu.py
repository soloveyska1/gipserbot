from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import SERVICES, ADMIN_IDS

# === КЛИЕНТСКИЕ КЛАВИАТУРЫ ===

def main_kb(user_id):
    kb = [
        [InlineKeyboardButton("🔥 СДЕЛАТЬ ЗАКАЗ", callback_data="order_start")],
        [InlineKeyboardButton("👤 Личный кабинет", callback_data="profile"), InlineKeyboardButton("💬 Оставить отзыв", callback_data="write_review")],
        [InlineKeyboardButton("🕸 Партнерка (15%)", callback_data="partners"), InlineKeyboardButton("👨‍💻 Саппорт", url=f"tg://user?id={ADMIN_IDS[0]}")],
        [InlineKeyboardButton("👀 Читать отзывы", url="https://t.me/c/178428445/1")]
    ]
    return InlineKeyboardMarkup(kb)

def services_kb():
    kb = []
    for k, v in SERVICES.items():
        kb.append([InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"srv_{k}")])
    kb.append([InlineKeyboardButton("🔙 В меню", callback_data="home")])
    return InlineKeyboardMarkup(kb)

def deadline_kb():
    kb = [
        [InlineKeyboardButton("🔥 СРОЧНО (1-3 дня) [+40%]", callback_data="time_urgent")],
        [InlineKeyboardButton("📅 В штатном режиме", callback_data="time_normal")],
        [InlineKeyboardButton("🔙 Назад к теме", callback_data="back_to_topic")]
    ]
    return InlineKeyboardMarkup(kb)

def upsell_kb(speech, pres, vip, p_speech, p_pres, p_vip):
    c_speech = "✅" if speech else "⬜️"
    c_pres = "✅" if pres else "⬜️"
    c_vip = "✅" if vip else "⬜️"
    
    kb = [
        [InlineKeyboardButton(f"{c_speech} Речь (+{p_speech}₽)", callback_data="toggle_speech")],
        [InlineKeyboardButton(f"{c_pres} Презентация (+{p_pres}₽)", callback_data="toggle_pres")],
        [InlineKeyboardButton(f"{c_vip} VIP Сопровождение (+{p_vip}₽)", callback_data="toggle_vip")],
        [InlineKeyboardButton("➡️ ГОТОВО (РАСЧЕТ)", callback_data="upsell_done")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_deadline")]
    ]
    return InlineKeyboardMarkup(kb)

def confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ПОДТВЕРДИТЬ ЗАКАЗ", callback_data="submit_order")],
        [InlineKeyboardButton("❌ Отмена", callback_data="home")]
    ])

def points_choice_kb(points: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Использовать {points} баллов", callback_data="use_points_yes")],
        [InlineKeyboardButton("❌ Нет, оплачу полностью", callback_data="use_points_no")]
    ])

def profile_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Мои заказы", callback_data="my_history")],
        [InlineKeyboardButton("💰 Транзакции", callback_data="my_transactions")],
        [InlineKeyboardButton("🔙 В меню", callback_data="home")]
    ])

def history_kb(orders):
    kb = []
    for o in orders[:5]:
        status_emoji = {"review": "🟡", "pending_pay": "💳", "work": "⚙️", "done": "✅", "cancel": "❌"}
        kb.append([InlineKeyboardButton(f"{status_emoji.get(o['status'], '?')} Заказ #{o['id']}", callback_data=f"my_order_{o['id']}")])
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="profile")])
    return InlineKeyboardMarkup(kb)

def order_details_kb(oid, status="review"):
    kb = [
        [InlineKeyboardButton("💬 ЧАТ С МЕНЕДЖЕРОМ", callback_data=f"chat_order_{oid}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="my_history")]
    ]
    return InlineKeyboardMarkup(kb)

# === АДМИНСКИЕ КЛАВИАТУРЫ (ИХ НЕ ХВАТАЛО) ===

def admin_main():
    kb = [
        [InlineKeyboardButton("📦 Заказы", callback_data="adm_orders_list"), InlineKeyboardButton("👥 Юзеры", callback_data="adm_users_list")],
        [InlineKeyboardButton("📢 Рассылка (Скоро)", callback_data="adm_broadcast"), InlineKeyboardButton("👀 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton("⚙️ Цены", callback_data="adm_settings")],
        [InlineKeyboardButton("🔙 Выход", callback_data="home")]
    ]
    return InlineKeyboardMarkup(kb)

def admin_users_list_kb(users, page=0):
    kb = []
    start = page * 5
    end = start + 5
    current_users = users[start:end]
    
    for u in current_users:
        kb.append([InlineKeyboardButton(f"{u['full_name']} ({u['balance']}₽)", callback_data=f"adm_user_{u['user_id']}")])
        
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_usr_page_{page-1}"))
    if end < len(users): nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_usr_page_{page+1}"))
    if nav: kb.append(nav)
    
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)

def admin_user_actions(uid, is_banned):
    ban_btn = InlineKeyboardButton("🔓 Разбанить", callback_data=f"unban_{uid}") if is_banned else InlineKeyboardButton("🚫 ЗАБАНИТЬ", callback_data=f"ban_{uid}")
    kb = [
        [ban_btn],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_users_list")]
    ]
    return InlineKeyboardMarkup(kb)

def admin_orders_list_kb(orders, page=0):
    kb = []
    start = page * 5
    end = start + 5
    current_orders = orders[start:end]
    
    status_emoji = {
        "checking": "🟡",
        "pending_pay": "💳",
        "work": "⚙️",
        "norm_control": "🧭",
        "edits": "✏️",
        "suspended": "⏸",
        "done": "✅",
        "cancel": "❌",
    }

    for o in current_orders:
        kb.append([
            InlineKeyboardButton(
                f"{status_emoji.get(o['status'], '?')} #{o['id']} | {o['price']}₽",
                callback_data=f"adm_order_{o['id']}",
            )
        ])
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_ord_page_{page-1}"))
    if end < len(orders): nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_ord_page_{page+1}"))
    if nav: kb.append(nav)
    
    kb.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(kb)

def admin_order_actions(oid, status):
    kb = [
        [InlineKeyboardButton("💬 ЧАТ ЗАКАЗА", callback_data=f"adm_chat_{oid}")],
        [InlineKeyboardButton("⚙️ В работу", callback_data=f"set_status_{oid}_work"), InlineKeyboardButton("✅ Выполнен", callback_data=f"set_status_{oid}_done")],
        [InlineKeyboardButton("💳 Ждет оплаты", callback_data=f"set_status_{oid}_pending_pay"), InlineKeyboardButton("❌ Отменить", callback_data=f"set_status_{oid}_cancel")],
        [InlineKeyboardButton("🧭 Нормконтроль", callback_data=f"set_status_{oid}_norm_control"), InlineKeyboardButton("✏️ Правки", callback_data=f"set_status_{oid}_edits")],
        [InlineKeyboardButton("⏸ Приостановить", callback_data=f"set_status_{oid}_suspended")],
        [InlineKeyboardButton("🔙 Назад к списку", callback_data="adm_orders_list")]
    ]
    return InlineKeyboardMarkup(kb)


def chat_kb(oid: int, is_admin: bool):
    """Клавиатура для внутреннего чата заказа."""
    back_cb = "adm_orders_list" if is_admin else f"my_order_{oid}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔒 Закрыть чат", callback_data="chat_close")],
            [InlineKeyboardButton("🔙 Назад", callback_data=back_cb)],
        ]
    )

def settings_kb():
    kb = [
        [InlineKeyboardButton("🎤 Речь", callback_data="set_price_speech"), InlineKeyboardButton("💻 Презентация", callback_data="set_price_pres")],
        [InlineKeyboardButton("👑 VIP", callback_data="set_price_vip")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ]
    # Add services dynamically
    srv_row = []
    for k, v in SERVICES.items():
        srv_row.append(InlineKeyboardButton(f"{v['emoji']} {v['name']}", callback_data=f"set_price_srv_{k}"))
        if len(srv_row) == 2:
            kb.insert(-1, srv_row)
            srv_row = []
    if srv_row: kb.insert(-1, srv_row)
    
    return InlineKeyboardMarkup(kb)

def back_kb(callback_data):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]])


def rules_accept_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ С правилами ознакомлен и согласен", callback_data="rules_accept")]]
    )
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_IDS

# --- MAIN MENU ---
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

# --- STEP 1: SHOWCASE ---
def service_showcase_kb():
    """Красивая витрина услуг"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎓 ДИПЛОМ (Золотая жила)", callback_data="srv_diploma")],
        [InlineKeyboardButton("🔥 КУРСОВАЯ (Партия в покер)", callback_data="srv_term")],
        [
            InlineKeyboardButton("✍️ Эссе", callback_data="srv_essay"),
            InlineKeyboardButton("📋 Отчет", callback_data="srv_practice")
        ],
        [
            InlineKeyboardButton("🎤 Речь", callback_data="srv_speech"),
            InlineKeyboardButton("💻 Слайды", callback_data="srv_pres")
        ],
        [
            InlineKeyboardButton("🎲 Экзамен", callback_data="srv_exam"),
            InlineKeyboardButton("👑 VIP", callback_data="srv_vip")
        ],
        [InlineKeyboardButton("🔙 Назад в лобби", callback_data="home")]
    ])

# --- STEP 2: DOSSIER NAVIGATION ---
def dossier_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤷‍♂️ У меня нет темы (Помощь)", callback_data="topic_help")],
        [InlineKeyboardButton("🔙 Назад к выбору услуги", callback_data="srv_back")]
    ])

# --- STEP 3: DEADLINE HEATMAP ---
def deadline_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 ОГОНЬ (1-3 дня) [x1.4]", callback_data="time_urgent")],
        [InlineKeyboardButton("⚡️ В ТЕМПЕ (4-7 дней) [x1.15]", callback_data="time_fast")],
        [InlineKeyboardButton("🐢 ЗАРАНЕЕ (Неделя+) [x1.0]", callback_data="time_normal")],
        [InlineKeyboardButton("🔙 Назад к теме", callback_data="back_to_topic")]
    ])

# --- STEP 4: UPSELL TOGGLES ---
def upsell_kb(state: dict):
    """Генерирует кнопки с галочками в зависимости от выбора"""
    # Цены (можно вынести в конфиг)
    prices = {"speech": 1500, "pres": 2000, "vip": 2500}
    
    def btn(key, label):
        is_active = state.get(key, False)
        mark = "🟢 ✔" if is_active else "🔴"
        text = f"{mark} {label} (+{prices[key]}₽)"
        return InlineKeyboardButton(text, callback_data=f"toggle_{key}")

    return InlineKeyboardMarkup([
        [btn("speech", "Речь для защиты")],
        [btn("pres", "Презентация")],
        [btn("vip", "VIP Сопровождение")],
        [InlineKeyboardButton("➡️ ГОТОВО (К ОПЛАТЕ)", callback_data="upsell_done")]
    ])

# --- STEP 5: POINTS CALCULATOR ---
def payment_kb(balance, max_discount):
    rows = []
    
    # 1. Кнопка списать всё (если есть что списывать)
    if balance > 0 and max_discount > 0:
        spend = min(balance, max_discount)
        rows.append([InlineKeyboardButton(f"💎 Списать ВСЁ (-{spend}₽)", callback_data="pay_all")])
    
    # 2. Фиксированные суммы
    presets = []
    if balance >= 1000 and max_discount >= 1000:
        presets.append(InlineKeyboardButton("💎 -1000₽", callback_data="pay_1000"))
    if balance >= 500 and max_discount >= 500:
        presets.append(InlineKeyboardButton("💎 -500₽", callback_data="pay_500"))
    if presets:
        rows.append(presets)
        
    # 3. Своя сумма и отказ
    rows.append([InlineKeyboardButton("✍️ Своя сумма", callback_data="pay_custom")])
    rows.append([InlineKeyboardButton("❌ Не тратить (Коплю)", callback_data="pay_zero")])
    
    return InlineKeyboardMarkup(rows)

# --- STEP 6: FINAL CONTRACT ---
def contract_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ ПОДПИСАТЬ КОНТРАКТ", callback_data="submit_order")],
        [InlineKeyboardButton("🧨 Сжечь и начать заново", callback_data="order_start")]
    ])

# --- STEP 7: AFTERMATH ---
def success_kb(order_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎰 Испытать удачу (Пока ждешь)", callback_data="daily_bonus")],
        [InlineKeyboardButton("💬 Чат заказа", callback_data=f"chat_order_{order_id}")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="home")]
    ])

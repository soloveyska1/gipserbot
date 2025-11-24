import logging
import os
import asyncio
import random
from collections import defaultdict, deque
from datetime import datetime
from html import escape
from typing import Deque, DefaultDict, Set

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from config import LOGS_DIR, LOG_CHANNEL_ID
from database import core as db

# Настройка логирования
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- WIRES & OBSERVABILITY ---
USER_ACTIONS: DefaultDict[int, Deque[str]] = defaultdict(lambda: deque(maxlen=10))
WATCHERS: DefaultDict[int, Set[int]] = defaultdict(set)

# Добавляем запись в файл
file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log'))
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

async def log_action(update, context, action):
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}): {action}")


ACTION_MAP = {
    # General
    "home": "🏠 Вышел в Главное Меню",
    "profile": "🤠 Открыл Профиль",
    "price_list": "📜 Смотрит Прайс",
    "partners": "🤝 Открыл Партнерку",
    "rules_accept": "✅ Принял Правила",
    # Orders
    "order_start": "🔥 Нажал: Сделать Заказ",
    "my_history": "📦 Смотрит Историю Заказов",
    "consultation_request": "🆘 Запросил Консультацию",
    "submit_order": "🚀 ПОДТВЕРДИЛ ЗАКАЗ",
    # Games
    "daily_bonus": "🎰 Крутит Слоты",
    "oracle_start": "🔮 Спрашивает Оракула",
    # Admin
    "admin_main": "👑 Зашел в Админку",
    "adm_orders": "📦 Смотрит Активные Заказы",
    "adm_stats": "📊 Смотрит Статистику",
}


def _compact(text: str | None, max_len: int = 100) -> str:
    if not text:
        return "—"
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _map_action(update: Update) -> tuple[str, str]:
    if getattr(update, "callback_query", None):
        return "🔘", "Нажал кнопку"
    if getattr(update, "message", None):
        msg = update.message
        if msg.text and msg.text.startswith("/"):
            return "⚡️", "Команда"
        return "💬", "Написал"
    return "ℹ️", "Действие"


def _parse_callback_data(data: str | None) -> tuple[str, str, str]:
    """Return human readable action line, detail, and tag."""
    if not data:
        return "Неизвестная кнопка", "—", "action"

    if data in ACTION_MAP:
        return ACTION_MAP[data], "Навигация по меню", "action"

    if data.startswith("srv_"):
        service_id = data.split("_", 1)[1]
        return f"Выбрал услугу ID {service_id}", "Выбор услуги", "action"

    if data.startswith("my_order_"):
        order_id = data.split("_")[-1]
        return f"Смотрит заказ #{order_id}", "Детализация заказа", "action"

    return f"Неизвестная кнопка ({data})", data, "action"


def _rank_badge(user: dict | None) -> str:
    if not user:
        return "🆕 Новичок"
    if user.get("total_spent", 0) > 20000:
        return "🐳 КИТ"
    if not user.get("is_alive", 1):
        return "👻 Призрак"
    if (user.get("orders_count", 0) or 0) == 0:
        return "🆕 Новичок"
    return "🎩 Клиент"


async def wiretap_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global interceptor that mirrors every step into the log channel and watcher feeds."""

    user = update.effective_user
    user_id = user.id if user else 0
    username = user.username if user else ""
    full_name = escape(user.full_name) if user else "Неизвестно"

    _, action_type = _map_action(update)
    action_text = "Неизвестное действие"
    content_text = "—"
    action_tag = "action"
    event_type: str | None = None

    if getattr(update, "callback_query", None):
        raw_data = update.callback_query.data or ""
        action_text, detail, action_tag = _parse_callback_data(raw_data)
        content_text = detail
        event_type = action_tag
    elif getattr(update, "message", None):
        msg = update.message
        text = msg.text or msg.caption or ""
        if text.startswith("/start"):
            action_text = "⚡️ Команда /start"
            event_type = "start"
        elif text.startswith("/"):
            action_text = f"⚡️ Ввел команду {text.split()[0]}"
            event_type = "command"
        else:
            action_text = "💬 Написал сообщение"
            event_type = "message"
        content_text = _compact(text, 50)
        action_tag = event_type or action_tag
    elif getattr(update, "inline_query", None):
        query = update.inline_query.query
        action_text = "🔍 Inline-запрос"
        content_text = _compact(query, 50)
        event_type = "inline"
        action_tag = event_type or action_tag

    user_snapshot = await db.get_user(user_id) if user_id else {}
    tags = await _behavior_tags(user_id) if user_id else []
    achievements = await compute_achievements(user_id) if user_id else []
    rank = _rank_badge(user_snapshot)
    total_spent = user_snapshot.get("total_spent", 0) if user_snapshot else 0

    badge_line = " ".join([rank] + tags + achievements).strip()

    username_part = f" @{escape(username)}" if username else ""
    header = (
        f"👤 <b>{full_name}</b> (<a href=\"tg://user?id={user_id}\">{user_id}</a>){username_part}\n"
        f"🏷 <b>Статус:</b> {badge_line} (💰 {total_spent} ₽)"
    )

    body = (
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"📍 <b>Действие:</b> {escape(action_text)}\n"
        f"📝 <b>Детали:</b> <i>{escape(content_text)}</i>"
    )

    footer = (
        "➖➖➖➖➖➖➖➖➖➖\n"
        "⚙️ <b>Управление:</b>\n"
        f"👉 <a href=\"tg://user?id={user_id}\">Написать в ЛС</a>\n"
        f"👁 <code>/watch {user_id}</code> | 🚫 <code>/ban {user_id}</code>\n"
        f"#u{user_id} #{action_tag}"
    )

    entry = "\n".join([header, body, footer])

    USER_ACTIONS[user_id].append(f"{action_type} | {content_text}")

    try:
        log_text = _compact(content_text)
        await db.add_action_log(user_id, log_text, event_type=event_type or action_tag, meta=log_text)
        if user_id:
            await db.update_user_field(user_id, "last_seen", datetime.utcnow())
    except Exception:
        logger.debug("DB wiretap logging failed", exc_info=True)

    if LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(
                LOG_CHANNEL_ID,
                entry,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            logger.debug("Wiretap send failed", exc_info=True)

    if user_id in WATCHERS:
        for admin_id in list(WATCHERS[user_id]):
            try:
                await context.bot.send_message(
                    admin_id,
                    entry,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception:
                continue


def get_recent_actions(user_id: int) -> list[str]:
    return list(USER_ACTIONS.get(user_id, []))


def add_watch(admin_id: int, target_id: int):
    WATCHERS[target_id].add(admin_id)


def remove_watch(admin_id: int, target_id: int | None = None):
    if target_id is None:
        for uid in list(WATCHERS.keys()):
            WATCHERS[uid].discard(admin_id)
            if not WATCHERS[uid]:
                WATCHERS.pop(uid, None)
        return
    WATCHERS[target_id].discard(admin_id)
    if not WATCHERS[target_id]:
        WATCHERS.pop(target_id, None)

def format_contact_link(contact: str) -> str:
    """Превращает текст контакта в кликабельную ссылку"""
    if not contact:
        return 'не указан'
    contact = contact.strip()
    safe_display = escape(contact)
    
    if contact.startswith('@') and len(contact) > 1:
        username = contact[1:].split()[0]
        if username and all(ch.isalnum() or ch == '_' for ch in username):
            return f'<a href="https://t.me/{username}">{safe_display}</a>'
            
    lower_contact = contact.lower()
    if lower_contact.startswith('http://') or lower_contact.startswith('https://'):
        return f'<a href="{escape(contact, quote=True)}">{safe_display}</a>'
        
    return safe_display

# --- HUMANIZATION ---

PHRASES = {
    "order_received": [
        "Принято. Дайте мне секунду, чтобы все оформить...",
        "Так, вижу заказ. Сейчас все посчитаем...",
        "Ого, интересная тема! Сейчас оформим.",
        "Записал. Момент...",
        "Ага, понял. Сейчас сделаем красиво."
    ],
    "done": [
        "Готово! Проверяйте.",
        "Сделано. Как вам?",
        "Все выполнено в лучшем виде.",
        "Принимайте работу!",
        "Ваш заказ готов. Жду вердикт."
    ],
    "thinking": [
        "Хм, дайте подумать...",
        "Так-так-так...",
        "Секундочку...",
        "Обрабатываю...",
        "Сейчас..."
    ]
}


async def _behavior_tags(user_id: int) -> list[str]:
    stats = await db.get_user_behavior_snapshot(user_id)
    tags: list[str] = []
    if stats.get("total_spent", 0) > 20000:
        tags.append("#WHALE")
    if (stats.get("orders_count", 0) or 0) == 0:
        tags.append("#NEW")
    if stats.get("price_clicks", 0) > 10 and stats.get("orders_count", 0) == 0:
        tags.append("#WINDOW_SHOPPER")
    total_actions = stats.get("total_actions", 0) or 0
    night_actions = stats.get("night_actions", 0) or 0
    if total_actions and night_actions / total_actions >= 0.8:
        tags.append("#NIGHT_OWL")
    return tags


async def get_behavior_tags(user_id: int) -> list[str]:
    return await _behavior_tags(user_id)


async def compute_achievements(user_id: int) -> list[str]:
    user = await db.get_user(user_id)
    orders = await db.get_user_orders(user_id) if hasattr(db, "get_user_orders") else []
    badges: list[str] = []

    if user and (user.get("orders_count", 0) or 0) > 0:
        badges.append("🥇")

    coursework_count = 0
    for o in orders:
        stype = (o.get("service_type") or "").lower()
        if "курс" in stype:
            coursework_count += 1
    if coursework_count >= 3:
        badges.append("🧠")

    if user and (user.get("bonus_streak", 0) or 0) >= 5:
        badges.append("🎰")

    return badges

async def send_typing(context, chat_id):
    """Simulate typing"""
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(random.uniform(0.5, 1.5))
    except: pass

def get_random_phrase(key):
    return random.choice(PHRASES.get(key, ["..."]))

def get_greeting(name):
    hour = datetime.now().hour
    if 6 <= hour < 12:
        t = "Доброе утро"
    elif 12 <= hour < 18:
        t = "Добрый день"
    elif 18 <= hour < 23:
        t = "Добрый вечер"
    else:
        t = "Доброй ночи"
    
    return f"🎩 <b>{t}, {name}.</b>"
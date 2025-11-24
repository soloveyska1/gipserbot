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


def _compact(text: str | None, max_len: int = 100) -> str:
    if not text:
        return "—"
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _map_action_type(update: Update) -> tuple[str, str]:
    if getattr(update, "callback_query", None):
        return "🔘", "Нажал кнопку"
    if getattr(update, "message", None):
        msg = update.message
        if msg.text and msg.text.startswith("/"):
            return "⚡️", "Команда"
        return "💬", "Написал"
    return "ℹ️", "Действие"


def _map_state(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("state_name") or context.chat_data.get("state_name") or "—"


def _map_callback_data(data: str | None) -> tuple[str, str, str | None]:
    """Return human readable content, tag, alert message if high value."""
    if not data:
        return "—", "action", None

    mapping = {
        "price_list": "Прайс-лист",
        "consultation_request": "Запрос консультации",
        "submit_order": "Отправка заказа",
        "order_start": "Новый заказ",
        "srv_diplom": "Услуга: Диплом",
        "srv_coursework": "Услуга: Курсовая",
        "srv_essay": "Услуга: Эссе",
        "balance_topup": "Пополнение баланса",
    }

    for key, label in mapping.items():
        if data.startswith(key):
            alert = None
            if key in {"srv_diplom", "balance_topup"}:
                alert = "🔥 Внимание: Клиент интересуется высокоценной услугой!"
            return label, "btn", alert

    return data, "btn", None


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

    action_emoji, action_type = _map_action_type(update)
    content_text = "—"
    action_tag = "action"
    alert = None
    event_type: str | None = None

    if getattr(update, "callback_query", None):
        raw_data = update.callback_query.data
        human, tag, alert = _map_callback_data(raw_data)
        content_text = escape(_compact(human))
        action_tag = tag
        event_type = tag
    elif getattr(update, "message", None):
        msg = update.message
        text = msg.text or msg.caption or ""
        content_text = escape(_compact(text))
        if text.startswith("/start"):
            event_type = "start"
        elif text.startswith("/"):
            event_type = "command"
        else:
            event_type = "message"
    elif getattr(update, "inline_query", None):
        query = update.inline_query.query
        content_text = escape(_compact(query))
        event_type = "inline"

    user_snapshot = await db.get_user(user_id) if user_id else {}
    tags = await _behavior_tags(user_id) if user_id else []
    badges = await compute_achievements(user_id) if user_id else []
    rank = _rank_badge(user_snapshot)
    total_spent = user_snapshot.get("total_spent", 0) if user_snapshot else 0

    tag_line = " ".join(tags + badges)
    tag_line = f" | {tag_line}" if tag_line else ""

    username_part = f" (@{escape(username)})" if username else ""
    header = (
        f"👤 <a href=\"tg://user?id={user_id}\"><b>{full_name}</b></a>{username_part}\n"
        f"🏆 <b>Ранг:</b> {rank} {tag_line} | 💰 <b>LTV:</b> {total_spent} ₽"
    )

    body = (
        f"{action_emoji} <b>{action_type}:</b>\n"
        f"└ <i>{content_text}</i>"
    )

    state_name = escape(_map_state(context))
    footer = (
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"📍 <b>Где:</b> {state_name}\n"
        "🛠 <b>Управление:</b>\n"
        f"<a href=\"tg://user?id={user_id}\">💬 Написать</a> | "
        f"<code>/watch {user_id}</code> | <code>/ban {user_id}</code>\n"
        f"#u{user_id} #{action_tag}"
    )

    parts = [header, "➖➖➖➖➖➖➖➖➖➖", body]
    if alert:
        parts.append(alert)
    parts.append(footer)
    entry = "\n".join(parts)

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
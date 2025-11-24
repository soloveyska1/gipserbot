import logging
import os
import asyncio
import random
from collections import defaultdict, deque
from datetime import datetime
from html import escape
from typing import Deque, DefaultDict, Set

from telegram import Update
from telegram.constants import ChatAction
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


def _compact(text: str | None, max_len: int = 200) -> str:
    if not text:
        return "—"
    text = str(text)
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


async def wiretap_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global interceptor that mirrors every step into the log channel and watcher feeds."""

    user_id = update.effective_user.id if update.effective_user else 0
    action = "Update"
    data: str | None = None
    event_type: str | None = None

    if getattr(update, "callback_query", None):
        action = "CallbackQuery"
        data = update.callback_query.data
        if data:
            if data.startswith("price_list"):
                event_type = "price_list"
            elif data.startswith("consultation_request"):
                event_type = "consult"
            elif data.startswith("submit_order"):
                event_type = "order_submit"
            elif data.startswith("order_start"):
                event_type = "start"
    elif getattr(update, "message", None):
        action = "Message"
        data = update.message.text or update.message.caption
        if data:
            if data.startswith("/start"):
                event_type = "start"
            elif "меню" in data.lower() or "цены" in data.lower():
                event_type = "price_list"
    elif getattr(update, "inline_query", None):
        action = "InlineQuery"
        data = update.inline_query.query

    tags = await _behavior_tags(user_id) if user_id else []
    tags_suffix = f" | {' '.join(tags)}" if tags else ""

    entry = f"#USER_{user_id} | {action} | {_compact(data)}{tags_suffix}"
    USER_ACTIONS[user_id].append(entry)

    try:
        if event_type:
            await db.add_action_log(user_id, entry, event_type=event_type, meta=_compact(data))
        else:
            await db.add_action_log(user_id, entry)
        if user_id:
            await db.update_user_field(user_id, "last_seen", datetime.utcnow())
    except Exception:
        logger.debug("DB wiretap logging failed", exc_info=True)

    if LOG_CHANNEL_ID:
        try:
            await context.bot.send_message(LOG_CHANNEL_ID, entry)
        except Exception:
            logger.debug("Wiretap send failed", exc_info=True)

    if user_id in WATCHERS:
        for admin_id in list(WATCHERS[user_id]):
            try:
                await context.bot.send_message(admin_id, entry)
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
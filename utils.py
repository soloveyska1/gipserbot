import logging
import os
import asyncio
import random
from datetime import datetime
from html import escape
from telegram.constants import ChatAction
from config import LOGS_DIR

# Настройка логирования
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Добавляем запись в файл
file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'bot.log'))
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

async def log_action(update, context, action):
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}): {action}")

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
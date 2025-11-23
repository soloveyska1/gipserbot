import os

# === 1. ТВОИ ДАННЫЕ ===
BOT_TOKEN = "7387413773:AAFSXCt7sCd7ODu0Rtwn4_7ogdlt90EvZZ0"
# Канал для отзывов
REVIEW_CHANNEL_ID = -1003241736635

# СПИСОК админов
ADMIN_IDS = [872379852] 
# Одиночный (для совместимости)
ADMIN_ID = 872379852 

# Ссылка на канал
CHANNEL_LINK = "https://t.me/+AbCdEfGhIjKlMnOp" 

# === 2. ТЕХНИЧЕСКИЕ НАСТРОЙКИ ===
LOGS_DIR = "logs"            
DB_PATH = "syndicate_v3.db" 

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# === 3. ЭКОНОМИКА ===
PRICE_SPEECH = 1500
PRICE_PRES = 2000
PRICE_VIP = 2500      
URGENCY_MULTIPLIER = 1.4 

# === 4. ТИПЫ УСЛУГ (LOVE EDITION: CONCRETE) ===
SERVICES = {
    "essay": {
        "name": "💋 Легкий флирт (Эссе)", 
        "base": 1500, 
        "desc": "Быстро, красиво и без лишних обязательств.",
        "emoji": "💋",
        "image": "AgACAgIAAxkBAAIRR2kf7F4dAW3EbtTMxKPTyz28QQ9bAAJeC2sb-nYBSQL-LGGkbqNkAQADAgADeQADNgQ",
        "script": "<b>💋 Цель: Эссе / Статья.</b>\n\nЛегкий флирт должен быть красивым, но кратким. Чтобы искра вспыхнула сразу, мне нужны факты.\n\nНапишите <b>Тему</b> и <b>Требования</b> (Объем, Антиплагиат).\nЕсли есть методичка — <b>прикрепляйте файл</b>.\n\n<i>Жду вводные...</i>"
    },
    "term": {
        "name": "🌹 Бурный роман (Курсач)", 
        "base": 3500, 
        "desc": "Требует внимания, цветов и серьезных намерений.",
        "emoji": "🌹",
        "image": "AgACAgIAAxkBAAIRSWkf7JbkfYiYlly7wueDzWX3rqN2AAJgC2sb-nYBSTMGhRGAXTcDAQADAgADeQADNgQ",
        "script": "<b>🌹 Цель: Курсовая работа.</b>\n\nС этой дамой всё серьезно. Чтобы роман сложился удачно, нужен четкий план действий.\n\nПрикрепите <b>Методичку</b> и утвержденный <b>План</b>.\nЕсли плана нет — так и напишите, составим сами.\n\n<i>Загружайте файлы и пишите тему...</i>"
    },
    "diploma": {
        "name": "💍 Свадьба (Диплом)", 
        "base": 15000, 
        "desc": "Главное событие жизни. Всё должно быть идеально.",
        "emoji": "💍",
        "image": "AgACAgIAAxkBAAIRS2kf7MSTTijXjDAMo5fTJWbr8oWtAAJhC2sb-nYBSTtb2lqL8Yp5AQADAgADeQADNgQ",
        "script": "<b>💍 Цель: Диплом (ВКР).</b>\n\nГлавное событие. Чтобы на защите вам сказали «Да», подготовка должна быть идеальной.\n\n<b>Загружайте всё досье:</b> Тему, План, Методичку, черновики (если есть).\nМы организуем торжество «под ключ».\n\n<i>Жду материалы...</i>"
    },
    "practice": {
        "name": "🎩 Семейный ужин (Отчет)", 
        "base": 2500, 
        "desc": "Нужно произвести впечатление приличного человека.",
        "emoji": "🎩",
        "image": "AgACAgIAAxkBAAIRTWkf7NpdmzffgdSOnfb08j5lH55xAAJiC2sb-nYBSVLuvCHN-GsrAQADAgADeQADNgQ",
        "script": "<b>🎩 Цель: Отчет по практике.</b>\n\nНужно произвести впечатление и сделать вид, что вы работали не покладая рук.\n\nПрикрепите <b>Шаблон дневника</b> и <b>данные о предприятии</b>.\nЕсли базы практики нет — мы придумаем красивую легенду.\n\n<i>Жду документы...</i>"
    },
    "exam": {
        "name": "🎲 Игра с судьбой (Экзамен)", 
        "base": 1000, 
        "desc": "Адреналин, риск и ставки ва-банк.",
        "emoji": "🎲",
        "image": "AgACAgIAAxkBAAIRT2kf7O3Ws4WR0kw-hfuqV8z9TMGwAAJjC2sb-nYBSZcEAV0GfBukAQADAgADeQADNgQ",
        "script": "<b>🎲 Цель: Онлайн-экзамен.</b>\n\nСвидание вслепую — это риск. Чтобы не провалиться, нам нужно знать время и место.\n\nНапишите <b>Дату</b>, <b>Время (МСК)</b> и <b>Предмет</b>.\nЕсли есть примеры билетов — прикрепляйте фото.\n\n<i>Пишите детали...</i>"
    }
}
import sqlite3
from typing import List, Dict, Any

from config import DB_PATH
from database import core


def _get_conn():
    return sqlite3.connect(DB_PATH)


def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _ensure_user_columns():
    """Guarantee the presence of new CRM columns in legacy databases."""
    conn = _get_conn()
    cur = conn.cursor()
    if not _column_exists(cur, "users", "is_banned"):
        cur.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    if not _column_exists(cur, "users", "admin_note"):
        cur.execute("ALTER TABLE users ADD COLUMN admin_note TEXT")
    if not _column_exists(cur, "users", "total_spent"):
        cur.execute("ALTER TABLE users ADD COLUMN total_spent INTEGER DEFAULT 0")
    conn.commit()
    conn.close()


def _ensure_promo_tables():
    _ensure_user_columns()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            discount_amount INTEGER,
            activations_left INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS promo_usages (
            user_id INTEGER,
            code TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, code)
        )
        """
    )
    conn.commit()
    conn.close()


def _ensure_services_table():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            description TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def seed_services():
    """Заполняет/обновляет салунный каталог услуг и чистит тестовые позиции."""
    _ensure_services_table()
    conn = _get_conn()
    cur = conn.cursor()
    # Убираем тестовые позиции
    cur.execute("DELETE FROM services WHERE name = ?", ("Чик-чик и больше не мужик",))

    defaults = [
        (
            "Эссе (Меткий выстрел)",
            4500,
            "⏱ <b>Срок:</b> 1-3 дня (с запасом).\n🎒 <b>Нужно от тебя:</b> Тема, задание и методичка (требования научрука).\n<b>Суть:</b> Бьем точно в цель без лишней воды.",
        ),
        (
            "Курсовая (Партия в покер)",
            15000,
            "⏱ <b>Срок:</b> 5-7 дней.\n🎒 <b>Нужно от тебя:</b> Утвержденная тема, план (если есть) и заметки научрука.\n<b>Суть:</b> Соберем Роял Флеш по всем правилам ВУЗа.",
        ),
        (
            "Диплом (Золотая жила)",
            35000,
            "⏱ <b>Срок:</b> 14-21 день.\n🎒 <b>Нужно от тебя:</b> Тема, план, методичка.\n<b>Суть:</b> Твой главный трофей. Полное сопровождение до защиты.",
        ),
        (
            "Магистерская (Собственное Ранчо)",
            55000,
            "⏱ <b>Срок:</b> 20-30 дней.\n🎒 <b>Нужно от тебя:</b> Тема, данные для анализа, требования к уникальности.\n<b>Суть:</b> Фундаментальный труд для серьезных людей.",
        ),
        (
            "Отчет (Верный мустанг)",
            12000,
            "⏱ <b>Срок:</b> 3-5 дней.\n🎒 <b>Нужно от тебя:</b> Информация о базе практики (где проходил), дневник (если есть).\n<b>Суть:</b> Вывезет тебя из бюрократии к зачету.",
        ),
        (
            "Экзамен (Дикое Родео)",
            20000,
            "⏱ <b>Срок:</b> В реальном времени.\n🎒 <b>Нужно от тебя:</b> Точная дата, время и предмет. Обсуждаем заранее!\n<b>Суть:</b> Мы страхуем, ты сдаешь.",
        ),
        (
            "Презентация (Карта сокровищ)",
            2500,
            "⏱ <b>Срок:</b> 1-2 дня.\n🎒 <b>Нужно от тебя:</b> Текст доклада или сама работа.\n<b>Суть:</b> Яркие слайды, чтобы шериф (препод) все понял.",
        ),
        (
            "Речь (Тост за удачу)",
            2500,
            "⏱ <b>Срок:</b> 1 день.\n🎒 <b>Нужно от тебя:</b> Твоя работа или презентация.\n<b>Суть:</b> Напишем так, что весь Салун будет слушать молча.",
        ),
        (
            "VIP (Ключ от города)",
            5000,
            "Приоритет и открытые двери.",
        ),
    ]

    # Добавляем отсутствующие услуги и обновляем описания существующих, не трогая цены админа
    for name, price, desc in defaults:
        cur.execute(
            "INSERT OR IGNORE INTO services (name, price, description) VALUES (?, ?, ?)",
            (name, price, desc),
        )
        cur.execute("UPDATE services SET description = ? WHERE name = ?", (desc, name))

    conn.commit()
    conn.close()


async def get_services() -> List[Dict[str, Any]]:
    _ensure_services_table()
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, name, price, description FROM services ORDER BY id"
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# Alias to emphasize full fetch for UI flows (e.g., клиентский заказ)
async def get_all_services() -> List[Dict[str, Any]]:
    return await get_services()


async def get_service(service_id: int) -> Dict[str, Any] | None:
    _ensure_services_table()
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT id, name, price, description FROM services WHERE id = ?",
        (service_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


async def add_service(name: str, price: int, description: str) -> int:
    _ensure_services_table()
    conn = _get_conn()
    with conn:
        cur = conn.execute(
            "INSERT INTO services (name, price, description) VALUES (?, ?, ?)",
            (name, price, description),
        )
    conn.close()
    return cur.lastrowid


async def update_service_name(service_id: int, name: str):
    _ensure_services_table()
    conn = _get_conn()
    with conn:
        conn.execute(
            "UPDATE services SET name = ? WHERE id = ?",
            (name, service_id),
        )
    conn.close()


async def update_service_price(service_id: int, price: int):
    _ensure_services_table()
    conn = _get_conn()
    with conn:
        conn.execute(
            "UPDATE services SET price = ? WHERE id = ?",
            (price, service_id),
        )
    conn.close()


async def update_service_description(service_id: int, description: str):
    _ensure_services_table()
    conn = _get_conn()
    with conn:
        conn.execute(
            "UPDATE services SET description = ? WHERE id = ?",
            (description, service_id),
        )
    conn.close()


async def delete_service(service_id: int):
    _ensure_services_table()
    conn = _get_conn()
    with conn:
        conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
    conn.close()


async def get_all_users_paginated(page: int, page_size: int = 10) -> List[Dict[str, Any]]:
    """Return a paginated slice of users with CRM fields for the admin list."""
    _ensure_user_columns()
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    offset = max(page, 0) * page_size
    cur = conn.execute(
        """
        SELECT user_id, username, full_name, balance, is_banned, admin_note, total_spent,
               orders_count, joined_at, referrer_id
        FROM users
        ORDER BY user_id
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def get_user_admin_profile(user_id: int) -> Dict[str, Any] | None:
    """Return a single user with admin-only fields (note, ban, totals)."""
    _ensure_user_columns()
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT user_id, username, full_name, balance, is_banned, admin_note, total_spent,
               orders_count, joined_at, referrer_id
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


async def update_admin_note(user_id: int, text: str) -> None:
    _ensure_user_columns()
    conn = _get_conn()
    with conn:
        conn.execute(
            "UPDATE users SET admin_note = ? WHERE user_id = ?",
            (text, user_id),
        )
    conn.close()


async def set_ban_status(user_id: int, is_banned: bool) -> None:
    _ensure_user_columns()
    conn = _get_conn()
    with conn:
        conn.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (1 if is_banned else 0, user_id),
        )
    conn.close()


async def create_promo_code(code: str, amount: int, activations: int):
    _ensure_promo_tables()
    conn = _get_conn()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO promo_codes (code, discount_amount, activations_left) VALUES (?, ?, ?)",
            (code, amount, activations),
        )
    conn.close()


async def fetch_promo_code(code: str):
    _ensure_promo_tables()
    conn = _get_conn()
    cur = conn.execute(
        "SELECT code, discount_amount, activations_left FROM promo_codes WHERE code = ?",
        (code,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"code": row[0], "discount_amount": row[1], "activations_left": row[2]}


async def decrement_promo(code: str):
    _ensure_promo_tables()
    conn = _get_conn()
    with conn:
        conn.execute(
            "UPDATE promo_codes SET activations_left = activations_left - 1 WHERE code = ? AND activations_left > 0",
            (code,),
        )
    conn.close()


async def has_used_promo(user_id: int, code: str) -> bool:
    _ensure_promo_tables()
    conn = _get_conn()
    cur = conn.execute(
        "SELECT 1 FROM promo_usages WHERE user_id = ? AND code = ?",
        (user_id, code),
    )
    used = cur.fetchone() is not None
    conn.close()
    return used


async def mark_promo_used(user_id: int, code: str):
    _ensure_promo_tables()
    conn = _get_conn()
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO promo_usages (user_id, code) VALUES (?, ?)",
            (user_id, code),
        )
    conn.close()


async def apply_promo_to_user(user_id: int, code: str):
    promo = await fetch_promo_code(code)
    if not promo or promo["activations_left"] <= 0:
        return None
    if await has_used_promo(user_id, code):
        return None
    await core.adjust_balance(user_id, promo["discount_amount"], "Промокод")
    await decrement_promo(code)
    await mark_promo_used(user_id, code)
    return promo

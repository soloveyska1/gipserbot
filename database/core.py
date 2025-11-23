import sqlite3
import logging
from config import DB_PATH

ALLOWED_STATUSES = {
    "checking",
    "pending_pay",
    "work",
    "norm_control",
    "edits",
    "suspended",
    "done",
    "cancel",
}


async def get_connection():
    return sqlite3.connect(DB_PATH)


def _column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _ensure_column(cursor, table, column, definition):
    if not _column_exists(cursor, table, column):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
        logging.info("[DB] Добавлен столбец %s в %s", column, table)


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # 1. Пользователи
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                orders_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT 0,
                is_alive INTEGER DEFAULT 1,
                agreed_to_rules INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 2. Заказы
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_type TEXT,
                topic TEXT,
                deadline TEXT,
                status TEXT DEFAULT 'checking',
                price INTEGER DEFAULT 0,
                files TEXT,
                speech INTEGER DEFAULT 0,
                pres INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0,
                is_visible INTEGER DEFAULT 1,
                is_hidden_for_user INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deadline_type TEXT,
                upsell INTEGER DEFAULT 0,
                referral_bonus_paid INTEGER DEFAULT 0,
                promo_code TEXT,
                last_ping_time TIMESTAMP
            )
            """
        )

        # 3. Сообщения
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                sender_id INTEGER,
                is_admin INTEGER,
                msg_type TEXT,
                content TEXT,
                file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 4. Транзакции
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 5. Отзывы
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 6. Настройки
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )

        # 7. Промокоды
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                discount_amount INTEGER NOT NULL,
                activations_left INTEGER NOT NULL
            )
            """
        )

        # 8. Логи
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        _ensure_column(cursor, "users", "is_alive", "is_alive INTEGER DEFAULT 1")
        _ensure_column(cursor, "users", "agreed_to_rules", "agreed_to_rules INTEGER DEFAULT 0")
        _ensure_column(cursor, "orders", "is_hidden_for_user", "is_hidden_for_user INTEGER DEFAULT 0")
        _ensure_column(cursor, "orders", "referral_bonus_paid", "referral_bonus_paid INTEGER DEFAULT 0")
        _ensure_column(cursor, "orders", "promo_code", "promo_code TEXT")
        _ensure_column(cursor, "orders", "last_ping_time", "last_ping_time TIMESTAMP")

        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance_mode', '0')"
        )

        conn.commit()
    logging.info("База данных успешно инициализирована и обновлена.")


async def get_setting(key):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


async def set_setting(key, value):
    conn = await get_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
    finally:
        conn.close()


async def create_order(data):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO orders (user_id, service_type, topic, deadline_type, price, files, speech, pres, vip, status, deadline, promo_code)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 'checking', ?, ?)
            """,
            (
                data['uid'],
                data['type'],
                data['topic'],
                data['deadline'],
                data['price'],
                "",
                data.get('deadline'),
                data.get('promo_code'),
            ),
        )

        conn.commit()
        oid = cursor.lastrowid
        conn.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?", (data['uid'],))
        conn.commit()
        return oid
    finally:
        conn.close()


async def add_user(user_id, username, full_name, referrer_id=0):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            return False
        conn.execute(
            "INSERT INTO users (user_id, username, full_name, referrer_id) VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, referrer_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


async def get_user(user_id):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "balance": row[3],
                "total_spent": row[4],
                "orders_count": row[5],
                "is_banned": row[6],
                "referrer_id": row[7],
                "is_alive": row[8],
                "agreed_to_rules": row[9],
                "joined_at": row[10],
            }
        return None
    finally:
        conn.close()


async def get_all_users():
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT user_id, full_name, username, balance, is_banned, referrer_id, is_alive FROM users")
        users = []
        for row in cursor.fetchall():
            users.append(
                {
                    "user_id": row[0],
                    "full_name": row[1],
                    "username": row[2],
                    "balance": row[3],
                    "is_banned": row[4],
                    "referrer_id": row[5],
                    "is_alive": row[6],
                }
            )
        return users
    finally:
        conn.close()


async def update_user_field(user_id, field, value):
    conn = await get_connection()
    try:
        conn.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
        conn.commit()
    finally:
        conn.close()


async def adjust_balance(user_id, delta, reason=""):
    conn = await get_connection()
    try:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        conn.execute("INSERT INTO transactions (user_id, amount, reason) VALUES (?, ?, ?)", (user_id, delta, reason))
        conn.commit()
    finally:
        conn.close()


async def get_order(order_id):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "service_type": row[2],
                "topic": row[3],
                "deadline": row[4],
                "status": row[5],
                "price": row[6],
                "files": row[7],
                "speech": row[8],
                "pres": row[9],
                "vip": row[10],
                "is_visible": row[11],
                "is_hidden_for_user": row[12],
                "created_at": row[13],
                "deadline_type": row[14],
                "upsell": row[15],
                "referral_bonus_paid": row[16],
                "promo_code": row[17],
                "last_ping_time": row[18],
            }
        return None
    finally:
        conn.close()


async def get_user_orders(user_id):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? AND is_visible = 1 AND is_hidden_for_user = 0 ORDER BY id DESC",
            (user_id,),
        )
        orders = []
        for row in cursor.fetchall():
            orders.append(
                {
                    "id": row[0],
                    "status": row[5],
                    "price": row[6],
                    "service_type": row[2],
                    "topic": row[3],
                    "deadline": row[4],
                    "promo_code": row[17],
                }
            )
        return orders
    finally:
        conn.close()


async def get_all_orders(limit=100):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT * FROM orders WHERE status != 'done' ORDER BY id DESC LIMIT ?", (limit,))
        orders = []
        for row in cursor.fetchall():
            orders.append(
                {
                    "id": row[0],
                    "user_id": row[1],
                    "status": row[5],
                    "price": row[6],
                    "service_type": row[2],
                    "topic": row[3],
                    "promo_code": row[17],
                }
            )
        return orders
    finally:
        conn.close()


async def update_order_status(order_id, new_status):
    conn = await get_connection()
    try:
        if new_status not in ALLOWED_STATUSES:
            raise ValueError("Недопустимый статус заказа")
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        conn.commit()
    finally:
        conn.close()


async def update_order_visibility(order_id, is_visible):
    conn = await get_connection()
    try:
        conn.execute("UPDATE orders SET is_visible = ? WHERE id = ?", (1 if is_visible else 0, order_id))
        conn.commit()
    finally:
        conn.close()


async def hide_order_for_user(order_id, hide=True):
    conn = await get_connection()
    try:
        conn.execute("UPDATE orders SET is_hidden_for_user = ? WHERE id = ?", (1 if hide else 0, order_id))
        conn.commit()
    finally:
        conn.close()


async def update_order_price(order_id, price):
    conn = await get_connection()
    try:
        conn.execute("UPDATE orders SET price = ? WHERE id = ?", (price, order_id))
        conn.commit()
    finally:
        conn.close()


async def set_order_last_ping(order_id, ts):
    conn = await get_connection()
    try:
        conn.execute("UPDATE orders SET last_ping_time = ? WHERE id = ?", (ts, order_id))
        conn.commit()
    finally:
        conn.close()


# --- CHAT & REVIEWS ---
async def add_chat_message(order_id, sender_id, is_admin, msg_type, content, file_id=None):
    conn = await get_connection()
    try:
        conn.execute(
            "INSERT INTO messages (order_id, sender_id, is_admin, msg_type, content, file_id) VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, sender_id, 1 if is_admin else 0, msg_type, content, file_id),
        )
        conn.commit()
    finally:
        conn.close()


async def get_chat_history(order_id, limit=None):
    conn = await get_connection()
    try:
        query = "SELECT sender_id, is_admin, msg_type, content, file_id, created_at FROM messages WHERE order_id = ? ORDER BY id DESC"
        params = [order_id]
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        cursor = conn.execute(query, params)
        res = []
        rows = cursor.fetchall()
        if limit:
            rows = list(reversed(rows))
        for row in rows:
            res.append(
                {
                    "sender_id": row[0],
                    "is_admin": row[1],
                    "message_type": row[2],
                    "content": row[3],
                    "file_id": row[4],
                    "created_at": row[5],
                }
            )
        return res
    finally:
        conn.close()


async def add_review(user_id, text):
    conn = await get_connection()
    try:
        conn.execute("INSERT INTO reviews (user_id, text) VALUES (?, ?)", (user_id, text))
        conn.commit()
    finally:
        conn.close()


async def get_transactions(user_id):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT amount, reason, created_at FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 10",
            (user_id,),
        )
        res = []
        for row in cursor.fetchall():
            res.append({"amount": row[0], "reason": row[1], "date": row[2]})
        return res
    finally:
        conn.close()


async def add_transaction(user_id, amount, reason):
    conn = await get_connection()
    try:
        conn.execute("INSERT INTO transactions (user_id, amount, reason) VALUES (?, ?, ?)", (user_id, amount, reason))
        conn.commit()
    finally:
        conn.close()


async def add_action_log(user_id, action_text):
    conn = await get_connection()
    try:
        conn.execute("INSERT INTO action_logs (user_id, action_text) VALUES (?, ?)", (user_id, action_text))
        conn.commit()
    finally:
        conn.close()


async def get_action_logs(limit=100):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT user_id, action_text, created_at FROM action_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


async def add_promo_code(code, discount_amount, activations_left):
    conn = await get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO promo_codes (code, discount_amount, activations_left) VALUES (?, ?, ?)",
            (code, discount_amount, activations_left),
        )
        conn.commit()
    finally:
        conn.close()


async def delete_promo_code(code):
    conn = await get_connection()
    try:
        conn.execute("DELETE FROM promo_codes WHERE code = ?", (code,))
        conn.commit()
    finally:
        conn.close()


async def get_promo_code(code):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT code, discount_amount, activations_left FROM promo_codes WHERE code = ?",
            (code,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {"code": row[0], "discount_amount": row[1], "activations_left": row[2]}
    finally:
        conn.close()


async def decrement_promo_activation(code):
    conn = await get_connection()
    try:
        conn.execute(
            "UPDATE promo_codes SET activations_left = activations_left - 1 WHERE code = ? AND activations_left > 0",
            (code,),
        )
        conn.commit()
    finally:
        conn.close()


async def get_stats():
    conn = await get_connection()
    try:
        u_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        o_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        money = conn.execute("SELECT SUM(price) FROM orders WHERE status != 'cancel'").fetchone()[0] or 0
        return u_count, o_count, money
    finally:
        conn.close()

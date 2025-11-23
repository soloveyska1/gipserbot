import sqlite3
import logging
from config import DB_PATH

async def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 1. Пользователи
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                orders_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT 0,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Заказы
        cursor.execute("""
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deadline_type TEXT,
                upsell INTEGER DEFAULT 0
            )
        """)
        
        # 3. Сообщения
        cursor.execute("""
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
        """)

        # 4. Транзакции
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. Отзывы
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. НАСТРОЙКИ
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
    logging.info("База данных успешно инициализирована и обновлена.")

# --- НОВЫЕ ФУНКЦИИ ДЛЯ main.py ---

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

# --- ЗАКАЗЫ (Create Order) ---
async def create_order(data):
    # data = {'uid': ..., 'type': ..., 'topic': ..., 'deadline': ..., 'price': ..., 'urgent': ..., 'upsell': ...}
    conn = await get_connection()
    try:
        cursor = conn.execute("""
            INSERT INTO orders (user_id, service_type, topic, deadline_type, price, files, speech, pres, vip, status, deadline)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 'checking', ?)
        """, (data['uid'], data['type'], data['topic'], data['deadline'], data['price'], "", data['deadline'])) # deadline дублируем временно
        
        conn.commit()
        oid = cursor.lastrowid
        conn.execute("UPDATE users SET orders_count = orders_count + 1 WHERE user_id = ?", (data['uid'],))
        conn.commit()
        return oid
    finally:
        conn.close()

# --- USERS ---
async def add_user(user_id, username, full_name, referrer_id=0):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone(): return False
        conn.execute("INSERT INTO users (user_id, username, full_name, referrer_id) VALUES (?, ?, ?, ?)", 
                     (user_id, username, full_name, referrer_id))
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
                "user_id": row[0], "username": row[1], "full_name": row[2],
                "balance": row[3], "total_spent": row[4], "orders_count": row[5],
                "is_banned": row[6], "referrer_id": row[7], "joined_at": row[8]
            }
        return None
    finally:
        conn.close()
        
async def get_all_users():
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT user_id, full_name, username, balance, is_banned, referrer_id FROM users")
        users = []
        for row in cursor.fetchall():
            users.append({"user_id": row[0], "full_name": row[1], "username": row[2], "balance": row[3], "is_banned": row[4], "referrer_id": row[5]})
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

# --- ORDERS GET ---
async def get_order(order_id):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0], "user_id": row[1], "service_type": row[2],
                "topic": row[3], "deadline": row[4], "status": row[5],
                "price": row[6], "files": row[7], "created_at": row[12], "deadline_type": row[13]
            }
        return None
    finally:
        conn.close()

async def get_user_orders(user_id):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT * FROM orders WHERE user_id = ? AND is_visible = 1 ORDER BY id DESC", (user_id,))
        orders = []
        for row in cursor.fetchall():
            orders.append({"id": row[0], "status": row[5], "price": row[6], "service_type": row[2], "topic": row[3], "deadline": row[4]})
        return orders
    finally:
        conn.close()

async def get_all_orders(limit=100):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT * FROM orders WHERE status != 'done' ORDER BY id DESC LIMIT ?", (limit,))
        orders = []
        for row in cursor.fetchall():
            orders.append({"id": row[0], "user_id": row[1], "status": row[5], "price": row[6], "service_type": row[2], "topic": row[3]})
        return orders
    finally:
        conn.close()

async def update_order_status(order_id, new_status):
    conn = await get_connection()
    try:
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

# --- CHAT & REVIEWS ---
async def add_chat_message(order_id, sender_id, is_admin, msg_type, content, file_id=None):
    conn = await get_connection()
    try:
        conn.execute("INSERT INTO messages (order_id, sender_id, is_admin, msg_type, content, file_id) VALUES (?, ?, ?, ?, ?, ?)", 
                     (order_id, sender_id, 1 if is_admin else 0, msg_type, content, file_id))
        conn.commit()
    finally:
        conn.close()

async def get_chat_history(order_id):
    conn = await get_connection()
    try:
        cursor = conn.execute("SELECT sender_id, is_admin, msg_type, content, file_id, created_at FROM messages WHERE order_id = ? ORDER BY id ASC", (order_id,))
        res = []
        for row in cursor.fetchall():
            res.append({"sender_id": row[0], "is_admin": row[1], "message_type": row[2], "content": row[3], "file_id": row[4], "created_at": row[5]})
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
        cursor = conn.execute("SELECT amount, reason, created_at FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
        res = []
        for row in cursor.fetchall():
            res.append({"amount": row[0], "reason": row[1], "date": row[2]})
        return res
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
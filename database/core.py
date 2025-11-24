import sqlite3
import logging
from datetime import datetime, timedelta
from config import DB_PATH

ALLOWED_STATUSES = {
    "checking",
    "pending_pay",
    "paid",
    "work",
    "norm_control",
    "edits",
    "suspended",
    "done",
    "cancel",
}


async def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn


def _column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _ensure_column(cursor, table, column, definition):
    if not _column_exists(cursor, table, column):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
            logging.info("[DB] Добавлен столбец %s в %s", column, table)
            return
        except sqlite3.OperationalError as exc:
            if "non-constant default" not in str(exc).lower() or "default" not in definition.lower():
                raise

            base_def = definition.split(" DEFAULT ", 1)[0]
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {base_def}")
            default_part = definition.split(" DEFAULT ", 1)[1]
            cursor.execute(
                f"UPDATE {table} SET {column} = {default_part} WHERE {column} IS NULL"
            )
            logging.info(
                "[DB] Добавлен столбец %s в %s без DEFAULT из-за ограничения SQLite; значения заполнены",
                column,
                table,
            )


def _ensure_user_columns(cursor):
    _ensure_column(cursor, "users", "balance", "balance INTEGER DEFAULT 0")
    _ensure_column(cursor, "users", "total_spent", "total_spent INTEGER DEFAULT 0")
    _ensure_column(cursor, "users", "orders_count", "orders_count INTEGER DEFAULT 0")
    _ensure_column(cursor, "users", "is_banned", "is_banned INTEGER DEFAULT 0")
    _ensure_column(cursor, "users", "referrer_id", "referrer_id INTEGER DEFAULT 0")
    _ensure_column(cursor, "users", "is_alive", "is_alive INTEGER DEFAULT 1")
    _ensure_column(cursor, "users", "agreed_to_rules", "agreed_to_rules INTEGER DEFAULT 0")
    _ensure_column(cursor, "users", "last_bonus_time", "last_bonus_time TIMESTAMP")
    _ensure_column(cursor, "users", "bonus_streak", "bonus_streak INTEGER DEFAULT 0")
    if not _column_exists(cursor, "users", "joined_at"):
        # SQLite не позволяет добавлять колонку с выражением по умолчанию через ALTER,
        # поэтому добавляем без дефолта и заполняем существующие записи вручную.
        cursor.execute("ALTER TABLE users ADD COLUMN joined_at TIMESTAMP")
        cursor.execute("UPDATE users SET joined_at = CURRENT_TIMESTAMP WHERE joined_at IS NULL")
        logging.info("[DB] Добавлен столбец joined_at в users и заполнен текущей датой")


def _ensure_order_columns(cursor):
    cursor.execute("PRAGMA table_info(orders)")
    columns = {row[1] for row in cursor.fetchall()}

    required_base = {
        "id",
        "user_id",
        "service_type",
        "topic",
        "deadline",
        "status",
        "price",
        "original_price",
        "points_used",
        "final_price",
        "files",
        "speech",
        "pres",
        "vip",
        "is_visible",
        "created_at",
    }

    def rebuild_orders_table():
        logging.info("[DB] Перестраиваем таблицу orders до актуальной схемы")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS orders_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_type TEXT,
                topic TEXT,
                deadline TEXT,
                status TEXT DEFAULT 'checking',
                price INTEGER DEFAULT 0,
                original_price INTEGER DEFAULT 0,
                points_used INTEGER DEFAULT 0,
                final_price INTEGER DEFAULT 0,
                files TEXT,
                speech INTEGER DEFAULT 0,
                pres INTEGER DEFAULT 0,
                vip INTEGER DEFAULT 0,
                is_visible INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_hidden_for_user INTEGER DEFAULT 0,
                referral_bonus_paid INTEGER DEFAULT 0,
                promo_code TEXT,
                last_ping_time TIMESTAMP,
                deadline_type TEXT,
                upsell INTEGER DEFAULT 0
            )
            """
        )

        cursor.execute("PRAGMA table_info(orders)")
        current = {row[1] for row in cursor.fetchall()}

        def col_or_default(col, default_expr, fallback=None):
            if col in current:
                return col
            if fallback and fallback in current:
                return fallback
            return default_expr

        select_exprs = [
            col_or_default("id", "NULL"),
                col_or_default("user_id", "0"),
                col_or_default("service_type", "''", fallback="order_type"),
                col_or_default("topic", "''"),
                col_or_default("deadline", "''"),
                col_or_default("status", "'checking'"),
                col_or_default("price", "0"),
                col_or_default("original_price", "price"),
                col_or_default("points_used", "0"),
                col_or_default("final_price", "price"),
                col_or_default("files", "''"),
                col_or_default("speech", "0"),
                col_or_default("pres", "0"),
                col_or_default("vip", "0"),
            col_or_default("is_visible", "1"),
            col_or_default("created_at", "CURRENT_TIMESTAMP"),
            col_or_default("is_hidden_for_user", "0"),
            col_or_default("referral_bonus_paid", "0"),
            col_or_default("promo_code", "NULL"),
            col_or_default("last_ping_time", "NULL"),
            col_or_default("deadline_type", "NULL"),
            col_or_default("upsell", "0"),
        ]

        cursor.execute(
            f"INSERT INTO orders_new SELECT {', '.join(select_exprs)} FROM orders"
        )
        cursor.execute("DROP TABLE orders")
        cursor.execute("ALTER TABLE orders_new RENAME TO orders")
        logging.info("[DB] Таблица orders перестроена")

    if not required_base.issubset(columns):
        rebuild_orders_table()
        cursor.execute("PRAGMA table_info(orders)")
        columns = {row[1] for row in cursor.fetchall()}

    # Переименование старого order_type в service_type (или добавление зеркальной колонки)
    has_order_type = _column_exists(cursor, "orders", "order_type")
    has_service_type = _column_exists(cursor, "orders", "service_type")
    if has_order_type and not has_service_type:
        try:
            cursor.execute("ALTER TABLE orders RENAME COLUMN order_type TO service_type")
            logging.info("[DB] Переименован order_type в service_type")
        except sqlite3.OperationalError:
            # Если RENAME COLUMN недоступен (старая версия SQLite), добавляем колонку и копируем данные
            _ensure_column(cursor, "orders", "service_type", "service_type TEXT")
            cursor.execute(
                "UPDATE orders SET service_type = order_type WHERE service_type IS NULL OR service_type = ''"
            )
            logging.info("[DB] Добавлена service_type и скопированы данные из order_type")
    elif not has_service_type:
        _ensure_column(cursor, "orders", "service_type", "service_type TEXT")

    _ensure_column(cursor, "orders", "is_hidden_for_user", "is_hidden_for_user INTEGER DEFAULT 0")
    _ensure_column(cursor, "orders", "referral_bonus_paid", "referral_bonus_paid INTEGER DEFAULT 0")
    _ensure_column(cursor, "orders", "promo_code", "promo_code TEXT")
    _ensure_column(cursor, "orders", "last_ping_time", "last_ping_time TIMESTAMP")
    _ensure_column(cursor, "orders", "deadline_type", "deadline_type TEXT")
    _ensure_column(cursor, "orders", "upsell", "upsell INTEGER DEFAULT 0")
    _ensure_column(cursor, "orders", "original_price", "original_price INTEGER DEFAULT 0")
    _ensure_column(cursor, "orders", "points_used", "points_used INTEGER DEFAULT 0")
    _ensure_column(cursor, "orders", "final_price", "final_price INTEGER DEFAULT 0")
    _ensure_column(cursor, "users", "achievements", "achievements TEXT DEFAULT ''")
    _ensure_column(cursor, "users", "last_seen", "last_seen TIMESTAMP")


def _ensure_action_log_columns(cursor):
    _ensure_column(cursor, "action_logs", "event_type", "event_type TEXT")
    _ensure_column(cursor, "action_logs", "meta", "meta TEXT")


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
                last_bonus_time TIMESTAMP,
                bonus_streak INTEGER DEFAULT 0,
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
                original_price INTEGER DEFAULT 0,
                points_used INTEGER DEFAULT 0,
                final_price INTEGER DEFAULT 0,
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
                event_type TEXT,
                meta TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        _ensure_user_columns(cursor)
        _ensure_order_columns(cursor)
        _ensure_action_log_columns(cursor)

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
            INSERT INTO orders (user_id, service_type, topic, deadline_type, price, original_price, points_used, final_price, files, speech, pres, vip, status, deadline, promo_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 'checking', ?, ?)
            """,
            (
                data['uid'],
                data['type'],
                data['topic'],
                data['deadline'],
                data['final_price'],
                data.get('original_price', data['final_price']),
                data.get('points_used', 0),
                data.get('final_price', data['final_price']),
                "",
                data.get('deadline'),
                data.get('promo_code'),
            ),
        )

        conn.commit()
        oid = cursor.lastrowid
        conn.execute(
            "UPDATE users SET orders_count = orders_count + 1, total_spent = total_spent + ? WHERE user_id = ?",
            (data.get('final_price', 0), data['uid']),
        )
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
            "INSERT INTO users (user_id, username, full_name, referrer_id, joined_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (user_id, username, full_name, referrer_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


async def get_user(user_id):
    conn = await get_connection()
    try:
        cursor = conn.cursor()
        _ensure_user_columns(cursor)
        conn.commit()

        cursor = conn.execute(
            """
            SELECT user_id, username, full_name, balance, total_spent, orders_count, is_banned,
                   COALESCE(referrer_id, 0) as referrer_id,
                   COALESCE(is_alive, 1) as is_alive,
                   COALESCE(agreed_to_rules, 0) as agreed_to_rules,
                   joined_at,
                   last_bonus_time,
                   COALESCE(bonus_streak, 0) as bonus_streak
            FROM users WHERE user_id = ?
            """,
            (user_id,),
        )
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
                "last_bonus_time": row[11],
                "bonus_streak": row[12],
            }
        return None
    finally:
        conn.close()


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


async def check_bonus_status(user_id):
    conn = await get_connection()
    try:
        cursor = conn.cursor()
        _ensure_user_columns(cursor)
        conn.commit()

        cursor = conn.execute(
            "SELECT last_bonus_time, COALESCE(bonus_streak, 0) FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        last_bonus_raw = row[0] if row else None
        streak = row[1] if row else 0

        last_bonus = _parse_ts(last_bonus_raw)
        now = datetime.utcnow()

        if not last_bonus:
            return {"available": True, "next_streak": max(1, streak or 1), "cooldown_seconds": 0}

        elapsed = now - last_bonus

        if elapsed < timedelta(hours=24):
            remaining = timedelta(hours=24) - elapsed
            return {
                "available": False,
                "next_streak": streak,
                "cooldown_seconds": int(remaining.total_seconds()),
            }

        if elapsed <= timedelta(hours=48):
            return {"available": True, "next_streak": streak + 1, "cooldown_seconds": 0}

        # Больше 48 часов — сброс серии
        conn.execute("UPDATE users SET bonus_streak = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return {"available": True, "next_streak": 0, "cooldown_seconds": 0}
    finally:
        conn.close()


async def record_bonus_claim(user_id, streak):
    conn = await get_connection()
    try:
        conn.execute(
            "UPDATE users SET last_bonus_time = CURRENT_TIMESTAMP, bonus_streak = ? WHERE user_id = ?",
            (streak, user_id),
        )
        conn.commit()
    finally:
        conn.close()


async def get_all_users():
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT user_id, full_name, username, balance, is_banned, COALESCE(referrer_id, 0), COALESCE(is_alive, 1) FROM users"
        )
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
        cursor = conn.execute(
            """
            SELECT id, user_id, service_type, topic, deadline, status, price, files, speech, pres, vip, is_visible,
                   COALESCE(is_hidden_for_user, 0), created_at, deadline_type, COALESCE(upsell, 0),
                   COALESCE(referral_bonus_paid, 0), promo_code, last_ping_time,
                   COALESCE(original_price, price), COALESCE(points_used, 0), COALESCE(final_price, price)
            FROM orders WHERE id = ?
            """,
            (order_id,),
        )
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
                "original_price": row[19],
                "points_used": row[20],
                "final_price": row[21],
            }
        return None
    finally:
        conn.close()


async def get_user_orders(user_id):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT id, user_id, service_type, topic, deadline, status, price, files, speech, pres, vip, is_visible,
                   COALESCE(is_hidden_for_user, 0), created_at, deadline_type, COALESCE(upsell, 0),
                   COALESCE(referral_bonus_paid, 0), promo_code, last_ping_time,
                   COALESCE(original_price, price), COALESCE(points_used, 0), COALESCE(final_price, price)
            FROM orders
            WHERE user_id = ? AND is_visible = 1 AND COALESCE(is_hidden_for_user, 0) = 0
            ORDER BY id DESC
            """,
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
                    "original_price": row[19],
                    "points_used": row[20],
                    "final_price": row[21],
                }
            )
        return orders
    finally:
        conn.close()


async def get_all_orders(limit=100, status_filter=None, search_query=None):
    conn = await get_connection()
    try:
        base_query = [
            """
            SELECT o.id, o.user_id, o.service_type, o.topic, o.deadline, o.status, o.price, o.promo_code,
                   COALESCE(o.original_price, o.price), COALESCE(o.points_used, 0), COALESCE(o.final_price, o.price),
                   u.username, u.full_name
            FROM orders o
            LEFT JOIN users u ON u.user_id = o.user_id
            """
        ]

        conditions = []
        params = []

        if status_filter == "active":
            conditions.append("o.status IN ('work', 'checking', 'norm_control', 'edits')")
        elif status_filter == "payment":
            conditions.append("o.status IN ('pending_pay')")
        elif status_filter == "new":
            conditions.append("o.status IN ('new', 'checking')")

        if search_query is not None:
            search_query = search_query.strip()
            if search_query.isdigit():
                conditions.append("o.id = ?")
                params.append(int(search_query))
            elif search_query:
                like_pattern = f"%{search_query}%"
                conditions.append("(u.username LIKE ? OR u.full_name LIKE ?)")
                params.extend([like_pattern, like_pattern])

        if conditions:
            base_query.append("WHERE " + " AND ".join(conditions))

        base_query.append("ORDER BY o.id DESC LIMIT ?")
        params.append(limit)

        cursor = conn.execute(" ".join(base_query), tuple(params))
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
                    "deadline": row[4],
                    "promo_code": row[7],
                    "original_price": row[8],
                    "points_used": row[9],
                    "final_price": row[10],
                    "username": row[11],
                    "full_name": row[12],
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


async def delete_order_permanently(order_id: int):
    conn = await get_connection()
    try:
        conn.execute("DELETE FROM messages WHERE order_id = ?", (order_id,))
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
    finally:
        conn.close()


async def update_order_price(order_id, price):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT COALESCE(points_used, 0) FROM orders WHERE id = ?",
            (order_id,),
        )
        row = cursor.fetchone()
        points_used = row[0] if row else 0
        final_price = max(price - points_used, 0)
        conn.execute(
            "UPDATE orders SET price = ?, original_price = ?, final_price = ?, points_used = ? WHERE id = ?",
            (final_price, price, final_price, points_used, order_id),
        )
        conn.commit()
    finally:
        conn.close()


async def refund_points_to_user(order_id):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT user_id, COALESCE(points_used, 0), COALESCE(original_price, price) FROM orders WHERE id = ?",
            (order_id,),
        )
        row = cursor.fetchone()
        if not row:
            return 0
        user_id, points_used, original_price = row
        if points_used > 0:
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (points_used, user_id))
            conn.execute(
                "UPDATE orders SET points_used = 0, final_price = ?, price = ? WHERE id = ?",
                (original_price, original_price, order_id),
            )
            conn.commit()
            return points_used
        return 0
    finally:
        conn.close()


async def mark_referral_paid(order_id):
    conn = await get_connection()
    try:
        conn.execute(
            "UPDATE orders SET referral_bonus_paid = 1 WHERE id = ?",
            (order_id,),
        )
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


async def get_user_files(user_id):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT m.id, m.file_id, m.msg_type, m.created_at, o.topic, o.service_type
            FROM messages m
            JOIN orders o ON m.order_id = o.id
            WHERE o.user_id = ?
              AND m.is_admin = 1
              AND m.file_id IS NOT NULL
              AND m.msg_type IN ('document', 'photo')
            ORDER BY m.created_at DESC
            """,
            (user_id,),
        )
        files = []
        for row in cursor.fetchall():
            files.append(
                {
                    "id": row[0],
                    "file_id": row[1],
                    "msg_type": row[2],
                    "created_at": row[3],
                    "topic": row[4],
                    "service_type": row[5],
                }
            )
        return files
    finally:
        conn.close()


async def get_file_message(message_id, user_id):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT m.file_id, m.msg_type
            FROM messages m
            JOIN orders o ON m.order_id = o.id
            WHERE m.id = ?
              AND o.user_id = ?
              AND m.is_admin = 1
              AND m.file_id IS NOT NULL
              AND m.msg_type IN ('document', 'photo')
            """,
            (message_id, user_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {"file_id": row[0], "msg_type": row[1]}
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


async def add_action_log(user_id, action_text, event_type: str | None = None, meta: str | None = None):
    conn = await get_connection()
    try:
        conn.execute(
            "INSERT INTO action_logs (user_id, action_text, event_type, meta) VALUES (?, ?, ?, ?)",
            (user_id, action_text, event_type, meta),
        )
        conn.commit()
    finally:
        conn.close()


async def get_action_logs(limit=100):
    conn = await get_connection()
    try:
        cursor = conn.execute(
            "SELECT user_id, action_text, event_type, meta, created_at FROM action_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


async def get_user_behavior_snapshot(user_id: int) -> dict:
    conn = await get_connection()
    try:
        user_row = conn.execute(
            "SELECT total_spent, orders_count, bonus_streak FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone() or (0, 0, 0)

        total_spent, orders_count, bonus_streak = user_row

        total_actions = conn.execute(
            "SELECT COUNT(*) FROM action_logs WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]

        price_clicks = conn.execute(
            "SELECT COUNT(*) FROM action_logs WHERE user_id = ? AND (event_type = 'price_list' OR action_text LIKE 'event:price_list%')",
            (user_id,),
        ).fetchone()[0]

        night_actions = conn.execute(
            """
            SELECT COUNT(*) FROM action_logs
            WHERE user_id = ? AND CAST(STRFTIME('%H', created_at) AS INTEGER) BETWEEN 0 AND 5
            """,
            (user_id,),
        ).fetchone()[0]

        return {
            "total_spent": total_spent or 0,
            "orders_count": orders_count or 0,
            "bonus_streak": bonus_streak or 0,
            "total_actions": total_actions or 0,
            "price_clicks": price_clicks or 0,
            "night_actions": night_actions or 0,
        }
    finally:
        conn.close()


async def get_revenue_timeseries(days: int = 30) -> dict:
    conn = await get_connection()
    try:
        since_date = (datetime.utcnow() - timedelta(days=days - 1)).date()
        rows = conn.execute(
            """
            SELECT DATE(created_at) as d, SUM(COALESCE(final_price, price))
            FROM orders
            WHERE status != 'cancel' AND created_at IS NOT NULL AND DATE(created_at) >= DATE(?)
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
            """,
            (since_date,),
        ).fetchall()
        return {row[0]: row[1] or 0 for row in rows}
    finally:
        conn.close()


async def get_service_distribution() -> dict:
    conn = await get_connection()
    try:
        rows = conn.execute(
            """
            SELECT COALESCE(service_type, 'Не указано'), COUNT(*)
            FROM orders
            WHERE status != 'cancel'
            GROUP BY COALESCE(service_type, 'Не указано')
            ORDER BY COUNT(*) DESC
            """,
        ).fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        conn.close()


async def get_funnel_counts(days: int = 30) -> dict:
    conn = await get_connection()
    try:
        rows = conn.execute(
            """
            SELECT event_type, COUNT(*)
            FROM action_logs
            WHERE created_at >= datetime('now', ?)
              AND event_type IN ('start','price_list','consult','order_submit')
            GROUP BY event_type
            """,
            (f"-{days} day",),
        ).fetchall()
        counts = {"start": 0, "price_list": 0, "consult": 0, "order_submit": 0}
        for row in rows:
            counts[row[0]] = row[1]
        return counts
    finally:
        conn.close()


async def get_live_pulse_metrics() -> dict:
    conn = await get_connection()
    try:
        revenue_today = (
            conn.execute(
                "SELECT SUM(COALESCE(final_price, price)) FROM orders WHERE status != 'cancel' AND DATE(created_at) = DATE('now')"
            ).fetchone()[0]
            or 0
        )

        avg_revenue_rows = conn.execute(
            """
            SELECT DATE(created_at) d, SUM(COALESCE(final_price, price))
            FROM orders WHERE status != 'cancel' AND created_at IS NOT NULL
            GROUP BY DATE(created_at) ORDER BY DATE(created_at) DESC LIMIT 7
            """
        ).fetchall()
        avg_revenue = 0
        if avg_revenue_rows:
            totals = [r[1] or 0 for r in avg_revenue_rows if r[1] is not None]
            avg_revenue = sum(totals) / max(1, len(totals))

        active_users_1h = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM action_logs WHERE created_at >= datetime('now','-1 hour')",
        ).fetchone()[0]

        pending_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status NOT IN ('done','cancel')",
        ).fetchone()[0]

        urgent_rows = conn.execute(
            "SELECT deadline, status FROM orders WHERE status NOT IN ('done','cancel') AND deadline IS NOT NULL",
        ).fetchall()
        urgent_count = 0
        now_date = datetime.utcnow().date()
        for deadline, status in urgent_rows:
            if not deadline:
                continue
            if isinstance(deadline, str) and ("urgent" in deadline.lower() or "сроч" in deadline.lower()):
                urgent_count += 1
                continue
            try:
                parsed = datetime.strptime(deadline, "%d.%m.%Y").date()
                if (parsed - now_date).days <= 3:
                    urgent_count += 1
            except Exception:
                continue

        orders_today = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')",
        ).fetchone()[0]
        leads_today = conn.execute(
            "SELECT COUNT(*) FROM action_logs WHERE event_type = 'start' AND DATE(created_at) = DATE('now')",
        ).fetchone()[0]
        conversion = 0
        if leads_today:
            conversion = round((orders_today / leads_today) * 100, 2)

        error_count = conn.execute(
            "SELECT COUNT(*) FROM action_logs WHERE event_type = 'error' AND DATE(created_at) = DATE('now')",
        ).fetchone()[0]

        return {
            "revenue_today": revenue_today,
            "avg_revenue": avg_revenue,
            "active_users_1h": active_users_1h or 0,
            "pending_orders": pending_orders or 0,
            "urgent_count": urgent_count,
            "conversion": conversion,
            "errors": error_count or 0,
        }
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


async def get_daily_analytics(days: int = 30):
    conn = await get_connection()
    try:
        since_date = (datetime.utcnow() - timedelta(days=days - 1)).date()

        users_rows = conn.execute(
            """
            SELECT DATE(joined_at) as d, COUNT(*)
            FROM users
            WHERE joined_at IS NOT NULL AND DATE(joined_at) >= DATE(?)
            GROUP BY DATE(joined_at)
            ORDER BY DATE(joined_at)
            """,
            (since_date,),
        ).fetchall()

        revenue_rows = conn.execute(
            """
            SELECT DATE(created_at) as d, SUM(COALESCE(final_price, price))
            FROM orders
            WHERE status != 'cancel' AND created_at IS NOT NULL AND DATE(created_at) >= DATE(?)
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at)
            """,
            (since_date,),
        ).fetchall()

        return {
            "users": {row[0]: row[1] for row in users_rows},
            "revenue": {row[0]: row[1] or 0 for row in revenue_rows},
        }
    finally:
        conn.close()

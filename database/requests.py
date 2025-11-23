import aiosqlite
from config import DB_NAME

# --- USERS ---
async def register_user(user_id, username, full_name, referrer_id=None):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            if await cursor.fetchone(): return False
        await db.execute("INSERT INTO users (user_id, username, full_name, referrer_id) VALUES (?, ?, ?, ?)",
                         (user_id, username, full_name, referrer_id))
        await db.commit()
        return True

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_balance(user_id, amount, method="add"):
    async with aiosqlite.connect(DB_NAME) as db:
        if method == "add": sql = "UPDATE users SET balance = balance + ? WHERE user_id = ?"
        else: sql = "UPDATE users SET balance = balance - ? WHERE user_id = ?"
        await db.execute(sql, (amount, user_id))
        await db.commit()

# --- ORDERS ---
async def add_order(user_id, data):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            INSERT INTO orders (user_id, type, topic, deadline_days, price, status)
            VALUES (?, ?, ?, ?, ?, 'new')
        """, (user_id, data['type'], data['topic'], data['days'], data['price']))
        await db.commit()
        # Обновляем стату юзера
        await db.execute("UPDATE users SET orders_count = orders_count + 1, total_spent = total_spent + ? WHERE user_id = ?", 
                         (data['price'], user_id))
        await db.commit()
        return cursor.lastrowid

async def get_order(order_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
            return await cursor.fetchone()

async def set_order_status(order_id, status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()

# --- ADMIN ANALYTICS ---
async def get_global_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c: users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM orders") as c: orders = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(total_spent) FROM users") as c: revenue = (await c.fetchone())[0] or 0
        return users, orders, int(revenue)

async def get_all_users_ids():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            return [row[0] for row in await cursor.fetchall()]
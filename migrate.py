import asyncio
import json
import os
from database.core import init_db, DB_PATH
import aiosqlite

DATA_DIR = 'data'

async def migrate():
    print("Начинаем миграцию...")
    await init_db()

    # 1. Загрузка пользователей и рефералов
    referrals = {}
    if os.path.exists(os.path.join(DATA_DIR, 'referrals.json')):
        with open(os.path.join(DATA_DIR, 'referrals.json'), 'r', encoding='utf-8') as f:
            referrals = json.load(f)

    # 2. Загрузка бонусов
    bonuses = {}
    if os.path.exists(os.path.join(DATA_DIR, 'bonuses.json')):
        with open(os.path.join(DATA_DIR, 'bonuses.json'), 'r', encoding='utf-8') as f:
            bonuses = json.load(f)

    # 3. Загрузка заказов
    orders_data = {}
    if os.path.exists(os.path.join(DATA_DIR, 'orders.json')):
        with open(os.path.join(DATA_DIR, 'orders.json'), 'r', encoding='utf-8') as f:
            orders_data = json.load(f)
    
    # 4. Загрузка настроек
    if os.path.exists(os.path.join(DATA_DIR, 'settings.json')):
        with open(os.path.join(DATA_DIR, 'settings.json'), 'r', encoding='utf-8') as f:
            settings = json.load(f)
            async with aiosqlite.connect(DB_PATH) as db:
                for k, v in settings.items():
                    await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                                     (k, json.dumps(v, ensure_ascii=False)))
                await db.commit()
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Миграция пользователей (из ключей orders и referrals)
        all_user_ids = set(orders_data.keys()) | set(referrals.keys()) | set(bonuses.keys())
        
        count_users = 0
        for uid in all_user_ids:
            if not uid.isdigit(): continue
            
            # Пытаемся найти баланс
            balance = bonuses.get(uid, {}).get('balance', 0)
            
            # Ищем реферера (кто пригласил этого uid)
            referrer = None
            for ref_id, refs_list in referrals.items():
                if int(uid) in refs_list:
                    referrer = int(ref_id)
                    break
            
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, balance, referrer_id)
                VALUES (?, ?, ?)
            """, (int(uid), balance, referrer))
            
            # Обновляем баланс, если он был
            if balance > 0:
                await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, int(uid)))
            
            count_users += 1

        # Миграция заказов
        count_orders = 0
        for uid, user_orders in orders_data.items():
            for order in user_orders:
                # Упаковываем лишние данные в JSON
                extra = {
                    'upsells': order.get('upsells', []),
                    'attachments': order.get('attachments', []),
                    'invoice_links': order.get('invoice_links', []),
                    'status_history': order.get('status_history', []),
                    'manager_notes': order.get('manager_notes', [])
                }
                
                await db.execute("""
                    INSERT INTO orders (
                        user_id, type, topic, deadline_days, price, status, 
                        payment_state, created_at, requirements, contact, manager, extra_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    int(uid),
                    order.get('type'),
                    order.get('topic'),
                    order.get('deadline_days'),
                    order.get('price'),
                    order.get('status'),
                    order.get('payment_state'),
                    order.get('created_at'),
                    order.get('requirements'),
                    order.get('contact'),
                    order.get('assigned_manager'),
                    json.dumps(extra, ensure_ascii=False)
                ))
                count_orders += 1
        
        await db.commit()

    print(f"Готово! Перенесено пользователей: {count_users}, заказов: {count_orders}.")

if __name__ == "__main__":
    asyncio.run(migrate())
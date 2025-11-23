from datetime import datetime
from config import PRICES, UPSELL_PRICES
from database import db
import logging

logger = logging.getLogger(__name__)

def calculate_price(order_type_key, days_left, complexity_factor=1.0):
    """Расчет стоимости заказа"""
    if order_type_key not in PRICES:
        return 0
    
    base = PRICES[order_type_key]['base']
    price = int(base * complexity_factor)
    
    mode = db.settings.get('pricing_mode', 'light')
    
    if mode == 'hard':
        if days_left < 7: price *= 1.3
        elif days_left < 15: price *= 1.15
    else:
        if days_left < 3: price *= 1.3
        elif days_left < 7: price *= 1.15
        
    return int(price)

def ensure_order_fields(order: dict) -> bool:
    """Проверяет и дописывает недостающие поля в заказе (миграция данных)"""
    changed = False
    defaults = {
        'payment_state': 'не оплачен',
        'prepayment_confirmed': False,
        'full_payment_confirmed': False,
        'bonus_total': 0,
        'bonus_released_prepaid': 0,
        'bonus_released_full': 0,
        'status_history': [],
        'manager_notes': [],
        'assigned_manager': None,
        'payment_channel': db.settings.get('payment_channels', ['Перевод'])[0],
        'invoice_links': []
    }
    
    for key, val in defaults.items():
        if key not in order:
            order[key] = val
            changed = True
            
    # Расчет бонусов, если их нет
    if order['bonus_total'] == 0 and order.get('price', 0) > 0:
        bonus_percent = db.settings.get('bonus_percent', 0.05)
        order['bonus_total'] = int(order['price'] * bonus_percent)
        changed = True

    return changed

def release_bonus(user_id: str, order: dict, stage: str) -> int:
    """Начисление бонусов пользователю"""
    ensure_order_fields(order)
    user_key = str(user_id)
    bonus_entry = db.bonuses.setdefault(user_key, {'balance': 0, 'history': []})
    
    amount = 0
    if stage == 'prepayment':
        if order.get('bonus_released_prepaid'): return 0
        amount = order.get('bonus_total', 0) // 2
        order['bonus_released_prepaid'] = amount
    elif stage == 'full':
        if order.get('bonus_released_full'): return 0
        already = order.get('bonus_released_prepaid', 0)
        amount = max(order.get('bonus_total', 0) - already, 0)
        order['bonus_released_full'] = amount
        
    if amount > 0:
        bonus_entry['balance'] = bonus_entry.get('balance', 0) + amount
        bonus_entry['history'].append({
            'order_id': order.get('order_id'),
            'amount': amount,
            'stage': stage,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        # Сохраняем изменения сразу
        db.save_bonuses()
        db.save_orders()
        
    return amount

def get_user_bonus_balance(user_id: str) -> int:
    return int(db.bonuses.get(str(user_id), {}).get('balance', 0))
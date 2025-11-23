from database import core as db
from config import SERVICES, PRICE_SPEECH, PRICE_PRES, PRICE_VIP

async def get_price(key):
    """
    Получает цену. Сначала ищет в базе (если админ менял).
    Если в базе нет — берет из config.py.
    """
    # Пробуем найти персональную настройку в базе
    val = await db.get_setting(f"price_{key}")
    
    if val is not None:
        return int(val)
    
    # Если в базе пусто, берем дефолт из конфига
    if key == "speech": return PRICE_SPEECH
    if key == "pres": return PRICE_PRES
    if key == "vip": return PRICE_VIP
    
    # Если это услуга (srv_essay, srv_diploma...)
    if key.startswith("srv_"):
        srv_key = key.replace("srv_", "")
        if srv_key in SERVICES:
            return SERVICES[srv_key]['base']
            
    return 0

async def set_price(key, value):
    """Сохраняет новую цену в базу"""
    await db.set_setting(f"price_{key}", value)
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler
from database import core as db
from keyboards import menu as kb
from keyboards import admin_kb
from config import ADMIN_ID

CHAT_STEP = 1

async def _safe_edit(query, text, **kwargs):
    msg = query.message
    try:
        if msg and msg.text:
            return await query.edit_message_text(text, **kwargs)
        if msg and msg.caption:
            return await query.edit_message_caption(caption=text, **kwargs)
    except BadRequest as exc:
        if "not modified" in str(exc).lower():
            return msg
    return await query.message.reply_text(text, **kwargs)


async def chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
        print(f"DEBUG: chat_start triggered with data: {query.data}") # LOGGING

        user = await db.get_user(query.from_user.id)
        if not user or not user.get("agreed_to_rules"):
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text="📜 Прими Кодекс Чести, чтобы открыть двери чата.",
                reply_markup=kb.rules_accept_kb(),
                parse_mode="HTML",
            )
            return ConversationHandler.END
        
        data = query.data
        # adm_chat_OID or chat_order_OID
        if "adm_chat_" in data:
            oid = int(data.split("_")[-1])
            is_admin = True
        else:
            oid = int(data.split("_")[-1])
            is_admin = False
            
        context.user_data['chat_oid'] = oid
        
        # Show history
        hist = await db.get_chat_history(oid)
        txt = f"💬 <b>ЧАТ ПО ЗАКАЗУ #{oid}</b>\n\n"
        
        if not hist:
            txt += "<i>Сообщений пока нет. Напишите первое!</i>\n"
        
        for msg in hist:
            role = "👮‍♂️ Менеджер" if msg['is_admin'] else "👤 Клиент"
            content = "[Файл]" if msg['message_type'] != 'text' else msg['content']
            txt += f"<b>{role}:</b> {content}\n"
            
        txt += "\n✍️ <i>Напишите сообщение или отправьте файл...</i>"
        
        await _safe_edit(query, txt, reply_markup=kb.chat_kb(oid, is_admin), parse_mode="HTML")
        return CHAT_STEP
    except Exception as e:
        print(f"ERROR in chat_start: {e}")
        try:
            await _safe_edit(
                query,
                f"❌ Ошибка чата: {e}",
                reply_markup=kb.main_kb(update.effective_user.id),
            )
        except: pass
        return ConversationHandler.END

async def chat_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    oid = context.user_data.get('chat_oid')
    if not oid: return ConversationHandler.END
    
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)
    
    # Save msg
    msg_type = 'text'
    content = update.message.text
    fid = None
    
    if update.message.document:
        msg_type = 'document'
        fid = update.message.document.file_id
        content = update.message.caption or "Документ"
        try: await update.message.set_reaction("👍")
        except: pass
    elif update.message.photo:
        msg_type = 'photo'
        fid = update.message.photo[-1].file_id
        content = update.message.caption or "Фото"
        try: await update.message.set_reaction("👀")
        except: pass
        
    await db.add_chat_message(oid, user.id, is_admin, msg_type, content, fid)
    
    # Notify other party
    o = await db.get_order(oid)
    target_id = o['user_id'] if is_admin else ADMIN_ID
    
    prefix = "👮‍♂️ <b>Менеджер:</b>" if is_admin else f"👤 <b>Клиент (Заказ #{oid}):</b>"
    
    try:
        if fid:
            await context.bot.send_document(target_id, fid, caption=f"{prefix} {content}", parse_mode="HTML")
        else:
            await context.bot.send_message(target_id, f"{prefix} {content}", parse_mode="HTML")
    except: pass
    
    # Confirm to sender (send new message to avoid editing old one which might be far up)
    # Actually, better to just reply or send a fresh message with the keyboard
    await update.message.reply_text("✅ Отправлено", reply_markup=kb.chat_kb(oid, is_admin))
    return CHAT_STEP

async def cancel_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Return to order view
    query = update.callback_query
    if query: await query.answer()
    
    oid = context.user_data.get('chat_oid')
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)
    
    if is_admin:
        # Redirect to admin order view
        # We need to import admin_god handlers or just simulate the callback
        # Since we can't easily call another handler's function if it expects specific state, 
        # we'll just send a message with the admin order keyboard.
        o = await db.get_order(oid)
        txt = (
            f"📦 <b>ЗАКАЗ #{oid}</b>\n"
            f"👤 Юзер: {o['user_id']}\n"
            f"📚 Тип: {o['service_type']}\n"
            f"💰 Цена: {o['price']} ₽\n"
            f"📊 Статус: {o['status']}\n"
            f"📝 Тема: {o['topic']}\n"
        )
        if query:
            await _safe_edit(query, txt, reply_markup=admin_kb.order_actions(oid, o['status']), parse_mode="HTML")
        else:
            await update.message.reply_text(txt, reply_markup=admin_kb.order_actions(oid, o['status']), parse_mode="HTML")
    else:
        # Redirect to client order view
        o = await db.get_order(oid)
        status_emoji = {"review": "🟡", "pending_pay": "💳", "work": "⚙️", "done": "✅", "cancel": "❌"}
        txt = (
            f"{status_emoji.get(o['status'], '?')} <b>ЗАКАЗ #{o['id']}</b>\n"
            f"📚 Услуга: {o['service_type']}\n"
            f"📝 Тема: {o['topic']}\n"
            f"💰 Цена: {o['price']} ₽\n"
            f"📅 Дедлайн: {o['deadline_type']}\n"
            f"📊 Статус: {o['status']}\n"
        )
        if query:
            await _safe_edit(query, txt, reply_markup=kb.order_details_kb(oid), parse_mode="HTML")
        else:
            await update.message.reply_text(txt, reply_markup=kb.order_details_kb(oid), parse_mode="HTML")
            
    return ConversationHandler.END

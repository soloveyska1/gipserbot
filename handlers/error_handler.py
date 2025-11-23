from telegram import Update
from telegram.ext import ContextTypes
import logging
import traceback
import json
from config import ADMIN_IDS

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a list of strings ending with a newline character.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    # Escape HTML characters in traceback
    import html
    tb_string = html.escape("".join(tb_list))

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"🚨 <b>CRITICAL ERROR</b>\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n"
        f"<pre>{tb_string}</pre>"
    )

    # Notify Admin
    for admin_id in ADMIN_IDS:
        try:
            # Split message if too long
            if len(message) > 4096:
                for x in range(0, len(message), 4096):
                    await context.bot.send_message(chat_id=admin_id, text=message[x:x+4096], parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
        except:
            pass
            
    # Notify User (Friendly message)
    if isinstance(update, Update) and update.effective_message:
        text = (
            "🤠 <b>Упс! Осечка...</b>\n\n"
            "Что-то пошло не так. Шериф уже получил уведомление и чистит револьвер.\n"
            "Попробуй повторить действие через минуту или напиши /start."
        )
        try:
            await update.effective_message.reply_text(text, parse_mode="HTML")
        except: pass

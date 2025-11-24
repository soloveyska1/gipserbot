import html
import json
import json
import logging
import traceback
import html

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS, LOG_CHANNEL_ID
import utils

# Настройка логгера
logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логирует ошибку и отправляет отчет админу."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = html.escape("".join(tb_list))

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"🚨 <b>CRITICAL ERROR</b>\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n"
        f"<pre>{tb_string}</pre>"
    )

    user_id = update.effective_user.id if isinstance(update, Update) and update.effective_user else 0
    recent_actions = utils.get_recent_actions(user_id)
    steps_block = "\n".join(recent_actions[-10:]) if recent_actions else "—"

    crash_report = (
        "#CRASH\n"
        f"User: {user_id}\n"
        f"Last actions:\n{steps_block}\n\n"
        f"{message}"
    )

    target = LOG_CHANNEL_ID or (ADMIN_IDS[0] if ADMIN_IDS else None)
    if target:
        try:
            for x in range(0, len(crash_report), 3500):
                await context.bot.send_message(chat_id=target, text=crash_report[x:x+3500], parse_mode="HTML")
        except Exception:
            pass

    try:
        await utils.db.add_action_log(user_id, "#CRASH", event_type="error", meta="exception")
    except Exception:
        logger.debug("Failed to persist crash log", exc_info=True)
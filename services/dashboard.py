import asyncio
import logging
from datetime import datetime

from telegram import Bot
from telegram.constants import ParseMode

from config import LOG_CHANNEL_ID
from database import core as db


def _progress_bar(percent: float, length: int = 10) -> str:
    filled = int(min(length, max(0, round(length * percent / 100))))
    return f"{'■' * filled}{'□' * (length - filled)}"


class LiveDashboard:
    def __init__(self):
        self.message_id: int | None = None
        self.chat_id = LOG_CHANNEL_ID
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

    async def _ensure_message(self, bot: Bot):
        if not self.chat_id:
            return
        if self.message_id:
            return
        msg = await bot.send_message(chat_id=self.chat_id, text="📡 INIT", parse_mode=ParseMode.HTML)
        try:
            await bot.pin_chat_message(chat_id=self.chat_id, message_id=msg.message_id, disable_notification=True)
        except Exception:
            pass
        self.message_id = msg.message_id

    async def _render(self, bot: Bot):
        if not self.chat_id:
            return
        metrics = await db.get_live_pulse_metrics()
        now = datetime.utcnow()
        progress_pct = 0 if metrics.get("avg_revenue", 0) == 0 else (metrics["revenue_today"] / metrics["avg_revenue"]) * 100
        bar = _progress_bar(progress_pct)
        text = (
            "🟢 <b>SYSTEM STATUS: ONLINE</b>\n"
            f"📅 {now.strftime('%d.%m.%Y')} | 🕒 {now.strftime('%H:%M')}\n\n"
            f"💰 <b>Revenue Today:</b> {int(metrics.get('revenue_today', 0))} ₽  [{bar}] ({progress_pct:.0f}% of avg)\n"
            f"👥 <b>Active Users (1h):</b> {metrics.get('active_users_1h', 0)}\n"
            f"📦 <b>Pending Orders:</b> {metrics.get('pending_orders', 0)} (⚠️ {metrics.get('urgent_count', 0)} Urgent)\n\n"
            f"📉 <b>Conversion Today:</b> {metrics.get('conversion', 0)}%\n"
            f"🚨 <b>Errors:</b> {metrics.get('errors', 0)}"
        )
        try:
            await bot.edit_message_text(chat_id=self.chat_id, message_id=self.message_id, text=text, parse_mode=ParseMode.HTML)
        except Exception:
            self.message_id = None
            await self._ensure_message(bot)

    async def tick(self, context):
        async with self.lock:
            await self._ensure_message(context.bot)
            await self._render(context.bot)

    def attach(self, application):
        if not self.chat_id:
            return
        job_queue = getattr(application, "job_queue", None)
        if not job_queue:
            self.logger.warning("JobQueue is not available. Install PTB with job-queue extras or APScheduler to enable live dashboard updates.")
            return
        job_queue.run_repeating(self.tick, interval=60, first=5, name="live_pulse")

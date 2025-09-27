import logging
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Lightweight Telegram notifier that sends messages without running the bot polling loop.

    Respects the settings flags:
    - telegram_notifications_enabled
    - TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._enabled: bool = bool(
            getattr(self.settings, "telegram_notifications_enabled", True)
            and self.settings.telegram_bot_token
            and self.settings.telegram_chat_id
        )
        self._bot = None
        if self._enabled:
            try:
                from telegram import Bot  # type: ignore
                self._bot = Bot(token=self.settings.telegram_bot_token)
            except Exception as e:
                logger.warning(f"Telegram notifier disabled (init failed): {e}")
                self._enabled = False

    async def send(self, text: str, parse_mode: Optional[str] = 'HTML') -> None:
        if not self._enabled or not self._bot:
            return
        try:
            await self._bot.send_message(
                chat_id=self.settings.telegram_chat_id,
                text=text,
                parse_mode=parse_mode,
            )
        except Exception as e:
            # Fail silently to avoid impacting main workflows
            logger.debug(f"Telegram notifier send failed: {e}")


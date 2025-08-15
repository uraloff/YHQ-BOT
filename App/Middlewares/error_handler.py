import logging
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound, TelegramBadRequest


logger = logging.getLogger(__name__)


class IgnoreBlockedUserMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        try:
            return await handler(event, data)

        except TelegramForbiddenError as e:
            logger.warning(f"❌ Пользователь заблокировал бота: {e}")
        except TelegramNotFound as e:
            logger.warning(f"❌ Пользователь не найден (возможно, удалён): {e}")
        except TelegramBadRequest as e:
            logger.warning(f"⚠ Плохой запрос: {e}")
        except Exception as e:
            logger.exception(f"💥 Необработанная ошибка: {e}")

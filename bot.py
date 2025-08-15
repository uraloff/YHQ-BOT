from os import getenv
import logging, asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from App.Handlers.Admin.admin import admin_router
from App.Handlers.User.uz_handlers import uz_user_router
from App.Middlewares.error_handler import IgnoreBlockedUserMiddleware


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(name)s — %(levelname)s — %(message)s'
)


async def main():
    load_dotenv()
    # await async_main()

    logging.info('Загрузка информации...')

    bot = Bot(
        token=getenv('TOKEN'),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    logging.info('Бот успешно запущен ✅')
    dp.include_routers(uz_user_router, admin_router)
    dp.message.middleware(IgnoreBlockedUserMiddleware())
    dp.callback_query.middleware(IgnoreBlockedUserMiddleware())

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), drop_pending_updates=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info('Бот успешно выключен ❌')
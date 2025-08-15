from os import getenv

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from App.Database.requests import check_confirmed_admin


async def set_commands(bot: Bot, user_id: int):
    if user_id == int(getenv('ADMIN_ID')) or await check_confirmed_admin(user_id):
        commands = [
            BotCommand(command='start', description='Botni ishga tushirish'),
            BotCommand(command='admin', description='Admin paneli'),
            BotCommand(command='user_mode', description='Foydalanuvchi rejimiga o\'tish'),
        ]
        
        await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=user_id))
    else:
        commands = [
            BotCommand(command='start', description='Botni ishga tushirish'),
            BotCommand(command='info', description='Bot haqida ma\'lumot'),
        ]
    
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

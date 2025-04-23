from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import (Message,
                           CallbackQuery)
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.state import State, StatesGroup

from bot_worker.util.helpers import cache_handling, kb_builder
from models import User
from settings import CHANNEL_USERNAME, logger
from db import DB


class Form(StatesGroup):
    waiting_for_subscription = State()


class StartMenu:
    def __init__(self, db: DB):
        self.db = db

    async def check_user_in_db(self, message: Message) -> None:
        if not await self.db.get_user_by_tg_id(message.from_user.id):
            user = User(tg_id=message.from_user.id,
                        username=message.from_user.username,
                        first_name=message.from_user.first_name,
                        last_name=message.from_user.last_name)
            await self.db.add_user(user)

    async def check_chat_member(self, bot: Bot, tg_id: int) -> bool:
        try:
            member = await bot.get_chat_member(CHANNEL_USERNAME, tg_id)
            if member.status in ['left', 'kicked']:
                return False
            return True
        except TelegramAPIError as e:
            logger.error(f'Ошибка при проверке подписки на канал: {e}')
            return False

    async def start(self,
                    message: Message,
                    state: FSMContext,
                    bot: Bot) -> None:
        await self.check_user_in_db(message)
        if not await self.check_chat_member(bot, message.from_user.id):
            await state.set_state(Form.waiting_for_subscription)
            kb = await kb_builder(kb_values=[
                [{"text": "Перейти в канал",
                  "url": f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"}],
                [{"text": "Я подписался",
                  "callback_data": "check_subscription"}]
            ])
            await message.answer(
                "Чтобы пользоваться ботом, подпишитесь на канал.",
                reply_markup=kb
            )
        else:
            await message.answer("Добро пожаловать!")
            await self.main_menu(message, state, bot)

    async def check_subscription(self,
                                 callback: CallbackQuery,
                                 state: FSMContext,
                                 bot: Bot) -> None:
        """Вывод главного меню"""
        try:
            member = await bot.get_chat_member(CHANNEL_USERNAME, callback.from_user.id)
            if not await self.check_chat_member(bot, callback.from_user.id):
                await callback.answer("Вы все еще не подписаны. "
                                      "Пожалуйста, подпишитесь на канал.")
            else:
                await callback.answer("Добро пожаловать!")
                await self.main_menu(callback, state, bot)
        except TelegramAPIError as e:
            await callback.answer(f"Ошибка: {e}", show_alert=True)

    async def main_menu(self,
                        target: Message | CallbackQuery,
                        state: FSMContext,
                        bot: Bot) -> None:
        """Вывод главного меню"""
        try:
            if isinstance(target, Message):
                msg_send = target.answer
            else:
                msg_send = target.message.edit_text

            await cache_handling(target.from_user.id, state, bot, self.db)

            menu_kb = await kb_builder(kb_values=[
                [{"text": "Каталог", "callback_data": "category_choice"}],
                [{"text": "Корзина", "callback_data": "show_cart"},
                 {"text": "Заказы", "callback_data": "show_orders"}],
                [{"text": "FAQ", "callback_data": "faq"}]
            ])
            text = ("Это магазин. Вы находитесь в главном меню. Чтобы выбрать "
                    "товар перейдите в 'Каталог', чтобы оформить покупку перейдите "
                    "в 'Корзину', ответы на частые вопросы вы найдете в 'FAQ'")
            await msg_send(text=text, reply_markup=menu_kb)
        except Exception as e:
            logger.error(f'<main_menu>: {e}')

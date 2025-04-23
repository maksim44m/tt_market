from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from .services import Form, StartMenu
from settings import db


router = Router()
worker = StartMenu(db)


@router.message(Command('start'))
async def start_handler(
    message: Message,
    state: FSMContext,
    bot: Bot
) -> None:
    """Обработчик сообщения /start"""
    await worker.start(message, state, bot)


@router.callback_query(Form.waiting_for_subscription,
                       F.data == 'check_subscription')
async def check_subscription_handler(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot
) -> None:
    """Обработчик проверки подписки на канал"""
    await worker.check_subscription(callback, state, bot)


@router.callback_query(F.data == "back_to_menu")
async def main_menu_handler(
    target: Message | CallbackQuery,
    state: FSMContext,
    bot: Bot
) -> None:
    """Обработчик перехода в главное меню"""
    await worker.main_menu(target, state, bot)

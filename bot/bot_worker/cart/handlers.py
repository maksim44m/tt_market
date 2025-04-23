from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from .services import CartWorker
from settings import db


router = Router()
worker = CartWorker(db)


@router.callback_query(F.data == 'show_cart')
async def show_cart_handler(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot
) -> None:
    """Обработчик подтверждения выбора продуктов"""
    await worker.show_cart(callback, state, bot)

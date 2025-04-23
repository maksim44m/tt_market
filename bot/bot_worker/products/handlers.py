from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from .services import ProductWorker
from settings import db


router = Router()
worker = ProductWorker(db)


@router.callback_query(F.data.startswith("category_id_"))
async def subcategory_choice_handler(
    callback: CallbackQuery
) -> None:
    """Обработчик выбора категории"""
    await worker.subcategory_choice(callback)


@router.callback_query(F.data == "category_choice")
async def category_choice_handler(
    callback: CallbackQuery
) -> None:
    """Обработчик выбора раздела Каталог в главном меню"""
    await worker.category_choice(callback)


@router.callback_query(F.data.startswith("subcategory_id_"))
async def product_choice_handler(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot
) -> None:
    """Обработчик выбора подкатегории"""
    await worker.product_choice(callback, state, bot)


@router.callback_query(F.data.startswith(("increase_", "decrease_")))
async def quantity_change_handler(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Обработчик кнопок изменения количества продукта"""
    await worker.quantity_change(callback, state)

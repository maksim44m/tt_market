from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineQuery
from aiogram.fsm.context import FSMContext

from .services import faq, inline_faq_handler


router = Router()

@router.callback_query(F.data == "faq")
async def faq_handler(callback: CallbackQuery) -> None:
    await faq(callback)


@router.inline_query()
async def inline_faq_handler_handler(inline_query: InlineQuery) -> None:
    await inline_faq_handler(inline_query)

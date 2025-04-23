from aiogram import Router, F
from aiogram.types import CallbackQuery

from .services import PaymentWorker
from settings import db

router = Router()
worker = PaymentWorker(db)


@router.callback_query(F.data.startswith('pay_order_'))
async def payment_handler(callback: CallbackQuery):
    """Обработчик платежа"""
    return await worker.payment(callback)

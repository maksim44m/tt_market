import asyncio
import os

import uuid
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yookassa import Payment, Configuration
from aiogram import types, Router, F
from yookassa.domain.response import PaymentResponse

from models import OrderStatus
from settings import logger, db

router = Router()

Configuration.account_id = os.getenv('YOOKASSA_SHOP_ID')
Configuration.secret_key = os.getenv('YOOKASSA_API_KEY')


async def check_pay(payment_id: str, order_id: int) -> Optional[OrderStatus]:
    payment_data = await asyncio.to_thread(Payment.find_one, *[payment_id])  # type: PaymentResponse
    status = payment_data.status
    if status == 'succeeded':
        await db.set_order_status(order_id, OrderStatus.PAID)
        await db.set_order_payment_id(order_id, '')  # удаление payment_id
        return OrderStatus.PAID
    else:
        return None


@router.callback_query(F.data.startswith('pay_order_'))
async def payment(callback: types.CallbackQuery):
    """Обработчик платежа через YooKassa. Вывод ссылки для оплаты."""
    try:
        order_id = int(callback.data.split("_order_")[1])
    except Exception as e:
        logger.error(f"check_pay: {e}")
        return

    try:
        value, order = await db.get_order_sum(order_id)
        if order.status in [OrderStatus.COMPLETED, OrderStatus.PAID]:
            await callback.answer('Заказ уже оплачен.')
            return

        if order.payment_id:
            if await check_pay(order.payment_id, order.id):
                await callback.answer('Заказ уже оплачен.')
                return

        if value == 0:
            await callback.answer('При формировании заказа произошла ошибка.')
            logger.error(f"order_menu: sum order № {order_id} == 0")
            return

        tg_username = callback.from_user.username

        yookassa: PaymentResponse = await asyncio.to_thread(
            create_payment_yookassa, *[value, tg_username]
        )
        await db.set_order_payment_id(order_id, yookassa.id)
        payment_url = yookassa.confirmation.confirmation_url

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="YooKassa", url=payment_url)],
            [InlineKeyboardButton(text="В заказы", callback_data="show_orders")],
            [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
        ])
        await callback.message.edit_text(f"Выберите способ оплаты:",
                                         reply_markup=kb)
    except Exception as e:
        await callback.answer("Ошибка при создании платежа.", show_alert=True)
        logger.error(f'payment: {e}')


def create_payment_yookassa(value: float, tg_username: str):
    """Функция создания платежа, запускаемая в отдельном потоке"""
    return Payment.create({
        "amount": {
            "value": f"{value}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f'https://t.me/{tg_username}'  # URL возврата после оплаты
        },
        "capture": True,
        "description": "Оплата заказа в тестовом режиме"
    }, uuid.uuid4())

import asyncio
import os
import uuid
from typing import Optional

from aiogram.types import CallbackQuery
from yookassa import Payment, Configuration
from yookassa.domain.response import PaymentResponse

from models import OrderStatus
from settings import CHANNEL_USERNAME, logger
from bot_worker.util.helpers import kb_builder
from db import DB

class PaymentWorker:
    def __init__(self, db: DB):
        self.db = db
        Configuration.account_id = os.getenv('YOOKASSA_SHOP_ID')
        Configuration.secret_key = os.getenv('YOOKASSA_API_KEY')

    async def check_pay(self,
                        payment_id: str,
                        order_id: int) -> Optional[OrderStatus]:
        payment_data = await asyncio.to_thread(Payment.find_one, *[payment_id])
        status = payment_data.status
        if status == 'succeeded':
            await self.db.set_order_status(order_id, OrderStatus.PAID)
            # удаление payment_id
            await self.db.set_order_payment_id(order_id, '')
            return OrderStatus.PAID
        else:
            return None

    async def payment(self, callback: CallbackQuery) -> None:
        """Вывод ссылки для оплаты."""
        try:
            order_id = int(callback.data.split("_order_")[1])
        except Exception as e:
            logger.error(f"payment: {e}")
            return

        try:
            value, order = await self.db.get_order_sum(order_id)
            if order.status in [OrderStatus.COMPLETED, OrderStatus.PAID]:
                await callback.answer('Заказ уже оплачен.')
                return

            if order.payment_id:
                if await self.check_pay(order.payment_id, order.id):
                    await callback.answer('Заказ уже оплачен.')
                    return

            if value == 0:
                await callback.answer('При формировании заказа произошла ошибка.')
                logger.error(f"payment: sum order № {order_id} == 0")
                return

            yookassa: PaymentResponse = await asyncio.to_thread(
                self.yookassa_payment, *[value]
            )
            await self.db.set_order_payment_id(order_id, yookassa.id)
            payment_url = yookassa.confirmation.confirmation_url

            kb = await kb_builder(kb_values=[
                [{"text": "YooKassa", "url": payment_url}],
                [{"text": "В заказы", "callback_data": "show_orders"}],
                [{"text": "Главное меню", "callback_data": "back_to_menu"}]
            ])
            await callback.message.edit_text(f"Выберите способ оплаты:",
                                             reply_markup=kb)
        except Exception as e:
            await callback.answer("Ошибка при создании платежа.", show_alert=True)
            logger.error(f'payment: {e}')

    @staticmethod
    def yookassa_payment(value: float):
        """Функция создания платежа, запускаемая в отдельном потоке"""
        return Payment.create({
            "amount": {
                "value": f"{value}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                # URL возврата после оплаты
                "return_url": f'https://t.me/{CHANNEL_USERNAME.lstrip("@")}'
            },
            "capture": True,
            "description": "Оплата заказа в тестовом режиме"
        }, uuid.uuid4())

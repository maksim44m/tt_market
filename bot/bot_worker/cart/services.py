from aiogram import Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot_worker.products.handlers import worker as product_worker
from bot_worker.util.helpers import cache_handling, kb_builder
from settings import logger

from db import DB


class CartWorker:
    def __init__(self, db: DB):
        self.db = db

    async def show_cart(self,
                        callback: CallbackQuery,
                        state: FSMContext,
                        bot: Bot) -> None:
        """Вывод корзины"""
        try:
            tg_id = callback.from_user.id
            await cache_handling(tg_id, state, bot, self.db)

            cart_item_with_quantities = \
                await self.db.get_cart_items_with_quantities(tg_id)
            if not cart_item_with_quantities:
                await callback.answer('Корзина пока пуста')
                return
            await callback.message.delete()
            # вывод корзины
            await product_worker.send_product_menu(
                cart_item_with_quantities, tg_id, state, bot
            )
            # сообщение с выбором способа доставки
            kb = await kb_builder(kb_values=[
                [{"text": "Выбрать способ доставки", "callback_data": "send_delivery_choice"},
                 {"text": "Главное меню", "callback_data": "back_to_menu"}]
            ])
            await bot.send_message(
                chat_id=tg_id,
                text=f'Для продолжения оформления заказа выберите способ доставки:',
                reply_markup=kb
            )
        except Exception as e:
            logger.error(f'show_cart: {e}')

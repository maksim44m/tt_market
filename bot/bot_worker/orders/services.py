from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import Bot
from aiogram.fsm.state import State, StatesGroup

from bot_worker.payments.handlers import worker as payment_worker
from bot_worker.start_menu.handlers import worker as start_menu_worker
from bot_worker.util.helpers import cache_handling, kb_builder
from db import DB
from settings import logger
from models import OrderStatus


class Form(StatesGroup):
    waiting_for_delivery_info = State()


class OrderWorker:
    def __init__(self, db: DB):
        self.db = db

    async def send_delivery_choice(self,
                                   callback: CallbackQuery,
                                   bot: Bot,
                                   state: FSMContext) -> None:
        """Обработчик подтверждения заказа. Отправка выбора способа доставки"""
        await cache_handling(callback.from_user.id, state, bot, self.db)
        kb = await kb_builder(kb_values=[
            [{"text": 'Самовывоз', "callback_data": 'create_order'},
             {"text": 'Доставка до адреса', "callback_data": 'delivery_info'}],
            [{"text": "Главное меню", "callback_data": "back_to_menu"}]
        ])
        # Отправка нового сообщения с выбором доставки
        await callback.message.edit_text(text=f'Выберите способ доставки:',
                                         reply_markup=kb)

    @staticmethod
    async def delivery_info(callback: CallbackQuery,
                            state: FSMContext) -> None:
        """Обработчик доставки. Запрос адреса у пользователя"""
        await state.set_state(Form.waiting_for_delivery_info)
        kb = await kb_builder(kb_values=[
            [{"text": "Главное меню", "callback_data": "back_to_menu"}]
        ])
        text = 'Отправьте адрес доставки в формате: Город, Улица, Дом, Квартира'
        await callback.message.edit_text(text=text, reply_markup=kb)

    async def create_order(self,
                           target: Message | CallbackQuery) -> None:
        """Отправка способа оплаты"""
        tg_id = target.from_user.id
        if isinstance(target, Message):
            delivery_address = f'Доставка. Адрес: {target.text.strip()}'
            msg_send = target.answer
        else:
            delivery_address = 'Самовывоз'
            msg_send = target.message.edit_text

        order_id = await self.db.create_order_db(tg_id, delivery_address)

        kb = await kb_builder(kb_values=[
            [{"text": "Оплатить", "callback_data": f"pay_order_{order_id}"}],
            [{"text": "Главное меню", "callback_data": "back_to_menu"}]
        ])
        text = "Ваш заказ готов к оплате.\nНажмите 'Оплатить' для завершения."
        await msg_send(text, reply_markup=kb)

    async def show_orders(self,
                          callback: CallbackQuery,
                          state: FSMContext,
                          bot: Bot) -> None:
        """Вывод списка заказов"""
        tg_id = callback.from_user.id
        if callback.data.startswith('delete_order_'):
            try:
                order_id = int(callback.data.split("_order_")[1])
                await self.db.delete_order(int(order_id))
            except Exception as e:
                logger.error(f"show_orders: {e}")
                return

        orders = await self.db.get_orders_by_user(tg_id)
        if not orders:  # переход в главное меню, если заказов нет
            await callback.answer("У вас нет заказов.")
            await start_menu_worker.main_menu(callback, state, bot)
            return

        message_text = "Ваши заказы:\n"
        kb_values = []
        for order in orders:
            if order.payment_id:
                # проверка оплаты при входе в раздел Заказы
                # проверка выполняется тут так как после перехода на страницу оплаты
                # колбек не выполняется и далее проще поймать пользователя
                # в разделе Заказы
                status = await payment_worker.check_pay(order.payment_id, order.id)
            else:
                status = order.status
            kb_values.append([{"text": f"Заказ #{order.id} - {status}",
                               "callback_data": f"order_{order.id}"}])

        kb_values.append(
            [{"text": "Главное меню", "callback_data": "back_to_menu"}])

        kb = await kb_builder(kb_values=kb_values)
        await callback.message.edit_text(message_text, reply_markup=kb)

    async def order_menu(self, callback: CallbackQuery) -> None:
        """Вывод меню заказа"""
        # Извлекаем идентификатор заказа
        try:
            order_id = int(callback.data.split("der_")[1])
        except Exception as e:
            logger.error(f"order_menu: {e}")
            return

        order = await self.db.get_order_by_id(order_id)
        if order is None:
            logger.error(f"order_menu: order № {order_id} is None")
            return

        kb_values = [
            [{"text": "Оплатить", "callback_data": f"pay_order_{order_id}"}],
            [{"text": "Удалить заказ", "callback_data": f"delete_order_{order_id}"}],
            [{"text": "Главное меню", "callback_data": "back_to_menu"}]
        ]

        if order.status in [OrderStatus.COMPLETED, OrderStatus.PAID]:
            kb_values.pop(0)  # удаление "Оплатить"
            if order.status == OrderStatus.PAID:
                kb_values.pop(0)  # удаление "Удалить заказ"

        kb = await kb_builder(kb_values=kb_values)
        await callback.message.edit_text(
            f"Заказ #{order_id}. Выберите действие:",
            reply_markup=kb
        )

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from .services import OrderWorker
from bot_worker.orders.services import Form
from settings import db

router = Router()
worker = OrderWorker(db)


@router.callback_query(F.data == 'send_delivery_choice')
async def send_delivery_choice_handler(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext
) -> None:
    """Обработчик подтверждения заказа. Отправка выбора способа доставки"""
    await worker.send_delivery_choice(callback, bot, state)


@router.callback_query(F.data == 'delivery_info')
async def delivery_info_handler(
    callback: CallbackQuery,
    state: FSMContext
) -> None:
    """Обработчик доставки. Запрос адреса у пользователя"""
    await worker.delivery_info(callback, state)


@router.callback_query(F.data == 'create_order')
@router.message(Form.waiting_for_delivery_info)
async def create_order_handler(
    target: Message | CallbackQuery
) -> None:
    """Обработчик создания заказа. Отправка способа оплаты"""
    await worker.create_order(target)


@router.callback_query(F.data.startswith('delete_order_'))
@router.callback_query(F.data == 'show_orders')
async def show_orders_handler(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot
) -> None:
    """Обработчик просмотра заказов. Вывод списка заказов"""
    await worker.show_orders(callback, state, bot)


@router.callback_query(F.data.startswith('order_'))
async def order_menu_handler(
    callback: CallbackQuery
) -> None:
    """Обработчик выбранного заказа. Вывод меню заказа"""
    await worker.order_menu(callback)

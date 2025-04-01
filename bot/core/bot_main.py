from typing import List, Tuple

from aiogram import types, Router, F, Bot  # pip install aiogram
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Category, SubCategory, Product, OrderStatus
from settings import CHANNEL_USERNAME, db, logger
from core.bot_pay import check_pay

router = Router()


class Form(StatesGroup):
    waiting_for_subscription = State()
    waiting_for_delivery_info = State()


@router.callback_query(F.data.startswith("order_", ))
async def order_menu(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбранного заказа. Вывод меню заказа"""
    # Извлекаем идентификатор заказа
    try:
        order_id = int(callback.data.split("der_")[1])
    except Exception as e:
        logger.error(f"order_menu: {e}")
        return

    order = await db.get_order_by_id(order_id)
    if order is None:
        logger.error(f"order_menu: order № {order_id} is None")
        return

    inline_keyboard = [
        [InlineKeyboardButton(text="Оплатить",
                              callback_data=f"pay_order_{order_id}")],
        [InlineKeyboardButton(text="Удалить заказ",
                              callback_data=f"delete_order_{order_id}")],
        [InlineKeyboardButton(text="Главное меню",
                              callback_data="back_to_menu")]
    ]

    if order.status in [OrderStatus.COMPLETED, OrderStatus.PAID]:
        inline_keyboard.pop(0)  # удаление "Оплатить"
        if order.status == OrderStatus.PAID:
            inline_keyboard.pop(0)  # удаление "Удалить заказ"

    await callback.message.edit_text(
        f"Заказ #{order_id}. Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    )


@router.callback_query(F.data.startswith('delete_order_'))
@router.callback_query(F.data == 'show_orders')
async def show_orders(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик просмотра заказов. Вывод списка заказов"""
    tg_id = callback.from_user.id
    if callback.data.startswith('delete_order_'):
        try:
            order_id = int(callback.data.split("_order_")[1])
            await db.delete_order(int(order_id))
        except Exception as e:
            logger.error(f"show_orders: {e}")
            return

    orders = await db.get_orders_by_user(tg_id)
    if not orders:  # переход в главное меню, если заказов нет
        await callback.answer("У вас нет заказов.")
        await main_menu(callback, state)
        return

    message_text = "Ваши заказы:\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for order in orders:
        if order.payment_id:
            # проверка оплаты при входе в раздел Заказы
            # проверка выполняется тут так как после перехода на страницу оплаты
            # колбек не выполняется и далее проще поймать пользователя
            # в разделе Заказы
            status = await check_pay(order.payment_id, order.id)
        else:
            status = order.status
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"Заказ #{order.id} - {status}",
                                 callback_data=f"order_{order.id}")
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")
    ])

    await callback.message.edit_text(message_text, reply_markup=kb)


@router.callback_query(F.data == "create_order")
@router.message(Form.waiting_for_delivery_info)
async def create_order(target: types.Message | types.CallbackQuery):
    """Обработчик создания заказа. Отправка способа оплаты"""
    tg_id = target.from_user.id
    if isinstance(target, types.Message):
        delivery_address = f'Доставка. Адрес: {target.text.strip()}'
        msg_send = target.answer
    elif isinstance(target, types.CallbackQuery):
        delivery_address = 'Самовывоз'
        msg_send = target.message.edit_text
    else:
        raise TypeError("Unsupported target type")
    order_id = await db.create_order_db(tg_id, delivery_address)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить", callback_data=f"pay_order_{order_id}")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    text = "Ваш заказ готов к оплате.\nНажмите 'Оплатить' для завершения."
    await msg_send(text, reply_markup=kb)


@router.callback_query(F.data == 'delivery_info')
async def delivery_info(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик доставки. Запрос адреса у пользователя"""
    await state.set_state(Form.waiting_for_delivery_info)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    text = 'Отправьте адрес доставки в формате: Город, Улица, Дом, Квартира'
    await callback.message.edit_text(text=text, reply_markup=kb)


@router.callback_query(F.data == 'send_delivery_choice')
async def send_delivery_choice(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """Обработчик подтверждения заказа. Отправка выбора способа доставки"""
    await cache_handling(callback.from_user.id, state, bot)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Самовывоз', callback_data='create_order'),
         InlineKeyboardButton(text='Доставка до адреса', callback_data='delivery_info')]
        ,
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    # Отправка нового сообщения с выбором доставки
    await callback.message.edit_text(text=f'Выберите способ доставки:',
                                     reply_markup=kb)


async def cache_handling(tg_id, state: FSMContext, bot: Bot):
    """Сохранение в БД и удаление сообщений"""
    state_data = await state.get_data()
    messages_cache = state_data.get("messages_cache", [])
    # сохранение количества товара из кеша в бд
    if messages_cache:
        try:
            await db.save_current_quantity_in_cart(tg_id, messages_cache)
        except Exception as e:
            logger.error(f"Error save_current_quantity_in_cart: {e}")
    # удаление сообщений с товарами
    for message_id, _, _ in messages_cache:
        try:
            await bot.delete_message(chat_id=tg_id, message_id=message_id)
        except:
            pass  # Сообщение уже удалено
    await state.update_data(messages_cache=[], confirmation_cache=None)


@router.callback_query(F.data == 'show_cart')
async def show_cart(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик подтверждения выбора продуктов. Вывод корзины"""
    try:
        tg_id = callback.from_user.id
        await cache_handling(tg_id, state, bot)

        cart_item_with_quantities = \
            await db.get_cart_items_with_quantities(tg_id)
        if not cart_item_with_quantities:
            await callback.answer('Корзина пока пуста')
            return
        await callback.message.delete()
        # вывод корзины
        await send_product_menu(cart_item_with_quantities, tg_id, state, bot)
        # сообщение с выбором способа доставки
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Выбрать способ доставки',
                                  callback_data='send_delivery_choice'),
             InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
        ])
        await bot.send_message(
            chat_id=tg_id,
            text=f'Для продолжения оформления заказа нажмите\n"Подтвердить":',
            reply_markup=kb
        )
    except Exception as e:
        logger.error(f'show_cart: {e}')


async def build_quantity_kb(product_id: int, quantity: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="–", callback_data=f"decrease_{product_id}"),
         InlineKeyboardButton(text=f"{quantity}", callback_data="noop"),
         InlineKeyboardButton(text="+", callback_data=f"increase_{product_id}")]
    ])


@router.callback_query(F.data.startswith(("increase_", "decrease_")))
async def handle_quantity_change(callback: types.CallbackQuery,
                                 state: FSMContext):
    """Обработчик кнопок изменения количества продукта"""
    # получение действия и идентификатора продукта
    action, product_id = callback.data.split("_")

    # получение количества продукта
    state_data = await state.get_data()
    messages_cache = state_data.get("messages_cache", [])
    logger.info(f'handle_quantity_change: {messages_cache=}')

    # Сохранение предыдущего количества для проверки
    quantity = next(
        (qty for msg_id, pid, qty in messages_cache if msg_id ==
         callback.message.message_id and pid == int(product_id)), 0
    )
    logger.info(f'handle_quantity_change: {quantity=}')

    # Вычисление нового количества
    if action == "increase":
        quantity += 1
    elif action == "decrease" and quantity > 0:
        quantity -= 1
    else:
        return

    # обновление кеша
    new_messages_cache = [
        (msg_id, pid, quantity if pid == int(product_id) else qty)
        for msg_id, pid, qty in messages_cache
    ]
    logger.info(f'handle_quantity_change: {new_messages_cache=}')
    await state.update_data(messages_cache=new_messages_cache)

    try:
        logger.info(f'handle_quantity_change: {quantity=}')
        kb = await build_quantity_kb(product_id, quantity)
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def save_message_cache(state: FSMContext, message_id: int,
                             product_id: int, quantity: int = 0):
    """
    Кеширование данных в state.get_data() в виде:
    {'messages_cache': [(message_id, product_id, quantity), ]}
    """
    # Сохранение идентификатора сообщения в состоянии
    data = await state.get_data()
    messages_cache = data.get("messages_cache", [])  # для первой итерации
    messages_cache.append((message_id, product_id, quantity))
    await state.update_data(messages_cache=messages_cache)


async def send_product_menu(products_with_qty: List[Tuple[Product, int]],
                            tg_id: int, state: FSMContext, bot: Bot):
    """Отправка отдельных сообщений с продуктами"""
    await cache_handling(tg_id, state, bot)
    for product, quantity in products_with_qty:
        # формирование инлайн кнопок
        kb = await build_quantity_kb(product.id, quantity)
        # отправка сообщения
        sent_message = await bot.send_photo(
            chat_id=tg_id,
            photo=product.image_url,
            caption=f"{product.name}\n"
                    f"{product.description}\n"
                    f"Цена: {product.price}\n\n"
                    f"В корзине:",
            reply_markup=kb
        )
        await save_message_cache(state, sent_message.message_id,
                                 product.id, quantity)


@router.callback_query(F.data.startswith("subcategory_id_"))
async def product_choice(callback: types.CallbackQuery,
                         state: FSMContext, bot: Bot):
    """Обработчик выбора подкатегории. Вывод товаров"""
    tg_id = callback.from_user.id
    page = 1
    page_size = 5

    # Разбор callback_data для получения subcategory_id и номера страницы
    if '_page_' in callback.data:
        cb_start, page_str = callback.data.split('_page_')
        page = int(page_str)
        if page < 1:
            return
        subcategory_id = int(cb_start.split("_id_")[1])
    else:
        subcategory_id = int(callback.data.split("_id_")[1])

    cart_item_qty = await db.get_cart_item_qty(subcategory_id, tg_id)

    total_page = (len(cart_item_qty) + page_size - 1) // page_size
    # пример: (11+5-1)//5=3; (10+5-1)//5=2
    offset = (page - 1) * page_size

    await callback.message.delete()
    await send_product_menu(cart_item_qty[offset:offset + page_size],
                            tg_id, state, bot)

    if page < total_page:
        cb_data_up = f"subcategory_id_{subcategory_id}_page_{page + 1}"
    else:
        cb_data_up = "noop"

    if page > 1:
        cb_data_down = f"subcategory_id_{subcategory_id}_page_{page - 1}"
    else:
        cb_data_down = "noop"

    # сообщение с пагинацией и подтверждением выбора
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏪", callback_data=cb_data_down),
         InlineKeyboardButton(text=f"стр. {page} из {total_page}", callback_data="noop"),
         InlineKeyboardButton(text="⏩", callback_data=cb_data_up)],
        [InlineKeyboardButton(text="Подтвердить", callback_data="show_cart")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    text = f'Для продолжения оформления заказа нажмите\n"Подтвердить":'
    await bot.send_message(chat_id=tg_id, text=text, reply_markup=kb)


@router.callback_query(F.data == "category_choice")
async def category_choice(callback: types.CallbackQuery):
    """Обработчик выбора раздела Каталог в главном меню. Вывод категорий"""
    category_kb = await build_category_menu()
    await callback.message.edit_text('Выберете категорию:',
                                     reply_markup=category_kb)


@router.callback_query(F.data.startswith("category_id_"))
async def subcategory_choice(callback: types.CallbackQuery):
    """Обработчик выбора категории. Вывод подкатегорий"""
    category_id = int(callback.data.split("_id_")[1])
    subcategory_kb = await build_category_menu(category_id)
    await callback.message.edit_text('Выберете подкатегорию:',
                                     reply_markup=subcategory_kb)


async def build_category_menu(category_id: int = 0) -> InlineKeyboardMarkup:
    """Сборка кнопок категорий (если задано значение category_id, то подкатегорий"""
    if category_id:
        categories = await db.get_categories(SubCategory, category_id)
        cb_name = 'subcategory_id_'
    else:
        categories = await db.get_categories(Category)
        cb_name = 'category_id_'
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for category in categories:
        button = InlineKeyboardButton(
            text=category.name,
            callback_data=f"{cb_name}{category.id}"
        )
        kb.inline_keyboard.append([button])
    # добавление кнопки возврата в главное меню
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")
    ])
    return kb


@router.callback_query(F.data == "back_to_menu")
async def main_menu(target: types.Message | types.CallbackQuery,
                    state: FSMContext, bot: Bot):
    """Обработчик перехода в главное меню. Вывод главного меню"""
    try:
        tg_id = target.from_user.id
        if isinstance(target, types.Message):
            msg_send = target.answer
        elif isinstance(target, types.CallbackQuery):
            msg_send = target.message.edit_text
        else:
            raise TypeError("Unsupported target type")

        await cache_handling(tg_id, state, bot)

        menu_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Каталог", callback_data="category_choice")],
            [InlineKeyboardButton(text="Корзина", callback_data="show_cart"),
             InlineKeyboardButton(text="Заказы", callback_data="show_orders")],  # add orders
            [InlineKeyboardButton(text="FAQ", callback_data="faq")]
        ])
        text = ("Это магазин. Вы находитесь в главном меню. Чтобы выбрать "
                "товар перейдите в 'Каталог', чтобы оформить покупку перейдите "
                "в 'Корзину', ответы на частые вопросы вы найдете в 'FAQ'")
        await msg_send(text=text, reply_markup=menu_kb)
    except Exception as e:
        logger.error(f'<main_menu>: {e}')


@router.callback_query(F.data == "check_subscription",  # фильтрация callback запросов
                       Form.waiting_for_subscription)  # фильтрации состояний
async def check_subscription(callback: types.CallbackQuery,
                             state: FSMContext, bot: Bot):
    """Обработчик выполнения подписки. Вывод главного меню"""
    tg_id = callback.from_user.id
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, tg_id)
        if member.status in ['left', 'kicked']:
            await callback.answer("Вы все еще не подписаны. "
                                  "Пожалуйста, подпишитесь на канал.")
        else:
            await callback.answer("Добро пожаловать!")
            await main_menu(callback, state, bot)
    except TelegramAPIError as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)


@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext, bot: Bot):
    """
    Обработчик сообщения /start. Добавление нового пользователя в БД
    и проверка подписки на канал
    """
    if not await db.get_user_by_tg_id(message.from_user.id):
        user = User(tg_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name)
        async with db.get_session() as session:  # type: AsyncSession
            session.add(user)

    try:  # проверка подписки на канал
        member = await bot.get_chat_member(CHANNEL_USERNAME, message.from_user.id)
        # не подписан - вывод канала и подтверждения действия
        if member.status in ['left', 'kicked']:
            await state.set_state(Form.waiting_for_subscription)
            subscription_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Перейти в канал",
                                      url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
                [InlineKeyboardButton(text="Я подписался",
                                      callback_data="check_subscription")]
            ])
            await message.answer(
                "Чтобы пользоваться ботом, подпишитесь на канал.",
                reply_markup=subscription_kb
            )
        # подписан - в главное меню
        else:
            await message.answer("Добро пожаловать!")
            await main_menu(message, state, bot)
    except Exception as e:
        logger.error(e)
        await message.answer(f"Не удалось проверить подписку на канал "
                             f"{CHANNEL_USERNAME}.\nПопробуйте /start.")

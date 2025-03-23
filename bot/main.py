import asyncio
import os
from typing import List, Tuple

from aiogram import types, Bot, Dispatcher, Router  # pip install aiogram
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from db import DB
from models import User, Category, SubCategory, Product
from settings import CHANNEL_USERNAME

router = Router()
db = DB()
bot = Bot(token=os.getenv("TG_TOKEN"))


class MainTrack(StatesGroup):
    waiting_for_subscription = State()
    waiting_for_menu_choice = State()


class OrderTrack(StatesGroup):
    waiting_for_category_choice = State()
    waiting_for_subcategory_choice = State()
    waiting_for_product_choice = State()


class CartTrack(StatesGroup):
    waiting_for_cart_view = State()
    waiting_for_delivery_choice = State()
    waiting_for_delivery_info = State()
    waiting_for_payment = State()


class FAQTrack(StatesGroup):
    waiting_for_faq = State()


async def faq(message: types.Message):
    """
    Ответы на частые вопросы ??? в инлайн режиме с автодополнением вопроса

    кнопка назад (главное меню)
    """
    pass


@router.callback_query(lambda c: c.data == 'payment',
                       state=CartTrack.waiting_for_payment)
async def payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Оплата успешно выполнена!", show_alert=True)


@router.callback_query(lambda c: c.data == "create_order",
                       state=CartTrack.waiting_for_delivery_choice)
@router.message(state=CartTrack.waiting_for_delivery_info)
async def create_order(target: types.Message | types.CallbackQuery,
                       state: FSMContext):
    """Обработчик создания заказа. Отправка способа оплаты"""
    await state.set_state(CartTrack.waiting_for_payment)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить", callback_data="make_payment")],
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    text = "Ваш заказ готов к оплате.\nНажмите 'Оплатить' для завершения."
    if isinstance(target, types.Message):
        delivery_address = f'Доставка. Адрес: {target.text.strip()}'
        await target.answer(text, reply_markup=kb)
    elif isinstance(target, types.CallbackQuery):
        delivery_address = 'Самовывоз'
        await target.message.edit_text(text, reply_markup=kb)
        await target.answer()
    else:
        raise TypeError("Unsupported target type")
    user_id = target.from_user.id
    await db.create_order_db(user_id, delivery_address)


# @router.callback_query(lambda c: c.data == 'handle_self_delivery',
#                        state=CartTrack.waiting_for_delivery_choice)
# async def handle_self_delivery(callback: types.CallbackQuery, state: FSMContext):
#     """Обработчик для самовывоза – переход к оплате напрямую"""
#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Оплатить", callback_data="payment")],
#         [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
#     ])
#     # Редактируем текущее сообщение или отправляем новое с сообщением об оплате
#     text = "Ваш заказ готов к оплате.\nНажмите 'Оплатить' для завершения."
#     await callback.message.edit_text(text=text, reply_markup=kb)
#     await state.set_state(CartTrack.waiting_for_payment)
#     await callback.answer()
#
#
# @router.message(state=CartTrack.waiting_for_delivery_info)
# async def handle_delivery_address(message: types.Message, state: FSMContext):
#     """Обработчик текстового ввода адреса доставки"""
#     delivery_address = message.text.strip()
#
#     # Переходим в оплату – отправляем сообщение с кнопками "Оплатить" и "Главное меню"
#     kb = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Оплатить", callback_data="payment")],
#         [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
#     ])
#     await bot.send_message(
#         chat_id=message.chat.id,
#         text="Ваш заказ готов к оплате.\nНажмите 'Оплатить' для завершения.",
#         reply_markup=kb
#     )
#     await state.set_state(CartTrack.waiting_for_payment)


@router.callback_query(lambda c: c.data == 'delivery_info',
                       state=CartTrack.waiting_for_delivery_choice)
async def delivery_info(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик доставки. Запрос адреса у пользователя"""
    await state.set_state(CartTrack.waiting_for_delivery_info)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    text = 'Введите адрес доставки в формате: Город, Улица, Дом, Квартира'
    await callback.message.edit_text(text=text, reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == 'send_delivery_choice',
                       state=CartTrack.waiting_for_cart_view)
async def send_delivery_choice(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик подтверждения заказа. Отправка выбора способа доставки"""
    await cache_handling(callback.message.message_id,
                         callback.from_user.id, state)
    await state.set_state(CartTrack.waiting_for_delivery_choice)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Самовывоз', callback_data='create_order'),
         InlineKeyboardButton(text='Доставка до адреса', callback_data='delivery_info')]
        ,
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    # Отправка нового сообщения с выбором доставки
    await bot.send_message(
        chat_id=callback.from_user.id,
        text=f'Выберите способ доставки:',
        reply_markup=kb
    )
    await callback.answer()


async def cart_view(user_id: int, state: FSMContext):
    """Вывод корзины, вид как при выборе товаров"""
    cart_item_with_quantities = await db.get_cart_items_with_quantities(user_id)
    await send_product_menu(cart_item_with_quantities, user_id, state)
    text = 'Выбрать способ доставки'
    await send_confirmation(text, 'send_delivery_choice',
                            user_id, state)


async def cache_handling(chat_id, user_id, state: FSMContext):
    """Сохранение в БД и удаление сообщений"""
    state_data = await state.get_data()
    messages_cache = state_data.get("messages_cache", [])
    # сохранение количества товара из кеша в бд
    if messages_cache:
        await db.save_current_quantity_in_cart(user_id, messages_cache)
    # удаление сообщений с товарами
    for message_id, _, _ in messages_cache:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    # удаление сообщения с подтверждением
    confirmation_msg_id = state_data.get("confirmation_cache")
    if confirmation_msg_id is not None:
        await bot.delete_message(chat_id=chat_id, message_id=confirmation_msg_id)
    await state.clear()


@router.callback_query(lambda c: c.data == 'send_confirmation_product_choice',
                       state=OrderTrack.waiting_for_product_choice)
async def send_confirmation_product_choice(callback: types.CallbackQuery,
                                           state: FSMContext):
    """Обработчик подтверждения выбора продуктов. Вывод корзины"""
    await cache_handling(callback.message.message_id,
                         callback.from_user.id, state)
    await state.set_state(CartTrack.waiting_for_cart_view)
    # вывод корзины
    await cart_view(callback.from_user.id, state)


async def build_quantity_kb(product_id: int, quantity: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="–", callback_data=f"decrease_{product_id}"),
         InlineKeyboardButton(text=f"В корзине: {quantity}", callback_data="noop"),
         InlineKeyboardButton(text="+", callback_data=f"increase_{product_id}")]
    ])


@router.callback_query(lambda c: c.data and c.data.startswith(
    ("increase_", "decrease_")), state="*")
async def handle_quantity_change(callback: types.CallbackQuery,
                                 state: FSMContext):
    """Обработчик кнопок изменения количества продукта"""
    data = callback.data
    # получение действия и идентификатора продукта
    action, product_id_str = data.split("_", 1)
    product_id = int(product_id_str)

    # получение количества продукта
    state_data = await state.get_data()
    messages_cache = state_data.get("messages_cache", [])
    iterator = iter([items[2] for items in messages_cache
                    if items[0] == callback.message.message_id])
    quantity = next(iterator, 0)

    # Изменение количества продукта в корзине
    if action == "increase":
        quantity += 1
    elif action == "decrease" and quantity > 0:
        quantity -= 1

    # обновление кеша
    new_messages_cache = []
    for msg_id, product_id, qty in messages_cache:
        if msg_id == callback.message.message_id:
            new_messages_cache.append((msg_id, product_id, quantity))
        else:
            new_messages_cache.append((msg_id, product_id, qty))
    await state.update_data(messages_cache=new_messages_cache)

    # Формирование новой клавиатуры с обновленным количеством:
    kb = await build_quantity_kb(product_id, quantity)
    # Редактирование клавиатуры в текущем сообщении, чтобы отобразить новое количество
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()  # Подтверждаем callback (убираем "часики")


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


async def send_confirmation(text: str, callback_data: str,
                            user_id: int, state: FSMContext):
    """Отправка сообщения с подтверждением выбора товаров в подкатегории"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback_data),
         InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    sent_message = await bot.send_message(
        chat_id=user_id,
        text=f'Для продолжения оформления заказа нажмите "{text}":',
        reply_markup=kb
    )
    # кеширование идентификатора сообщения для дальнейшего удаления
    await state.update_data(confirmation_cache=sent_message.message_id)


async def send_product_menu(products_with_qty: List[Tuple[Product, int]],
                            user_id: int, state: FSMContext):
    """Отправка отдельных сообщений с продуктами"""
    for product, quantity in products_with_qty:
        # формирование инлайн кнопок
        kb = await build_quantity_kb(product.id, quantity)
        # отправка сообщения
        sent_message = await bot.send_photo(
            chat_id=user_id,
            photo=product.image_url,
            caption=f"{product.name}\n{product.description}\nЦена: {product.price}",
            reply_markup=kb
        )
        await save_message_cache(state, sent_message.message_id,
                                 product.id, quantity)


@router.callback_query(lambda c: c.data and c.data.startswith("subcategory_"),
                       state=OrderTrack.waiting_for_subcategory_choice)
async def product_choice(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора подкатегории. Вывод товаров"""
    await callback.message.delete()
    subcategory_id = int(callback.data.split("_", 1)[1])
    await state.set_state(OrderTrack.waiting_for_product_choice)
    products_with_qty = await db.get_products_with_quantities(
        subcategory_id, callback.from_user.id
    )
    await send_product_menu(products_with_qty, callback.from_user.id, state)
    await send_confirmation("Подтвердить", "send_confirmation_product_choice",
                            callback.from_user.id, state)


@router.callback_query(lambda c: c.data and c.data.startswith("category_"),
                       state=OrderTrack.waiting_for_category_choice)
# если c.data is None, то startswith приведет к ошибке
async def subcategory_choice(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора категории. Вывод подкатегорий"""
    category_id = int(callback.data.split("_", 1)[1])
    subcategory_kb = await build_category_menu(category_id)
    await state.set_state(OrderTrack.waiting_for_subcategory_choice)
    await callback.message.edit_text('Выберете подкатегорию:',
                                     reply_markup=subcategory_kb)


async def build_category_menu(category_id: int = 0) -> InlineKeyboardMarkup:
    """Сборка кнопок категорий (если задано значение category_id, то подкатегорий"""
    current_category = SubCategory if category_id else Category
    categories = await db.get_categories(current_category)

    kb_data_startswith = 'subcategory_' if category_id else 'category_'
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for category in categories:
        button = InlineKeyboardButton(
            text=category.name,
            callback_data=f"{kb_data_startswith}{category.id}"
        )
        kb.inline_keyboard.append([button])
    # добавление кнопки возврата в главное меню
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")
    ])
    return kb


@router.callback_query(lambda c: c.data == "category_choice",
                       state=MainTrack.waiting_for_menu_choice)
async def category_choice(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора раздела Каталог в главном меню. Вывод категорий"""
    category_kb = await build_category_menu()
    await state.set_state(OrderTrack.waiting_for_category_choice)
    await callback.message.edit_text('Выберете категорию:',
                                     reply_markup=category_kb)


@router.callback_query(lambda c: c.data == "back_to_menu")
async def send_main_menu(target: types.Message | types.CallbackQuery,
                         state: FSMContext):
    """Обработчик перехода в главное меню. Вывод главного меню"""
    if isinstance(target, types.Message):
        msg = target
        msg_send = msg.answer
    elif isinstance(target, types.CallbackQuery):
        msg = target.message
        msg_send = msg.edit_text
    else:
        raise TypeError("Unsupported target type")

    await cache_handling(msg.message_id, msg.from_user.id, state)
    await state.set_state(MainTrack.waiting_for_menu_choice)

    menu_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Каталог", callback_data="category_choice")],
        [InlineKeyboardButton(text="Корзина", callback_data="menu_cart")],
        [InlineKeyboardButton(text="FAQ", callback_data="menu_faq")]
    ])
    text = "Главное меню"
    await msg_send(text=text, reply_markup=menu_kb)


@router.callback_query(lambda c: c.data == "check_subscription",  # фильтрация callback запросов
                       state=MainTrack.waiting_for_subscription)  # фильтрации состояний
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выполнения подписки. Вывод главного меню"""
    user_id = callback.from_user.id
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['left', 'kicked']:
            await callback.answer(
                "Вы все еще не подписаны. Пожалуйста, подпишитесь на канал.",
                show_alert=True
            )
        else:
            await callback.answer("Добро пожаловать!")
            await send_main_menu(callback, state)
    except:
        await callback.answer("Ошибка проверки подписки.",
                              show_alert=True)


@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    """
    Обработчик сообщения /start. Добавление нового пользователя в БД
    и проверка подписки на канал
    """
    user = User(tg_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name)
    async with db.get_session() as session:  # type: AsyncSession
        session.add(user)
    try:  # проверка подписки на канал
        member = await bot.get_chat_member(CHANNEL_USERNAME, user.tg_id)
        # не подписан - вывод канала и подтверждения действия
        if member.status in ['left', 'kicked']:
            await state.set_state(MainTrack.waiting_for_subscription)
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
            await send_main_menu(message, state)
    except:
        await message.answer(f"Не удалось проверить подписку на канал "
                             f"{CHANNEL_USERNAME}.\nПопробуйте /start.")


async def main():
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot, timeout=30)
    # режим polling возвращает ответ при поступлении сообщения или через timeout


if __name__ == "__main__":
    asyncio.run(main())

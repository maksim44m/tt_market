from typing import List, Tuple

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (InlineKeyboardMarkup,
                           CallbackQuery)

from models import Category, SubCategory, Product
from settings import logger
from bot_worker.util.helpers import (cache_handling,
                                     kb_builder,
                                     save_message_cache)
from db import DB


class ProductWorker:
    def __init__(self, db: DB):
        self.db = db

    async def build_category_menu(self, category_id: int = 0) -> InlineKeyboardMarkup:
        """Сборка кнопок категорий (если задано значение category_id, то подкатегорий"""
        if category_id:
            categories = await self.db.get_categories(SubCategory, category_id)
            cb_name = 'subcategory_id_'
        else:
            categories = await self.db.get_categories(Category)
            cb_name = 'category_id_'
        kb_values = []
        for category in categories:
            button = {"text": category.name,
                      "callback_data": f"{cb_name}{category.id}"}
            kb_values.append([button])
        # добавление кнопки возврата в главное меню
        kb_values.append([
            {"text": "Главное меню", "callback_data": "back_to_menu"}
        ])
        return await kb_builder(kb_values=kb_values)

    async def category_choice(self, callback: CallbackQuery) -> None:
        """Вывод категорий"""
        category_kb = await self.build_category_menu()
        await callback.message.edit_text('Выберете категорию:',
                                         reply_markup=category_kb)

    async def subcategory_choice(self, callback: CallbackQuery) -> None:
        """Вывод подкатегорий"""
        category_id = int(callback.data.split("_id_")[1])
        subcategory_kb = await self.build_category_menu(category_id)
        await callback.message.edit_text('Выберете подкатегорию:',
                                         reply_markup=subcategory_kb)

    async def product_choice(self,
                             callback: CallbackQuery,
                             state: FSMContext,
                             bot: Bot) -> None:
        """Вывод товаров"""
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

        cart_item_qty = await self.db.get_cart_item_qty(subcategory_id, tg_id)

        total_page = (len(cart_item_qty) + page_size - 1) // page_size
        # пример: (11+5-1)//5=3; (10+5-1)//5=2
        offset = (page - 1) * page_size

        try:
            await callback.message.delete()
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение: {e}")
        await self.send_product_menu(cart_item_qty[offset:offset + page_size],
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
        kb = await kb_builder(kb_values=[
            [{"text": "⏪", "callback_data": cb_data_down},
             {"text": f"стр. {page} из {total_page}", "callback_data": "noop"},
             {"text": "⏩", "callback_data": cb_data_up}],
            [{"text": "Подтвердить", "callback_data": "show_cart"}],
            [{"text": "Главное меню", "callback_data": "back_to_menu"}]
        ])
        text = f'Для продолжения оформления заказа нажмите\n"Подтвердить":'
        await bot.send_message(chat_id=tg_id, text=text, reply_markup=kb)

    @staticmethod
    async def build_quantity_kb(product_id: int,
                                quantity: int) -> InlineKeyboardMarkup:
        return await kb_builder(kb_values=[
            [{"text": "–", "callback_data": f"decrease_{product_id}"},
             {"text": f"{quantity}", "callback_data": "noop"},
             {"text": "+", "callback_data": f"increase_{product_id}"}]
        ])

    async def send_product_menu(self,
                                products_with_qty: List[Tuple[Product, int]],
                                tg_id: int,
                                state: FSMContext,
                                bot: Bot) -> None:
        """Отправка отдельных сообщений с продуктами"""
        await cache_handling(tg_id, state, bot, self.db)
        for product, quantity in products_with_qty:
            # формирование инлайн кнопок
            kb = await self.build_quantity_kb(product.id, quantity)
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

    async def quantity_change(self,
                              callback: CallbackQuery,
                              state: FSMContext) -> None:
        """Изменение количества продукта"""
        # получение действия и идентификатора продукта
        action, product_id = callback.data.split("_")

        # получение количества продукта
        state_data = await state.get_data()
        messages_cache = state_data.get("messages_cache", [])
        # logger.info(f'handle_quantity_change: {messages_cache=}')

        # Сохранение предыдущего количества для проверки
        quantity = next(
            (qty for msg_id, pid, qty in messages_cache if msg_id ==
             callback.message.message_id and pid == int(product_id)), 0
        )
        # logger.info(f'handle_quantity_change: {quantity=}')

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
        # logger.info(f'handle_quantity_change: {new_messages_cache=}')
        await state.update_data(messages_cache=new_messages_cache)

        try:
            logger.info(f'handle_quantity_change: {quantity=}')
            kb = await self.build_quantity_kb(product_id, quantity)
            await callback.message.edit_reply_markup(reply_markup=kb)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise

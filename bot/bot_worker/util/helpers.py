from typing import List

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import (InlineKeyboardMarkup, 
                           InlineKeyboardButton)

from settings import logger
from db import DB

async def save_message_cache(state: FSMContext, 
                             message_id: int,
                             product_id: int, 
                             quantity: int = 0) -> None:
    """
    Кеширование данных в state.get_data() в виде:
    {'messages_cache': [(message_id, product_id, quantity), ]}
    """
    # Сохранение идентификатора сообщения в state
    data = await state.get_data()
    messages_cache = data.get("messages_cache", [])  # для первой итерации
    messages_cache.append((message_id, product_id, quantity))
    await state.update_data(messages_cache=messages_cache)


async def cache_handling(tg_id: int, 
                         state: FSMContext, 
                         bot: Bot,
                         db: DB) -> None:
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
    

async def kb_builder(kb_values: List[List[dict]]) -> InlineKeyboardMarkup:
    """
    dict:
     *,
     text: str,
     url: str | None = None,
     callback_data: str | None = None,
     web_app: WebAppInfo | None = None,
     login_url: LoginUrl | None = None,
     switch_inline_query: str | None = None,
     switch_inline_query_current_chat: str | None = None,
     switch_inline_query_chosen_chat: SwitchInlineQueryChosenChat | None = None,
     copy_text: CopyTextButton | None = None,
     callback_game: CallbackGame | None = None,
     pay: bool | None = None,
     **__pydantic_kwargs: Any
    """
    inline_keyboard = []
    for values in kb_values:
        line_buttons = []
        for value in values:
            line_buttons.append(InlineKeyboardButton(**value))
        inline_keyboard.append(line_buttons)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
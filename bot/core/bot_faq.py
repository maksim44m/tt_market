from aiogram import F, Router
from aiogram import types
from aiogram.types import (InlineQueryResultArticle,
                           InputTextMessageContent,
                           InlineKeyboardButton,
                           InlineKeyboardMarkup)
from aiogram.fsm.context import FSMContext
import uuid

from settings import logger


router = Router()


@router.callback_query(F.data == "faq")
async def faq(callback: types.CallbackQuery, state: FSMContext):
    faq_data = await search_faq('')
    text = "\n\n".join([
        f"**Вопрос:** {faq['question']}\n**Ответ:** {faq['answer']}"
        for faq in faq_data
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


async def search_faq(query: str) -> list:
    # Для демонстрации:
    faqs = [
        {"id": 1,
         "question": "Как оплатить заказ?",
         "answer": "Вы можете оплатить заказ онлайн через платежную систему."},
        {"id": 2,
         "question": "Как оформить доставку?",
         "answer": "Доставка осуществляется по адресу, указанному при оформлении заказа."},
        {"id": 3,
         "question": "Где я могу найти FAQ?",
         "answer": "Часто задаваемые вопросы вы найдете здесь."},
    ]
    if query:
        # Фильтрация по вхождению query в вопрос (регистр можно привести к нижнему)
        return [faq for faq in faqs if query.lower() in faq["question"].lower()]
    else:
        return faqs


@router.inline_query()
async def inline_faq_handler(inline_query: types.InlineQuery):
    try:
        query_text = inline_query.query.strip()
        results = []

        # Если текст пустой, можно вернуть подсказку
        if not query_text:
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="Введите вопрос для поиска в FAQ",
                    input_message_content=InputTextMessageContent(
                        message_text="Попробуйте ввести ключевые слова вопроса."
                    ),
                    description="Например: Как оплатить заказ?"
                )
            )
        else:
            # Ищем FAQ по введённому запросу
            faq_items = await search_faq(query_text)
            if not faq_items:
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid.uuid4()),
                        title="Ничего не найдено",
                        input_message_content=InputTextMessageContent(
                            message_text="К сожалению, ничего не найдено."
                        ),
                        description="Попробуйте изменить запрос."
                    )
                )
            else:
                for faq in faq_items:
                    results.append(
                        InlineQueryResultArticle(
                            id=str(uuid.uuid4()),
                            title=faq["question"],
                            input_message_content=InputTextMessageContent(
                                message_text=f"**Вопрос:** {faq['question']}\n\n**Ответ:** {faq['answer']}",
                                parse_mode="Markdown"
                            ),
                            description=faq["answer"][:100]  # первые 100 символов ответа
                        )
                    )

        await inline_query.answer(results, cache_time=1)
    except Exception as e:
        logger.error(f'inline_faq_handler {e}')

import asyncio
from typing import Tuple

from pydantic import BaseModel

from settings import db, bot, logger


class BroadcastRequest(BaseModel):
    message: str


async def broadcast_message(message_text: str) -> Tuple[str, list]:
    tg_ids = await db.get_all_tg_ids()
    count = 0
    errors = []
    for tg_id in tg_ids:
        try:
            await bot.send_message(tg_id, message_text)
            # 30 сообщений в секунду для ботов — частота запросов к API
            # 1 сообщение в секунду - частота отправки сообщений одному пользователю
            count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            err_msg = f"Ошибка отправки пользователю {tg_id}: {e}"
            logger.error(err_msg)
            errors.append(err_msg)
    return ((f'Рассылка выполнена.\n'
             f'Отправлено сообщений: {count}\n'
             f'Ошибок отправки: {len(errors)}'),
            errors)
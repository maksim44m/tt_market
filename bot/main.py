import asyncio

from aiogram import Dispatcher  # pip install aiogram

from core import bot_main, bot_pay, bot_faq, bot_api
from settings import bot

dp = Dispatcher()
dp.include_routers(bot_main.router,
                   bot_pay.router,
                   bot_faq.router)


async def run_uvicorn():
    """Создание и запуск сервера для вызова в цикле событий"""
    import uvicorn
    config = uvicorn.Config(app=bot_api.app,
                            host="0.0.0.0",
                            port=8001,
                            reload=False,
                            log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_tg_dispatcher():
    await dp.start_polling(bot, timeout=30)


async def main():
    # await db.seed_db()

    uvi_task = asyncio.create_task(run_uvicorn())
    dp_task = asyncio.create_task(run_tg_dispatcher())
    await asyncio.gather(uvi_task, dp_task)
    # режим polling возвращает ответ при поступлении сообщения или через timeout


if __name__ == "__main__":
    asyncio.run(main())

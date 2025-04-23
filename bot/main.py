import asyncio

from aiogram import Dispatcher  # pip install aiogram

from bot_worker import (start_menu, 
                        products,
                        cart, 
                        orders, 
                        payments, 
                        faq)
from bot_api import broadcast
from settings import bot  # , db

dp = Dispatcher()
dp.include_routers(start_menu.router,
                   products.router,
                   cart.router,
                   payments.router,
                   orders.router,
                   faq.router)


async def run_uvicorn():
    """Создание и запуск сервера для вызова в цикле событий"""
    import uvicorn
    config = uvicorn.Config(app=broadcast.app,
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

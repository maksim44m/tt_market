import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Tuple, Union, Type

from sqlalchemy import select, literal, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker  # pip install SQLAlchemy asyncpg

from bot.models import CartItem, Cart, Product, Category, SubCategory, Order, OrderItem


class DB:
    def __init__(self):
        self.engine = create_async_engine(os.getenv('DB_URL'), echo=False, future=True)

        self.SessionLocal = sessionmaker(bind=self.engine,  # type: ignore
                                         class_=AsyncSession,
                                         autoflush=False,
                                         future=True,
                                         expire_on_commit=False)

    @asynccontextmanager  # для создания
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """
        Асинхронный генератор сессий. Работает как контекстный менеджер
        благодаря @asynccontextmanager.
        """
        async with self.SessionLocal() as session:  # type: AsyncSession
            async with session.begin():
                try:
                    yield session
                except Exception as e:
                    await session.rollback()
                    raise e

    async def get_categories(  # Type - чтобы передавать класс, а не объект
            self, current_category: Type[Union[SubCategory, Category]]
    ) -> List[Union[Category, SubCategory]]:
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(select(current_category))
            return list(result.scalars().all())

    async def get_product_quantity(self, user_id: int, product_id: int) -> int:
        async with self.SessionLocal() as session:  # type: AsyncSession
            result = await session.execute(
                select(CartItem.quantity)
                .join(Cart)
                .where(Cart.user_id == literal(user_id),
                       CartItem.product_id == literal(product_id))
            )
            quantity = result.scalar()
        return quantity if quantity is not None else 0

    async def get_all_products_in_subcategory(
            self, subcategory_id: int
    ) -> List[Product]:
        async with self.SessionLocal() as session:  # type: AsyncSession
            result = await session.execute(
                select(Product).where(
                    Product.subcategory_id == literal(subcategory_id))
            )
            return list(result.scalars().all())

    async def get_products_with_quantities(
            self, subcategory_id: int, user_id: int
    ) -> List[Tuple[Product, int]]:
        async with self.get_session() as session:
            result = await session.execute(
                select(Product, CartItem.quantity)
                .outerjoin(CartItem,
                           and_(CartItem.product_id == Product.id,
                                CartItem.cart.has(Cart.user_id == user_id)))
                .where(Product.subcategory_id == literal(subcategory_id))
            )
            rows = result.all()

            return [(product, quantity if quantity is not None else 0)
                    for product, quantity in rows]

    async def get_cart_items_with_quantities(
            self, user_id: int
    ) -> List[Tuple[Product, int]]:
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(
                select(Product, CartItem.quantity)
                .join(CartItem, Product.id == CartItem.product_id)
                .join(Cart, Cart.id == CartItem.cart_id)
                .where(Cart.user_id == literal(user_id))
            )
            return [(row[0], row[1]) for row in result.all()]

    async def save_current_quantity_in_cart(
            self, user_id: int, items: List[Tuple[int, int, int]],
    ):
        async with self.get_session() as session:  # type: AsyncSession
            # Получение корзины пользователя
            result = await session.execute(
                select(Cart).where(Cart.user_id == literal(user_id))
            )
            cart = result.scalars().first()
            if not cart:
                cart = Cart(user_id=user_id)  # Если корзины нет, создание корзины
                session.add(cart)
                await session.flush()  # чтобы получить cart.id

            for _, product_id, new_quantity in items:
                # Поиск существующего CartItem для данного продукта в корзине
                result = await session.execute(
                    select(CartItem).where(
                        CartItem.cart_id == literal(cart.id),
                        CartItem.product_id == literal(product_id)
                    )
                )
                cart_item = result.scalars().first()
                if cart_item:
                    cart_item.quantity = new_quantity  # Обновление количества
                else:  # Если элемента нет, создание нового
                    cart_item = CartItem(cart_id=cart.id, product_id=product_id, quantity=new_quantity)
                    session.add(cart_item)

    async def create_order_db(self, user_id: int, delivery_info: str):
        async with self.get_session() as session:  # type: AsyncSession
            # Получаем корзину пользователя
            result = await session.execute(
                select(Cart).where(Cart.user_id == literal(user_id))
            )
            cart = result.scalars().first()
            if not cart:
                raise Exception('Корзина пуста')

            # Создаем новый заказ. Допустим, в модели Order есть поле delivery_address.
            order = Order(user_id=user_id, status="Новый", delivery=delivery_info)
            session.add(order)
            await session.flush()  # чтобы получить order.id до создания OrderItem

            # Перебираем все элементы корзины и создаем для каждого заказанный товар
            for cart_item in cart.cartitems:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=cart_item.product_id,
                    quantity=cart_item.quantity
                )
                session.add(order_item)

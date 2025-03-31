import os
from contextlib import asynccontextmanager
import random
from typing import AsyncIterator, List, Tuple, Union, Type, Optional

from sqlalchemy import select, literal, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, selectinload  # pip install SQLAlchemy psycopg2-binary

from settings import logger

from models import (CartItem, Cart, Product, Category, SubCategory,
                    Order, OrderItem, User, OrderStatus)


class DB:
    def __init__(self):
        self.engine = create_async_engine(os.getenv('DB_URL'),
                                          echo=True, future=True)

        self.SessionLocal = sessionmaker(bind=self.engine,  # type: ignore
                                         class_=AsyncSession,
                                         autoflush=False,
                                         future=True,
                                         expire_on_commit=False)

    @asynccontextmanager  # для создания контекстного менеджера
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

    async def get_user_by_tg_id(self, tg_id: int) -> Optional[User]:
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(
                select(User).where(User.tg_id == literal(tg_id))
            )
            return result.scalars().first()

    async def get_categories(
            self,  # Type - чтобы передавать класс, а не объект
            current_category: Type[Union[SubCategory, Category]],
            category_id: Optional[int] = None
    ) -> List[Union[Category, SubCategory]]:
        async with self.get_session() as session:  # type: AsyncSession
            query = select(current_category)
            # Если передан category_id и ищем подкатегории, добавляем фильтр
            if category_id is not None and current_category == SubCategory:
                query = query.where(SubCategory.category_id == literal(category_id))
            result = await session.execute(query)
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
            self, subcategory_id: int, tg_id: int
    ) -> List[Tuple[Product, int]]:
        async with self.get_session() as session:
            result = await session.execute(
                select(Product, CartItem.quantity)
                .outerjoin(
                    CartItem,
                    and_(
                        CartItem.product_id == Product.id,
                        CartItem.cart.has(
                            Cart.user.has(User.tg_id == literal(tg_id))
                        )
                    )
                )
                .where(Product.subcategory_id == literal(subcategory_id))
            )
            rows = result.all()

            return [(product, quantity if quantity is not None else 0)
                    for product, quantity in rows]

    async def get_cart_items_with_quantities(
            self, tg_id: int
    ) -> List[Tuple[Product, int]]:
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(
                select(Product, CartItem.quantity)
                .join(CartItem, Product.id == CartItem.product_id)
                .join(Cart, Cart.id == CartItem.cart_id)
                .join(User)
                .where(User.tg_id == literal(tg_id))
            )
            return [(row[0], row[1]) for row in result.all()]

    async def save_current_quantity_in_cart(
            self, tg_id: int, items: List[Tuple[int, int, int]],  # (message_id, product_id, quantity)
    ):
        async with self.get_session() as session:  # type: AsyncSession
            user = await self.get_user_by_tg_id(tg_id)
            # Получение корзины пользователя
            result = await session.execute(
                select(Cart).where(Cart.user_id == literal(user.id))
            )
            # Если корзины нет, создание корзины
            cart = result.scalars().first()
            if not cart:
                cart = Cart(user_id=user.id)
                session.add(cart)
                await session.flush()  # чтобы получить cart.id
            # Поиск существующего CartItem для данного продукта в корзине
            try:
                for _, product_id, new_quantity in items:
                    result = await session.execute(
                        select(CartItem).where(
                            CartItem.cart_id == literal(cart.id),
                            CartItem.product_id == literal(product_id)
                        )
                    )
                    cart_item = result.scalars().first()
                    if new_quantity:
                        if cart_item:
                            cart_item.quantity = new_quantity
                        else:  # Если элемента нет, создание нового
                            cart_item = CartItem(cart_id=cart.id,
                                                 product_id=product_id,
                                                 quantity=new_quantity)
                            session.add(cart_item)
                    else:
                        if cart_item:
                            await session.delete(cart_item)
            except Exception as e:
                logger.error(f'Error save_current_quantity_in_cart (for): {e}')

    async def create_order_db(self, tg_id: int, delivery_info: str) -> int:
        async with self.get_session() as session:  # type: AsyncSession
            # Получение корзины пользователя с загрузкой связанных элементов (cartitems)
            result = await session.execute(
                select(Cart)
                .options(selectinload(Cart.cartitems),
                         selectinload(Cart.user))
                .join(User)
                .where(User.tg_id == literal(tg_id))
            )
            cart = result.scalars().first()
            if not cart:
                raise Exception("Корзина пуста")

            # Создание нового заказа
            order = Order(user_id=cart.user.id, status=OrderStatus.NOT_PAID,
                          delivery=delivery_info)
            session.add(order)
            await session.flush()  # чтобы получить order.id до создания OrderItem

            # Перебираем все элементы корзины и создаем для каждого заказанный товар
            for cart_item in cart.cartitems:
                order_item = OrderItem(order_id=order.id,
                                       product_id=cart_item.product_id,
                                       quantity=cart_item.quantity)
                session.add(order_item)
                await session.delete(cart_item)  # удаление из корзины
            return order.id

    async def get_orders_by_user(self, tg_id: int) -> list[Order]:
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(
                select(Order)
                .join(User, Order.user_id == User.id)
                .where(User.tg_id == literal(tg_id))
            )
            orders = result.scalars().all()
            return list(orders)

    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(
                select(Order).where(Order.id == literal(order_id))
            )
            return result.scalars().first()

    async def delete_order(self, order_id: int):
        async with self.get_session() as session:  # type: AsyncSession
            order = await session.get(Order, order_id, options=[selectinload(Order.orderitems)])
            if order:
                await session.delete(order)

    async def set_order_status(self, order_id: int, status: OrderStatus):
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(
                select(Order).where(Order.id == literal(order_id))
            )
            order = result.scalars().first()
            if order:
                order.status = status

    async def set_order_payment_id(self, order_id: int, payment_id: str):
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(
                select(Order).where(Order.id == literal(order_id))
            )
            order = result.scalars().first()
            if order:
                order.payment_id = payment_id

    async def get_order_sum(self, order_id: int) -> Tuple[int, Order]:
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(
                select(Order)
                .options(selectinload(Order.orderitems)
                         .selectinload(OrderItem.products))
                .where(Order.id == literal(order_id))
            )
            order = result.scalars().first()
        if not order:
            return 0, order
        total = sum(item.products.price * item.quantity for item in order.orderitems)
        return total, order

    async def get_all_tg_ids(self) -> list[int]:
        async with self.get_session() as session:  # type: AsyncSession
            result = await session.execute(select(User.tg_id))
            return list(result.scalars().all())

    async def seed_db(self):
        try:
            async with self.get_session() as session:  # type: AsyncSession
                for cat_num in range(1, 6):
                    # Создаем категорию
                    category = Category(name=f"Категория {cat_num}")
                    session.add(category)
                    await session.flush()  # чтобы получить category.id

                    for subcat_num in range(1, 4):
                        # Создаем подкатегорию, привязанную к категории
                        subcategory = SubCategory(
                            name=f"Подкатегория {cat_num}-{subcat_num}",
                            category_id=category.id
                        )
                        session.add(subcategory)
                        await session.flush()  # чтобы получить subcategory.id

                        # Генерируем случайное количество товаров от 5 до 10
                        num_products = random.randint(5, 10)
                        for prod_num in range(1, num_products + 1):
                            product = Product(
                                name=f"Товар {cat_num}-{subcat_num}-{prod_num}",
                                description=f"Описание товара {cat_num}-{subcat_num}-{prod_num}",
                                price=round(random.uniform(10, 100), 2),
                                category_id=category.id,
                                subcategory_id=subcategory.id,
                                image_url="https://via.placeholder.com/150"  # тестовый URL для изображения
                            )
                            session.add(product)
                print("Database seeded successfully!")
        except Exception as e:
            print("Error seeding database:", e)

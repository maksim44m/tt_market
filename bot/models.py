from sqlalchemy import (Column, BigInteger, String, Integer,
                        ForeignKey, Text, DECIMAL, text, CheckConstraint)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# задать __tablename__ в каждой модели соответствующее имени модели Джанго
# {app_label}_{model_class_name_in_lowercase}, например users_user


class User(Base):
    __tablename__ = 'users_user'
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    username = Column(String(length=32), nullable=True)

    # Связь один к одному с корзиной: uselist=False говорит, что это один объект, а не список.
    cart = relationship('Cart', back_populates='user', uselist=False,
                        cascade="all, delete-orphan", passive_deletes=True)
    orders = relationship('Order', back_populates='user',
                          cascade="all, delete-orphan", passive_deletes=True)


class Cart(Base):
    __tablename__ = 'users_cart'
    id = Column(Integer, primary_key=True)
    # unique=True, чтобы гарантировать один к одному
    user_id = Column(
        Integer,
        ForeignKey('users_user.id', ondelete='CASCADE'),
        unique=True,
        nullable=False
    )

    user = relationship("User", back_populates='cart')
    cartitems = relationship("CartItem", back_populates='cart',
                             cascade="all, delete-orphan", passive_deletes=True)


class CartItem(Base):
    __tablename__ = 'users_cartitem'
    id = Column(Integer, primary_key=True)
    cart_id = Column(
        Integer,
        ForeignKey('users_cart.id', ondelete='CASCADE'),
        nullable=False
    )
    product_id = Column(
        Integer,
        ForeignKey('products_product.id', ondelete='CASCADE'),
        nullable=False
    )
    quantity = Column(Integer, default=1, nullable=False)

    cart = relationship("Cart", back_populates='cartitems')
    product = relationship("Product")


class Category(Base):
    __tablename__ = 'products_category'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=255), nullable=False)

    products = relationship("Product", back_populates='category')
    subcategories = relationship("SubCategory", back_populates='category')


class SubCategory(Base):
    __tablename__ = 'products_subcategory'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=255), nullable=False)
    category_id = Column(
        Integer,
        ForeignKey('products_category.id', ondelete='CASCADE'),
        nullable=False
    )

    category = relationship("Category", back_populates='subcategories')
    products = relationship("Product", back_populates='subcategory')


class Product(Base):
    __tablename__ = 'products_product'
    id = Column(Integer, primary_key=True)
    category_id = Column(
        Integer,
        ForeignKey('products_category.id', ondelete='CASCADE'),
        nullable=False
    )
    subcategory_id = Column(
        Integer,
        ForeignKey('products_subcategory.id', ondelete='CASCADE'),
        nullable=False
    )
    name = Column(String(length=255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    image_url = Column(String, nullable=True)

    category = relationship("Category", back_populates='products')
    cartitems = relationship('CartItem', back_populates='product')
    orderitems = relationship('OrderItem', back_populates='products')
    subcategory = relationship("SubCategory", back_populates='products')


class OrderStatus:
    NOT_PAID: str = 'Не оплачен'
    PAID: str = 'Оплачен'
    COMPLETED: str = 'Выполнен'


class Order(Base):
    __tablename__ = 'orders_order'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer,
                     ForeignKey('users_user.id', ondelete='CASCADE'),
                     nullable=False)
    delivery = Column(String, server_default=text("'Самовывоз'"), nullable=False)
    payment_id = Column(String(length=255), nullable=True)
    status = Column(String(10), default='Не оплачен', nullable=False)
    __table_args__ = (CheckConstraint("status IN ("
                                      f"'{OrderStatus.NOT_PAID}', "
                                      f"'{OrderStatus.PAID}', "
                                      f"'{OrderStatus.COMPLETED}')",
                                      name='order_status_check'),)

    user = relationship('User', back_populates='orders')
    orderitems = relationship('OrderItem', back_populates='order',
                              cascade="all, delete-orphan", passive_deletes=True)


class OrderItem(Base):
    __tablename__ = 'orders_orderitem'
    id = Column(Integer, primary_key=True)
    order_id = Column(
        Integer,
        ForeignKey('orders_order.id', ondelete='CASCADE'),
        nullable=False
    )
    product_id = Column(
        Integer,
        ForeignKey('products_product.id', ondelete='CASCADE'),
        nullable=False
    )
    quantity = Column(Integer, default=1, nullable=False)

    order = relationship('Order', back_populates='orderitems')
    products = relationship('Product')

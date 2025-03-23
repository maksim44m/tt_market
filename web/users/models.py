from django.db import models
from web.products import Product


class User(models.Model):
    id = models.AutoField(primary_key=True)
    tg_id = models.BigIntegerField(unique=True, null=False)
    first_name = models.CharField(null=True)
    last_name = models.CharField(null=True)
    username = models.CharField(max_length=32, null=True, blank=True)

    def __str__(self):
        return f"{self.tg_id} - {self.username}"

    class Meta:
        db_table = 'users_user'


class Cart(models.Model):
    """Корзина пользователя со связью 1:1"""
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User,
                                on_delete=models.CASCADE,
                                related_name="cart",
                                null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)

    def __str__(self):
        return f"Корзина пользователя {self.user.tg_id}"

    class Meta:
        db_table = 'users_cart'


class CartItem(models.Model):
    """Товары в корзинах со связями корзин 1:М и продуктов 1:М"""
    id = models.AutoField(primary_key=True)
    cart = models.ForeignKey(Cart,
                             on_delete=models.CASCADE,
                             related_name="items",
                             null=False)
    product = models.ForeignKey(Product,
                                on_delete=models.CASCADE,
                                null=False)
    quantity = models.PositiveIntegerField(default=1, null=False)

    def __str__(self):
        return f"{self.product.name} (x{self.quantity})"

    class Meta:
        db_table = 'users_cartitem'

from typing import cast

from django.db import models
from web.users import User
from web.products import Product


class Order(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='order',
                             null=False)
    delivery = models.TextField(default='Самовывоз', null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    status = models.CharField(max_length=20, default='Новый', null=False)

    def __str__(self):
        return f"Order #{self.id} - User {self.user.tg_id}"  # type: ignore

    class Meta:
        db_table = 'orders_order'


class OrderItem(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order,
                              on_delete=models.CASCADE,
                              related_name='items',
                              null=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=False)
    quantity = models.PositiveIntegerField(default=1, null=False)

    def __str__(self):
        quantity_val = int(getattr(self, 'quantity'))  # иначе интерпретатор ругается
        prod = cast(Product, self.product)
        total = quantity_val * prod.price
        return f"{self.product.name}: {self.quantity} x {prod.price} = {total}"

    class Meta:
        db_table = 'orders_orderitem'

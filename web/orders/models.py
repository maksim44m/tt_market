from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from django.db import models
from users.models import User
from products.models import Product


class Order(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='order',
                             null=False)
    delivery = models.TextField(default='Самовывоз', null=False)
    payment_id = models.CharField(max_length=255, null=True)
    ORDER_STATUS_CHOICES = [('Не оплачен', 'Не оплачен'),
                            ('Оплачен', 'Оплачен'),
                            ('Выполнен', 'Выполнен'), ]
    status = models.CharField(max_length=10,
                              choices=ORDER_STATUS_CHOICES,
                              default='Не оплачен',
                              null=False)

    def __str__(self):
        return f"Order #{self.id} - User {self.user.tg_id}"  # type: ignore

    class Meta:
        db_table = 'orders_order'
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def get_total_for_order(self):
        total = sum(item.get_total_for_orderitem() for item in self.items.all())  # type: ignore
        total_dec = Decimal(total)
        return total_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class OrderItem(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order,
                              on_delete=models.CASCADE,
                              related_name='items',
                              null=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=False)
    quantity = models.PositiveIntegerField(default=1, null=False)

    def get_total_for_orderitem(self):
        quantity_val = int(getattr(self, 'quantity'))  # иначе интерпретатор ругается
        prod = cast(Product, self.product)
        total_dec = Decimal(quantity_val * prod.price)
        return total_dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def __str__(self):
        prod = cast(Product, self.product)
        total = self.get_total_for_orderitem()
        return (f"{self.product.name}: "
                f"количество - {self.quantity}, "
                f"цена - {prod.price}, "
                f"сумма - {total}")

    class Meta:
        db_table = 'orders_orderitem'

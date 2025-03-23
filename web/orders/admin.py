from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):  # или StackedInline
    """Инлайн-модель для ордера"""
    model = OrderItem
    extra = 0


@admin.register(Order)
class CartAdmin(admin.ModelAdmin):
    """Регистрация ордера и задание инлайн модели для вывода"""
    inlines = [OrderItemInline]

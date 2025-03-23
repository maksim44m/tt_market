from django.contrib import admin
from .models import User, Cart, CartItem


admin.site.register(User)


class CartItemInline(admin.TabularInline):  # или StackedInline
    """Инлайн-модель для корзины"""
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Регистрация корзины и задание инлайн модели для вывода"""
    inlines = [CartItemInline]

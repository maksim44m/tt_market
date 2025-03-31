from django.contrib import admin
from .models import Product, Category, SubCategory


class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1  # Количество дополнительных форм


class ProductInline(admin.TabularInline):
    model = Product
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    inlines = [SubCategoryInline]
    list_display = ("id", "name")
    search_fields = ("name", 'display_subcategories',)

    def display_subcategories(self, obj):
        return ", ".join([sub.name for sub in obj.subcategories.all()])
    display_subcategories.short_description = "Подкатегории"


@admin.register(SubCategory)
class SubcategoryAdmin(admin.ModelAdmin):
    inlines = [ProductInline]
    list_display = ("id", "name")
    search_fields = ("name", 'display_products',)

    def display_products(self, obj):
        return ", ".join([sub.name for sub in obj.products.all()])
    display_products.short_description = "Продукты"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "price")
    list_filter = ("category",)
    search_fields = ("name", "description")


from django.db import models


class Category(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, null=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'products_category'


class SubCategory(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category,
                                 related_name='subcategories',
                                 on_delete=models.CASCADE,
                                 verbose_name="Категория",
                                 null=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'products_subcategory'


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey(Category,
                                 related_name='products',
                                 on_delete=models.CASCADE,
                                 verbose_name="Категория",
                                 null=False)
    subcategory = models.ForeignKey(SubCategory,
                                    related_name='subcategory_products',
                                    on_delete=models.CASCADE,
                                    verbose_name="Подкатегория",
                                    null=False)
    name = models.CharField(max_length=255, null=False)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=False)
    image_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'products_product'

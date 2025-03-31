from datetime import datetime
from io import BytesIO

from django.contrib import admin
from django.http import HttpResponse
from openpyxl import Workbook

from .models import Order, OrderItem


admin.site.site_header = "Административная панель"
admin.site.site_title = "Панель Заказов"


def export_paid_orders(modeladmin, request, queryset):
    """
    Экспорт оплаченных заказов в Excel.
    Предполагается, что заказ считается оплаченным, если у него status == 'paid'
    и у модели Order есть related_name 'items' для OrderItem.
    """
    # Фильтрация оплаченных заказов
    paid_orders = queryset.filter(status='Оплачен')
    if not paid_orders.exists():
        modeladmin.message_user(request, "Нет оплаченных заказов для экспорта.")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Paid Orders"

    table_headers = ["ID",
                     "Пользователь (tg_id)",
                     "Способ доставки",
                     "Статус",
                     "Товары",
                     "Сумма заказа"]
    ws.append(table_headers)

    for order in paid_orders:
        row = [order.id,
               order.user.tg_id,
               order.delivery,
               order.status,
               "\n".join(str(item) for item in order.items.all()),
               order.get_total_for_order()]
        ws.append(row)

    output = BytesIO()  # объект для временного сохранения данных в байтах
    wb.save(output)
    output.seek(0)  # возврат курсора в начало для чтения сначала файла

    filename = f"paid_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    response = HttpResponse(
        output.read(),
        headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 "Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )
    return response


export_paid_orders.short_description = "Экспортировать оплаченные заказы в Excel"


class OrderItemInline(admin.TabularInline):  # или StackedInline
    """Инлайн-модель для ордера"""
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Регистрация ордера и задание инлайн модели для вывода"""
    inlines = [OrderItemInline]
    exclude = ('payment_id',)
    actions = [export_paid_orders]

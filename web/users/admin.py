from django.contrib import admin, messages
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.urls import path
from django.conf import settings
import requests

from .models import User, Cart, CartItem, Broadcast
from .forms import BroadcastForm


admin.site.register(User)


class CartItemInline(admin.TabularInline):  # или StackedInline
    """Инлайн-модель для корзины"""
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Регистрация корзины и задание инлайн модели для вывода"""
    inlines = [CartItemInline]


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        """Пустой QuerySet чтобы не выполнять запрос к несуществующей таблице"""
        return self.model.objects.none()

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [path(
            'broadcast/',
            self.admin_site.admin_view(self.broadcast_view),
            name='users_broadcast'
        ),]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        """Перенаправление на кастомный view с формой"""
        return redirect('admin:users_broadcast')

    def broadcast_view(self, request: HttpRequest):
        if request.method == 'POST':
            form = BroadcastForm(request.POST)
            if form.is_valid():
                message_text = form.cleaned_data['message']
                try:
                    response = requests.post(settings.BOT_BROADCAST_URL,
                                             json={'message': message_text})
                    self.message_user(request,
                                      "Рассылка запущена!",
                                      level=messages.SUCCESS)
                    if response.status_code == 200:
                        resp_dict = response.json()
                        errors = '\n'.join(i for i in resp_dict.get('errors', []))
                        msg = f"{resp_dict.get('message', )}\n{errors}"
                        self.message_user(request, msg, level=messages.SUCCESS)
                    else:
                        self.message_user(request,
                                          f"Ошибка: {response.status_code}",
                                          level=messages.SUCCESS)
                except Exception as e:
                    self.message_user(request,
                                      f"Ошибка: {e}",
                                      level=messages.ERROR)
                return redirect("..")
        else:
            form = BroadcastForm()
        context = {
            "title": "Рассылка сообщений",
            "form": form,
            **self.admin_site.each_context(request)
        }
        return render(request, "admin/broadcast_form.html", context)

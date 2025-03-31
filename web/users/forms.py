from django import forms


class BroadcastForm(forms.Form):
    """Для рассылок"""
    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'cols': 60}),
        label="Сообщение для рассылки"
    )

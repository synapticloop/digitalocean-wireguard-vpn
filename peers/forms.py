from decimal import Decimal, InvalidOperation
from django import forms
from accounts.models import User

class UserCreateForm(forms.ModelForm):
    usage_limit_gb = forms.DecimalField(required=False, min_value=Decimal('0'), decimal_places=3, max_digits=12, help_text='Blank means unlimited. Admins are never locked out of the web interface by limits.')

    class Meta:
        model = User
        fields = ['username', 'email', 'is_vpn_admin', 'is_active', 'usage_limit_gb', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.usage_limit_bytes is not None:
            self.fields['usage_limit_gb'].initial = Decimal(self.instance.usage_limit_bytes) / Decimal(1024 ** 3)

    def save(self, commit=True):
        obj = super().save(commit=False)
        limit_gb = self.cleaned_data.get('usage_limit_gb')
        if limit_gb in (None, ''):
            obj.usage_limit_bytes = None
        else:
            obj.usage_limit_bytes = int(Decimal(limit_gb) * Decimal(1024 ** 3))
        if commit:
            obj.save()
            self.save_m2m()
        return obj

class PeerCreateForm(forms.Form):
    name = forms.CharField(max_length=100)
    enabled = forms.BooleanField(required=False, initial=True)

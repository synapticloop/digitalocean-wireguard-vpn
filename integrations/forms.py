from django import forms
from .models import PrivacySettings

class DigitalOceanSettingsForm(forms.Form):
    api_token = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False), help_text='Leave blank to keep existing token.')
    droplet_id = forms.CharField(required=False)
    usage_window_override_day = forms.IntegerField(min_value=1, max_value=28, initial=1)

class PrivacySettingsForm(forms.ModelForm):
    class Meta:
        model = PrivacySettings
        fields = ['persistent_audit_logs_enabled', 'persistent_usage_accounting_enabled']
        labels = {
            'persistent_audit_logs_enabled': 'Enable persistent audit/config logs',
            'persistent_usage_accounting_enabled': 'Enable persistent WireGuard usage accounting',
        }

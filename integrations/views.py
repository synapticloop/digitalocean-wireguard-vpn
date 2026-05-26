from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from peers.views import require_admin
from peers.models import record_audit
from .crypto import encrypt
from .forms import DigitalOceanSettingsForm, PrivacySettingsForm
from .models import DigitalOceanSettings, IntegrationSecret, PrivacySettings


def token_hint(token):
    return token[:6] + '...' + token[-4:] if len(token) >= 12 else 'saved'


def digitalocean_settings(request):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    settings_obj = DigitalOceanSettings.get_solo()
    if request.method == 'POST':
        form = DigitalOceanSettingsForm(request.POST)
        if form.is_valid():
            token = form.cleaned_data['api_token']
            if token:
                secret, _ = IntegrationSecret.objects.update_or_create(name='digitalocean_api_token', defaults={'encrypted_value': encrypt(token), 'token_hint': token_hint(token)})
                settings_obj.token_secret = secret
            settings_obj.droplet_id = form.cleaned_data['droplet_id']
            settings_obj.usage_window_override_day = form.cleaned_data['usage_window_override_day']
            settings_obj.save()
            record_audit(admin_user, 'digitalocean.settings.update')
            messages.success(request, 'DigitalOcean settings saved.')
            return redirect('digitalocean_settings')
    else:
        form = DigitalOceanSettingsForm(initial={'droplet_id': settings_obj.droplet_id, 'usage_window_override_day': settings_obj.usage_window_override_day})
    return render(request, 'integrations/digitalocean.html', {'form': form, 'settings_obj': settings_obj})


def privacy_settings(request):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    settings_obj = PrivacySettings.get_solo()
    form = PrivacySettingsForm(request.POST or None, instance=settings_obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        # Intentionally record only when persistent audit logs remain enabled after save.
        record_audit(admin_user, 'privacy.settings.update')
        messages.success(request, 'Privacy settings saved.')
        return redirect('privacy_settings')
    return render(request, 'integrations/privacy.html', {'form': form, 'settings_obj': settings_obj})

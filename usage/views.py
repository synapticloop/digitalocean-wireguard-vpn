from django.http import HttpResponseForbidden
from django.shortcuts import render
from peers.views import require_admin
from integrations.models import DigitalOceanSettings
from .models import UsagePeriod, PeerUsagePeriodTotal, DropletUsagePeriodTotal


def usage_dashboard(request):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    period = UsagePeriod.objects.filter(is_current=True).first()
    totals = PeerUsagePeriodTotal.objects.select_related('peer', 'peer__user').filter(period=period).order_by('peer__vpn_ipv4') if period else []
    droplet_total = DropletUsagePeriodTotal.objects.filter(period=period).first() if period else None
    return render(request, 'usage/dashboard.html', {
        'period': period,
        'totals': totals,
        'droplet_total': droplet_total,
        'digitalocean_settings': DigitalOceanSettings.get_solo(),
    })

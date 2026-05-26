import base64
from io import BytesIO
import qrcode
from django.contrib import messages
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from accounts.models import User
from .forms import UserCreateForm, PeerCreateForm
from .models import Peer, record_audit
from .services import next_available_ipv4, wg_genkey, build_client_config
from usage.models import PeerUsagePeriodTotal
from usage.services import current_utc_month_period, user_period_bytes, user_over_limit


def require_admin(request):
    user = request.wg_user
    if not user or not user.is_vpn_admin:
        return None
    return user


def config_qr_data_uri(config_text):
    img = qrcode.make(config_text)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def dashboard(request):
    period = current_utc_month_period()
    peers = list(Peer.objects.select_related('user').order_by('vpn_ipv4'))
    totals = {
        row['peer_id']: (row['rx'] or 0) + (row['tx'] or 0)
        for row in PeerUsagePeriodTotal.objects.filter(period=period).values('peer_id').annotate(rx=Sum('rx_bytes'), tx=Sum('tx_bytes'))
    }
    peer_rows = []
    for peer in peers:
        if peer.user.is_vpn_admin:
            status = 'Admin'
        elif not peer.enabled or not peer.user.is_active:
            status = 'Disabled'
        elif user_over_limit(peer.user, period):
            status = 'Limited'
        else:
            status = 'Active'
        peer_rows.append({
            'peer': peer,
            'usage_bytes': totals.get(peer.id, 0),
            'status': status,
            'initial': (peer.name or peer.user.username or '?')[:1].upper(),
        })

    total_usage = sum(totals.values())
    configured_limits = [u.usage_limit_bytes for u in User.objects.filter(usage_limit_bytes__isnull=False)]
    total_limit = sum(configured_limits) if configured_limits else None
    usage_percent = min(int((total_usage / total_limit) * 100), 100) if total_limit else 0
    admins = User.objects.filter(is_active=True, is_vpn_admin=True).count()
    active_peers = Peer.objects.filter(enabled=True, user__is_active=True).count()
    setup_peer = next((peer for peer in peers if peer.one_time_client_config), None)
    setup_qr_data_uri = config_qr_data_uri(setup_peer.one_time_client_config) if setup_peer else ''
    usage_rows = sorted(peer_rows, key=lambda row: row['usage_bytes'], reverse=True)
    max_usage = max([row['usage_bytes'] for row in usage_rows] + [1])
    for row in usage_rows:
        row['usage_percent'] = int((row['usage_bytes'] / max_usage) * 100)
    top_usage_rows = usage_rows[:4]
    other_usage_bytes = sum(row['usage_bytes'] for row in usage_rows[4:])
    other_usage_percent = int((other_usage_bytes / max_usage) * 100) if other_usage_bytes else 0

    return render(request, 'peers/dashboard.html', {
        'period': period,
        'peer_rows': peer_rows,
        'active_peers': active_peers,
        'total_peers': len(peers),
        'admins': admins,
        'total_usage': total_usage,
        'total_limit': total_limit,
        'usage_percent': usage_percent,
        'setup_peer': setup_peer,
        'setup_qr_data_uri': setup_qr_data_uri,
        'top_usage_rows': top_usage_rows,
        'other_usage_bytes': other_usage_bytes,
        'other_usage_percent': other_usage_percent,
    })


def user_list(request):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Admin access requires an active admin WireGuard peer.')
    period = current_utc_month_period()
    rows = []
    for user in User.objects.order_by('username'):
        used = user_period_bytes(user, period)
        rows.append({'user': user, 'used_bytes': used, 'over_limit': user_over_limit(user, period)})
    return render(request, 'peers/user_list.html', {'rows': rows})


def user_add(request):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    form = UserCreateForm(request.POST or None, initial={'is_active': True})
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        record_audit(admin_user, 'user.create', 'user', user.id)
        messages.success(request, 'User created.')
        return redirect('user_detail', user_id=user.id)
    return render(request, 'peers/form.html', {'form': form, 'title': 'Add user'})


def user_edit(request, user_id):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    user = get_object_or_404(User, id=user_id)
    form = UserCreateForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        record_audit(admin_user, 'user.update', 'user', user.id)
        messages.success(request, 'User updated.')
        return redirect('user_detail', user_id=user.id)
    return render(request, 'peers/form.html', {'form': form, 'title': f'Edit {user.username}'})


def user_detail(request, user_id):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    user = get_object_or_404(User, id=user_id)
    period = current_utc_month_period()
    return render(request, 'peers/user_detail.html', {
        'target_user': user,
        'used_bytes': user_period_bytes(user, period),
        'over_limit': user_over_limit(user, period),
    })


def peer_add(request, user_id):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    user = get_object_or_404(User, id=user_id)
    form = PeerCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        private, public = wg_genkey()
        ip = next_available_ipv4()
        config = build_client_config(private, ip)
        peer = Peer.objects.create(
            user=user,
            name=form.cleaned_data['name'],
            public_key=public,
            vpn_ipv4=ip,
            enabled=form.cleaned_data['enabled'],
            one_time_client_config=config,
        )
        record_audit(admin_user, 'peer.create', 'peer', peer.id)
        messages.success(request, 'Peer created. Scan the QR code or download the config, then commit.')
        return redirect('peer_setup', peer_id=peer.id)
    return render(request, 'peers/form.html', {'form': form, 'title': f'Add peer for {user.username}'})


def peer_setup(request, peer_id):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    peer = get_object_or_404(Peer.objects.select_related('user'), id=peer_id)
    if not peer.one_time_client_config:
        return HttpResponse('Client config no longer available.', status=410)
    return render(request, 'peers/peer_setup.html', {
        'peer': peer,
        'config_text': peer.one_time_client_config,
        'qr_data_uri': config_qr_data_uri(peer.one_time_client_config),
    })


def peer_disable(request, peer_id):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    peer = get_object_or_404(Peer, id=peer_id)
    if request.method == 'POST':
        if peer.user.is_vpn_admin and Peer.objects.filter(user__is_vpn_admin=True, enabled=True, user__is_active=True).exclude(id=peer.id).count() == 0:
            messages.error(request, 'Cannot disable the last active admin peer.')
            return redirect('user_detail', user_id=peer.user_id)
        peer.enabled = False
        peer.save(update_fields=['enabled', 'updated_at'])
        record_audit(admin_user, 'peer.disable', 'peer', peer.id)
        messages.success(request, 'Peer disabled. Commit to apply.')
    return redirect('user_detail', user_id=peer.user_id)


def peer_client_config_download(request, peer_id):
    admin_user = require_admin(request)
    if not admin_user:
        return HttpResponseForbidden('Forbidden')
    peer = get_object_or_404(Peer, id=peer_id)
    if not peer.one_time_client_config:
        return HttpResponse('Client config no longer available.', status=410)
    config_text = peer.one_time_client_config
    peer.one_time_client_config = ''
    peer.one_time_config_downloaded_at = timezone.now()
    peer.save(update_fields=['one_time_client_config', 'one_time_config_downloaded_at'])
    resp = HttpResponse(config_text, content_type='text/plain')
    resp['Content-Disposition'] = f'attachment; filename="wg-{peer.user.username}-{peer.name}.conf"'
    return resp

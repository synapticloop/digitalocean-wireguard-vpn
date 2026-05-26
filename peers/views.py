import base64
from io import BytesIO
import qrcode
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from accounts.models import User
from .forms import UserCreateForm, PeerCreateForm
from .models import Peer, record_audit
from .services import next_available_ipv4, wg_genkey, build_client_config
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
    peers = Peer.objects.select_related('user').order_by('vpn_ipv4')
    return render(request, 'peers/dashboard.html', {'peers': peers})


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

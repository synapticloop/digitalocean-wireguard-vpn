import ipaddress
from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils.functional import SimpleLazyObject


def get_client_ip(request):
    # Nginx connects to Gunicorn over loopback and sets X-Real-IP. Only trust it when the
    # immediate socket peer is loopback. Never trust X-Forwarded-For for identity.
    remote = request.META.get('REMOTE_ADDR', '')
    if remote in {'127.0.0.1', '::1'}:
        return request.META.get('HTTP_X_REAL_IP', remote)
    return remote


def ip_in_wg_subnet(ip):
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network(settings.WG_SUBNET, strict=False)
    except ValueError:
        return False


def resolve_wireguard_peer(request):
    from peers.models import Peer
    ip = get_client_ip(request)
    try:
        return Peer.objects.select_related('user').get(vpn_ipv4=ip, enabled=True, user__is_active=True)
    except Peer.DoesNotExist:
        return None


def resolve_wireguard_user(request):
    peer = resolve_wireguard_peer(request)
    return peer.user if peer else None


class WireGuardOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.wg_remote_addr = get_client_ip(request)
        request.wg_peer = SimpleLazyObject(lambda: resolve_wireguard_peer(request))
        request.wg_user = SimpleLazyObject(lambda: request.wg_peer.user if request.wg_peer else None)

        allowed_prefixes = ('/static/',)
        if any(request.path.startswith(prefix) for prefix in allowed_prefixes):
            return self.get_response(request)

        if not ip_in_wg_subnet(request.wg_remote_addr):
            return HttpResponseForbidden('This interface is only available through the WireGuard VPN.')

        peer = request.wg_peer
        if not peer:
            return HttpResponseForbidden('This WireGuard address is not registered as an active peer.')

        from usage.services import user_over_limit
        if user_over_limit(peer.user):
            return HttpResponseForbidden('This user has exceeded their usage limit.')

        return self.get_response(request)

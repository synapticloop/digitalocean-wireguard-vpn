import ipaddress
import subprocess
from django.conf import settings
from .models import Peer


def next_available_ipv4():
    net = ipaddress.ip_network(settings.WG_SUBNET, strict=False)
    used = set(Peer.objects.values_list('vpn_ipv4', flat=True))
    for ip in net.hosts():
        s = str(ip)
        if s != settings.WG_SERVER_IP and s not in used:
            return s
    raise RuntimeError('No available WireGuard IP addresses')


def wg_genkey():
    private = subprocess.check_output(['wg', 'genkey'], text=True).strip()
    public = subprocess.check_output(['wg', 'pubkey'], input=private, text=True).strip()
    return private, public


def build_client_config(private_key, address):
    from commits.models import ServerConfig
    server = ServerConfig.get_solo()
    return (
        f"[Interface]\n"
        f"PrivateKey = {private_key}\n"
        f"Address = {address}/32\n"
        f"DNS = 9.9.9.9, 149.112.112.112\n\n"
        f"[Peer]\n"
        f"PublicKey = {server.public_key}\n"
        f"Endpoint = {settings.WG_PUBLIC_ENDPOINT}\n"
        f"AllowedIPs = 0.0.0.0/0\n"
        f"PersistentKeepalive = 25\n"
    )

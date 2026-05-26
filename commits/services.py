from pathlib import Path
import os
import subprocess
from django.conf import settings
from peers.models import Peer
from .models import ServerConfig


def render_wg0_conf():
    from usage.services import current_utc_month_period, user_over_limit
    server = ServerConfig.get_solo()
    period = current_utc_month_period()
    lines = [
        '[Interface]',
        f'Address = {settings.WG_SERVER_IP}/24',
        f'ListenPort = {server.listen_port}',
        f'PrivateKey = {server.private_key}',
        '',
        '# NAT/firewall are managed by bootstrap scripts.',
        '',
    ]
    for peer in Peer.objects.select_related('user').filter(enabled=True, user__is_active=True).order_by('vpn_ipv4'):
        if user_over_limit(peer.user, period):
            lines += [f'# {peer.user.username} / {peer.name} omitted: usage limit exceeded', '']
            continue
        lines += [
            f'# {peer.user.username} / {peer.name}',
            '[Peer]',
            f'PublicKey = {peer.public_key}',
            f'AllowedIPs = {peer.vpn_ipv4}/32',
        ]
        if peer.preshared_key:
            lines.append(f'PresharedKey = {peer.preshared_key}')
        lines.append('')
    return '\n'.join(lines) + '\n'


def write_candidate():
    path = Path(settings.WG_CANDIDATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(render_wg0_conf(), encoding='utf-8')
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    return str(path)


def run_commit_helper():
    return subprocess.run(['sudo', '/usr/local/sbin/wg-admin-commit'], text=True, capture_output=True, timeout=60)

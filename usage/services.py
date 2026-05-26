import subprocess
from datetime import datetime, timezone as dt_timezone
from django.db import transaction
from django.utils import timezone
from peers.models import Peer
from .models import UsagePeriod, PeerUsagePeriodTotal, PeerUsageRuntimeState


def current_utc_month_period():
    now = timezone.now()
    start = datetime(now.year, now.month, 1, tzinfo=dt_timezone.utc)
    end = datetime(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1, tzinfo=dt_timezone.utc)
    UsagePeriod.objects.exclude(period_start=start, period_end=end).filter(is_current=True).update(is_current=False)
    period, _ = UsagePeriod.objects.get_or_create(provider='digitalocean', period_start=start, period_end=end, defaults={'is_current': True, 'source': 'utc_calendar_month'})
    if not period.is_current:
        period.is_current = True
        period.save(update_fields=['is_current'])
    return period


def parse_wg_transfer(interface='wg0'):
    output = subprocess.check_output(['wg', 'show', interface, 'transfer'], text=True)
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 3:
            yield parts[0], int(parts[1]), int(parts[2])


def user_period_bytes(user, period=None):
    period = period or current_utc_month_period()
    qs = PeerUsagePeriodTotal.objects.filter(period=period, peer__user=user)
    return sum((row.rx_bytes + row.tx_bytes) for row in qs)


def user_over_limit(user, period=None):
    if user.is_vpn_admin or user.usage_limit_bytes is None:
        return False
    return user_period_bytes(user, period) >= user.usage_limit_bytes


@transaction.atomic
def collect_usage(interface='wg0'):
    from integrations.models import PrivacySettings
    if not PrivacySettings.get_solo().persistent_usage_accounting_enabled:
        return 0
    period = current_utc_month_period()
    now = timezone.now()
    seen = 0
    for public_key, rx, tx in parse_wg_transfer(interface):
        try:
            peer = Peer.objects.get(public_key=public_key)
        except Peer.DoesNotExist:
            continue
        state, _ = PeerUsageRuntimeState.objects.get_or_create(peer=peer)
        delta_rx = rx - state.last_rx_bytes if rx >= state.last_rx_bytes else rx
        delta_tx = tx - state.last_tx_bytes if tx >= state.last_tx_bytes else tx
        total, _ = PeerUsagePeriodTotal.objects.get_or_create(period=period, peer=peer)
        total.rx_bytes += max(delta_rx, 0)
        total.tx_bytes += max(delta_tx, 0)
        total.save(update_fields=['rx_bytes', 'tx_bytes'])
        state.last_rx_bytes = rx
        state.last_tx_bytes = tx
        state.last_sampled_at = now
        state.save(update_fields=['last_rx_bytes', 'last_tx_bytes', 'last_sampled_at'])
        seen += 1
    return seen


def enforce_usage_limits():
    from commits.services import write_candidate, run_commit_helper
    period = current_utc_month_period()
    changed = 0
    for peer in Peer.objects.select_related('user').filter(enabled=True, user__is_active=True):
        if user_over_limit(peer.user, period):
            peer.enabled = False
            peer.save(update_fields=['enabled', 'updated_at'])
            changed += 1
    if changed:
        write_candidate()
        run_commit_helper()
    return changed

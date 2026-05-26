import calendar
import subprocess
from datetime import datetime, timezone as dt_timezone
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from peers.models import Peer
from .models import UsagePeriod, PeerUsagePeriodTotal, PeerUsageRuntimeState


def current_utc_month_period():
    now = timezone.now()
    try:
        from integrations.models import DigitalOceanSettings
        window_day = DigitalOceanSettings.get_solo().usage_window_override_day
    except (OperationalError, ProgrammingError):
        window_day = 1
    window_day = min(max(int(window_day or 1), 1), 28)
    start_year = now.year
    start_month = now.month
    if now.day < window_day:
        if start_month == 1:
            start_year -= 1
            start_month = 12
        else:
            start_month -= 1
    if start_month == 12:
        end_year = start_year + 1
        end_month = 1
    else:
        end_year = start_year
        end_month = start_month + 1
    start_day = min(window_day, calendar.monthrange(start_year, start_month)[1])
    end_day = min(window_day, calendar.monthrange(end_year, end_month)[1])
    start = datetime(start_year, start_month, start_day, tzinfo=dt_timezone.utc)
    end = datetime(end_year, end_month, end_day, tzinfo=dt_timezone.utc)
    source = 'utc_calendar_month' if window_day == 1 else f'manual_day_{window_day}'
    UsagePeriod.objects.exclude(period_start=start, period_end=end).filter(is_current=True).update(is_current=False)
    period, _ = UsagePeriod.objects.get_or_create(provider='digitalocean', period_start=start, period_end=end, defaults={'is_current': True, 'source': source})
    if not period.is_current:
        period.is_current = True
        period.source = source
        period.save(update_fields=['is_current', 'source'])
    return period


def parse_wg_transfer(interface='wg0'):
    output = subprocess.check_output(['wg', 'show', interface, 'transfer'], text=True)
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 3:
            yield parts[0], int(parts[1]), int(parts[2])


def parse_wg_handshakes(interface='wg0'):
    output = subprocess.check_output(['wg', 'show', interface, 'dump'], text=True)
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 5:
            try:
                handshake_epoch = int(parts[4])
            except ValueError:
                continue
            yield parts[0], handshake_epoch


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
    handshakes = dict(parse_wg_handshakes(interface))
    for public_key, rx, tx in parse_wg_transfer(interface):
        try:
            peer = Peer.objects.get(public_key=public_key)
        except Peer.DoesNotExist:
            continue
        handshake_epoch = handshakes.get(public_key, 0)
        if handshake_epoch > 0:
            handshake_at = datetime.fromtimestamp(handshake_epoch, tz=dt_timezone.utc)
            if peer.latest_handshake_at is None or handshake_at > peer.latest_handshake_at:
                peer.latest_handshake_at = handshake_at
                peer.save(update_fields=['latest_handshake_at'])
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

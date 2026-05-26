import requests
from django.utils import timezone

from usage.models import DropletUsagePeriodTotal
from usage.services import current_utc_month_period
from .crypto import decrypt
from .models import DigitalOceanSettings


DIGITALOCEAN_BANDWIDTH_URL = 'https://api.digitalocean.com/v2/monitoring/metrics/droplet/bandwidth'


def _integrate_mbps_values(values):
    points = []
    for raw_timestamp, raw_value in values:
        try:
            points.append((float(raw_timestamp), float(raw_value)))
        except (TypeError, ValueError):
            continue
    points.sort(key=lambda point: point[0])
    total_bytes = 0.0
    for (left_ts, left_mbps), (right_ts, right_mbps) in zip(points, points[1:]):
        interval = max(right_ts - left_ts, 0)
        average_mbps = (left_mbps + right_mbps) / 2
        total_bytes += average_mbps * 1_000_000 * interval / 8
    return max(int(total_bytes), 0), len(points)


def _fetch_bandwidth_values(token, droplet_id, interface, direction, start, end):
    response = requests.get(
        DIGITALOCEAN_BANDWIDTH_URL,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        params={
            'host_id': droplet_id,
            'interface': interface,
            'direction': direction,
            'start': str(int(start.timestamp())),
            'end': str(int(end.timestamp())),
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json().get('data', {})
    results = data.get('result', [])
    if not results:
        return []
    return results[0].get('values', [])


def sync_digitalocean_usage():
    settings_obj = DigitalOceanSettings.get_solo()
    if not settings_obj.token_secret or not settings_obj.droplet_id:
        return None
    period = current_utc_month_period()
    token = decrypt(settings_obj.token_secret.encrypted_value)
    totals = {}
    sample_count = 0
    try:
        for interface in ('public', 'private'):
            for direction in ('inbound', 'outbound'):
                values = _fetch_bandwidth_values(
                    token,
                    settings_obj.droplet_id,
                    interface,
                    direction,
                    period.period_start,
                    min(period.period_end, timezone.now()),
                )
                total_bytes, samples = _integrate_mbps_values(values)
                totals[f'{interface}_{direction}_bytes'] = total_bytes
                sample_count += samples
    except Exception as exc:
        settings_obj.last_sync_error = str(exc)
        settings_obj.save(update_fields=['last_sync_error', 'updated_at'])
        raise

    droplet_total, _ = DropletUsagePeriodTotal.objects.get_or_create(period=period)
    for field_name, value in totals.items():
        setattr(droplet_total, field_name, value)
    droplet_total.sample_count = sample_count
    droplet_total.synced_at = timezone.now()
    droplet_total.save()
    settings_obj.last_sync_at = droplet_total.synced_at
    settings_obj.last_sync_error = ''
    settings_obj.save(update_fields=['last_sync_at', 'last_sync_error', 'updated_at'])
    return droplet_total

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from integrations.models import DigitalOceanSettings, IntegrationSecret
from integrations.services import _integrate_mbps_values, sync_digitalocean_usage
from usage.models import DropletUsagePeriodTotal


class DigitalOceanUsageSyncTests(SimpleTestCase):
    def test_integrates_mbps_samples_to_bytes(self):
        total_bytes, sample_count = _integrate_mbps_values([
            [0, '8'],
            [10, '8'],
            [20, '16'],
        ])

        self.assertEqual(sample_count, 3)
        self.assertEqual(total_bytes, 25_000_000)


class DigitalOceanUsagePersistenceTests(TestCase):
    def test_sync_writes_droplet_totals_and_status_to_database(self):
        secret = IntegrationSecret.objects.create(
            name='digitalocean_api_token',
            encrypted_value=b'encrypted-token',
            token_hint='saved',
        )
        settings_obj = DigitalOceanSettings.get_solo()
        settings_obj.token_secret = secret
        settings_obj.droplet_id = '12345'
        settings_obj.save()

        samples_by_key = {
            ('public', 'inbound'): [[0, '8'], [10, '8']],
            ('public', 'outbound'): [[0, '16'], [10, '16']],
            ('private', 'inbound'): [[0, '0'], [10, '0']],
            ('private', 'outbound'): [[0, '4'], [10, '4']],
        }

        def fake_fetch(token, droplet_id, interface, direction, start, end):
            self.assertEqual(token, 'token')
            self.assertEqual(droplet_id, '12345')
            return samples_by_key[(interface, direction)]

        with patch('integrations.services.decrypt', return_value='token'), patch('integrations.services._fetch_bandwidth_values', side_effect=fake_fetch):
            droplet_total = sync_digitalocean_usage()

        droplet_total.refresh_from_db()
        settings_obj.refresh_from_db()
        self.assertEqual(DropletUsagePeriodTotal.objects.count(), 1)
        self.assertEqual(droplet_total.public_inbound_bytes, 10_000_000)
        self.assertEqual(droplet_total.public_outbound_bytes, 20_000_000)
        self.assertEqual(droplet_total.private_inbound_bytes, 0)
        self.assertEqual(droplet_total.private_outbound_bytes, 5_000_000)
        self.assertEqual(droplet_total.sample_count, 8)
        self.assertIsNotNone(droplet_total.synced_at)
        self.assertEqual(settings_obj.last_sync_at, droplet_total.synced_at)
        self.assertEqual(settings_obj.last_sync_error, '')

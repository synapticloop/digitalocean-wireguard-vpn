from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from integrations.models import PrivacySettings
from peers.models import Peer
from usage.models import PeerUsagePeriodTotal
from usage.services import collect_usage, current_utc_month_period


class WireGuardUsageCollectionTests(TestCase):
    def test_collect_usage_adds_deltas_and_handles_counter_reset(self):
        user = User.objects.create_user(username='alice', is_active=True)
        peer = Peer.objects.create(user=user, name='phone', public_key='pubkey1', vpn_ipv4='10.44.0.9')
        PrivacySettings.get_solo()

        with patch('usage.services.parse_wg_transfer', return_value=[('pubkey1', 100, 200)]):
            self.assertEqual(collect_usage('wg0'), 1)
        with patch('usage.services.parse_wg_transfer', return_value=[('pubkey1', 150, 250)]):
            self.assertEqual(collect_usage('wg0'), 1)
        with patch('usage.services.parse_wg_transfer', return_value=[('pubkey1', 10, 20)]):
            self.assertEqual(collect_usage('wg0'), 1)

        total = PeerUsagePeriodTotal.objects.get(period=current_utc_month_period(), peer=peer)
        self.assertEqual(total.rx_bytes, 160)
        self.assertEqual(total.tx_bytes, 270)

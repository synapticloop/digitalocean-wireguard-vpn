from django.test import Client, TestCase

from accounts.models import User
from peers.models import Peer


class DashboardRenderTests(TestCase):
    def test_dashboard_renders_mobile_shell(self):
        user = User.objects.create_user(username='admin', is_active=True, is_vpn_admin=True)
        Peer.objects.create(user=user, name='Admin', public_key='pubkey1', vpn_ipv4='10.44.0.2', enabled=True)

        response = Client(REMOTE_ADDR='10.44.0.2').get('/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'WireGuard VPN Admin')
        self.assertContains(response, 'Active peers')
        self.assertContains(response, 'Handshake')

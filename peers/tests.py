from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from peers.models import Peer


class DashboardRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='admin', is_active=True, is_vpn_admin=True)
        self.peer = Peer.objects.create(
            user=self.user,
            name='Admin',
            public_key='pubkey1',
            vpn_ipv4='10.44.0.2',
            enabled=True,
            one_time_client_config='[Interface]\nPrivateKey = test\n',
        )
        self.client = Client(REMOTE_ADDR='10.44.0.2')

    def test_dashboard_renders_mobile_shell(self):
        response = Client(REMOTE_ADDR='10.44.0.2').get('/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'WireGuard VPN Admin')
        self.assertContains(response, 'Active peers')
        self.assertContains(response, 'Handshake')

    def test_primary_pages_render_mobile_shell(self):
        paths = [
            reverse('user_list'),
            reverse('user_detail', args=[self.user.id]),
            reverse('user_add'),
            reverse('user_edit', args=[self.user.id]),
            reverse('peer_add', args=[self.user.id]),
            reverse('peer_setup', args=[self.peer.id]),
            reverse('usage_dashboard'),
            reverse('digitalocean_settings'),
            reverse('privacy_settings'),
            reverse('commit_config'),
        ]

        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'app-shell')

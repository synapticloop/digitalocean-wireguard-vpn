from django.db import models
from peers.models import Peer

class UsagePeriod(models.Model):
    provider = models.CharField(max_length=32, default='digitalocean')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    source = models.CharField(max_length=64, default='utc_calendar_month')
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period_start']

class PeerUsagePeriodTotal(models.Model):
    period = models.ForeignKey(UsagePeriod, on_delete=models.CASCADE)
    peer = models.ForeignKey(Peer, on_delete=models.CASCADE)
    rx_bytes = models.BigIntegerField(default=0)
    tx_bytes = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [('period', 'peer')]

class PeerUsageRuntimeState(models.Model):
    peer = models.OneToOneField(Peer, on_delete=models.CASCADE)
    last_rx_bytes = models.BigIntegerField(default=0)
    last_tx_bytes = models.BigIntegerField(default=0)
    last_sampled_at = models.DateTimeField(null=True, blank=True)

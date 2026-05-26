from django.conf import settings
from django.db import models

class Peer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='peers')
    name = models.CharField(max_length=100)
    public_key = models.CharField(max_length=64, unique=True)
    preshared_key = models.CharField(max_length=64, blank=True)
    vpn_ipv4 = models.GenericIPAddressField(unique=True)
    enabled = models.BooleanField(default=True)
    latest_handshake_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    one_time_client_config = models.TextField(blank=True)
    one_time_config_downloaded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.user} / {self.name} / {self.vpn_ipv4}'

class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


def record_audit(actor, action, target_type='', target_id='', details=None):
    from integrations.models import PrivacySettings
    if not PrivacySettings.get_solo().persistent_audit_logs_enabled:
        return None
    return AuditLog.objects.create(actor=actor, action=action, target_type=target_type, target_id=str(target_id or ''), details=details or {})

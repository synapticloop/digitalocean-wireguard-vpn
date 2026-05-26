from django.db import models

class IntegrationSecret(models.Model):
    name = models.CharField(max_length=100, unique=True)
    encrypted_value = models.BinaryField()
    token_hint = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class DigitalOceanSettings(models.Model):
    droplet_id = models.CharField(max_length=100, blank=True)
    token_secret = models.ForeignKey(IntegrationSecret, null=True, blank=True, on_delete=models.SET_NULL)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True)
    usage_window_override_day = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

class PrivacySettings(models.Model):
    persistent_audit_logs_enabled = models.BooleanField(default=True)
    persistent_usage_accounting_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

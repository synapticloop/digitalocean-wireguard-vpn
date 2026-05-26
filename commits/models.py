from django.conf import settings
from django.db import models

class ServerConfig(models.Model):
    private_key = models.CharField(max_length=64)
    public_key = models.CharField(max_length=64)
    listen_port = models.PositiveIntegerField(default=51820)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if not obj:
            raise RuntimeError('ServerConfig has not been initialized')
        return obj

class ConfigCommit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=32)
    summary = models.TextField(blank=True)
    error = models.TextField(blank=True)
    candidate_path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    is_vpn_admin = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    usage_limit_bytes = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text='Current DigitalOcean usage-window limit. Blank means unlimited.',
    )

    @property
    def usage_limit_gb(self):
        if self.usage_limit_bytes is None:
            return None
        return self.usage_limit_bytes / (1024 ** 3)

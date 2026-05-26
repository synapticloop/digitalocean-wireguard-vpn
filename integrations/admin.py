from django.contrib import admin
from .models import IntegrationSecret, DigitalOceanSettings
admin.site.register(IntegrationSecret)
admin.site.register(DigitalOceanSettings)

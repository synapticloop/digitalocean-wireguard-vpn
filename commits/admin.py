from django.contrib import admin
from .models import ServerConfig, ConfigCommit
admin.site.register(ServerConfig)
admin.site.register(ConfigCommit)

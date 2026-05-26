from django.contrib import admin
from .models import Peer, AuditLog

@admin.register(Peer)
class PeerAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'vpn_ipv4', 'enabled', 'latest_handshake_at')
    search_fields = ('user__username', 'name', 'public_key', 'vpn_ipv4')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'target_type', 'target_id')

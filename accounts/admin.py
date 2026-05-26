from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("VPN", {"fields": ("is_vpn_admin", "notes")}),)
    list_display = ('username', 'email', 'is_active', 'is_vpn_admin', 'is_staff')

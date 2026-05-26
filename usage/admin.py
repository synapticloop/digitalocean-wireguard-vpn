from django.contrib import admin
from .models import UsagePeriod, PeerUsagePeriodTotal, PeerUsageRuntimeState, DropletUsagePeriodTotal
admin.site.register(UsagePeriod)
admin.site.register(PeerUsagePeriodTotal)
admin.site.register(PeerUsageRuntimeState)
admin.site.register(DropletUsagePeriodTotal)

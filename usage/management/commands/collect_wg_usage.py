from django.conf import settings
from django.core.management.base import BaseCommand
from usage.services import collect_usage, enforce_usage_limits

class Command(BaseCommand):
    help = 'Collect WireGuard per-peer transfer counters into period totals.'

    def add_arguments(self, parser):
        parser.add_argument('--enforce-limits', action='store_true', help='Disable/commit peers for non-admin users over their limit.')

    def handle(self, *args, **options):
        count = collect_usage(settings.WG_INTERFACE)
        msg = f'Collected usage for {count} peers'
        if options['enforce_limits']:
            disabled = enforce_usage_limits()
            msg += f'; disabled {disabled} over-limit peers'
        self.stdout.write(self.style.SUCCESS(msg))

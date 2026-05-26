from django.core.management.base import BaseCommand, CommandError

from integrations.services import sync_digitalocean_usage


class Command(BaseCommand):
    help = 'Sync aggregate DigitalOcean droplet bandwidth metrics for the current usage period.'

    def handle(self, *args, **options):
        try:
            droplet_total = sync_digitalocean_usage()
        except Exception as exc:
            raise CommandError(f'DigitalOcean usage sync failed: {exc}') from exc
        if droplet_total is None:
            self.stdout.write('Skipped DigitalOcean sync: token or droplet ID not configured')
            return
        self.stdout.write(self.style.SUCCESS(f'Synced DigitalOcean usage from {droplet_total.sample_count} samples'))

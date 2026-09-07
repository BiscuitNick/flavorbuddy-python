from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from scrape_me.models import ImportDraft


class Command(BaseCommand):
    help = "Expire abandoned previews after seven days; mark interrupted synchronous requests failed."

    def handle(self, *args, **options):
        stale = ImportDraft.objects.filter(
            state="processing", updated_at__lt=timezone.now() - timedelta(minutes=2)
        ).update(state="failed", error_code="interrupted")
        count, _ = (
            ImportDraft.objects.filter(
                created_at__lt=timezone.now() - timedelta(days=7)
            )
            .exclude(state="saved")
            .delete()
        )
        # Saved keys remain for idempotency; original pasted input is no longer needed.
        ImportDraft.objects.filter(state="saved").update(input={})
        self.stdout.write(f"Interrupted: {stale}; expired objects: {count}")

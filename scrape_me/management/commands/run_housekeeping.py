from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run retry-safe import, private-media and OAuth cleanup for the hourly scheduler."

    def handle(self, *args, **options):
        for command in ("expire_imports", "cleanup_private_photos", "cleartokens"):
            call_command(command)

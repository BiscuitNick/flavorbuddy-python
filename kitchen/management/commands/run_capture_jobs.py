import time
from django.core.management.base import BaseCommand
from kitchen.jobs import work_one


class Command(BaseCommand):
    help = "Process durable fixture capture jobs. No live AI provider is implemented."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            worked = work_one()
            if options["once"]:
                self.stdout.write(
                    "Processed one job." if worked else "No eligible job."
                )
                return
            if not worked:
                time.sleep(2)

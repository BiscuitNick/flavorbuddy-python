from django.apps import AppConfig


class KitchenConfig(AppConfig):
    name = "kitchen"

    def ready(self):
        from . import signals  # noqa: F401

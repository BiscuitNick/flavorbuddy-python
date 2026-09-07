"""Operator-only registration/rotation; secrets are written once to a mode-0600 file."""

import json
import os
import secrets
from pathlib import Path
from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from oauth2_provider.models import Application, AccessToken
from integrations.models import AppGrant, Catalog


class Command(BaseCommand):
    help = "Register, rotate or disable one confidential catalog client. Never prints secrets."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["register", "rotate", "disable"])
        parser.add_argument("name")
        parser.add_argument("--catalog", action="append", default=[])
        parser.add_argument("--credentials-file")
        parser.add_argument("--days", type=int, default=90)

    @transaction.atomic
    def handle(self, *args, **options):
        action = options["action"]
        if not 1 <= options["days"] <= 365:
            raise CommandError("days must be 1–365")
        if action != "disable" and not options["credentials_file"]:
            raise CommandError(
                "--credentials-file is required; choose a path outside the repository"
            )
        if options["credentials_file"] and Path(
            options["credentials_file"]
        ).resolve().is_relative_to(settings.BASE_DIR):
            raise CommandError("Credentials must be stored outside the repository.")
        if action == "register":
            if Application.objects.filter(name=options["name"]).exists():
                raise CommandError(
                    "That name is registered; rotate or choose an environment-specific name."
                )
            catalogs = list(
                Catalog.objects.filter(slug__in=options["catalog"], enabled=True)
            )
            if not catalogs or len(catalogs) != len(set(options["catalog"])):
                raise CommandError(
                    "Explicit existing enabled --catalog grants are required."
                )
            app = Application(
                name=options["name"],
                client_type="confidential",
                authorization_grant_type="client-credentials",
            )
        else:
            try:
                app = Application.objects.select_for_update().get(name=options["name"])
            except Application.DoesNotExist:
                raise CommandError("Unknown client.")
            grant = AppGrant.objects.select_for_update().get(application=app)
            AccessToken.objects.filter(application=app).delete()
            if action == "disable":
                grant.enabled = False
                grant.save(update_fields=["enabled"])
                self.stdout.write("Client disabled; outstanding tokens revoked.")
                return
        secret = secrets.token_urlsafe(48)
        app.client_secret = secret
        app.save()  # Toolkit hashes the secret at rest.
        if action == "register":
            grant = AppGrant.objects.create(
                application=app,
                environment=settings.ENVIRONMENT,
                expires_at=timezone.now() + timedelta(days=options["days"]),
            )
            grant.catalogs.set(catalogs)
        else:
            grant.expires_at = timezone.now() + timedelta(days=options["days"])
            grant.save(update_fields=["expires_at"])
        try:
            fd = os.open(
                options["credentials_file"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
        except OSError:
            raise CommandError(
                "Cannot create credentials file; use a new private path."
            )
        with os.fdopen(fd, "w") as output:
            json.dump(
                {
                    "client_id": app.client_id,
                    "client_secret": secret,
                    "resource": settings.CATALOG_AUDIENCE,
                },
                output,
            )
        self.stdout.write(
            "Client credentials written privately. Rotation revoked all previous tokens."
        )

from django.conf import settings
from django.utils import timezone
from oauth2_provider.models import Application
from rest_framework.exceptions import Throttled
from scrape_me.services.budgets import reserve
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error
from .models import AppGrant


def usable(application):
    if application is None:
        return False
    return AppGrant.objects.filter(
        application=application,
        enabled=True,
        environment=settings.ENVIRONMENT,
        expires_at__gt=timezone.now(),
    ).exists()


class CatalogValidator(OAuth2Validator):
    def authenticate_client(self, request, *args, **kwargs):
        return super().authenticate_client(request, *args, **kwargs) and usable(
            request.client
        )

    def validate_grant_type(
        self, client_id, grant_type, client, request, *args, **kwargs
    ):
        return grant_type == "client_credentials" and super().validate_grant_type(
            client_id, grant_type, client, request, *args, **kwargs
        )

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        return set(scopes) == {"catalog:read"} and super().validate_scopes(
            client_id, scopes, client, request, *args, **kwargs
        )

    def _check_and_set_request_resource(self, request):
        super()._check_and_set_request_resource(request)
        if request.resource != [settings.CATALOG_AUDIENCE]:
            raise CustomOAuth2Error(
                error="invalid_target",
                description="Use the configured catalog resource.",
            )

    def validate_bearer_token(self, token, scopes, request):
        if not super().validate_bearer_token(token, scopes, request):
            return False
        access = request.access_token
        return (
            access.resource == [settings.CATALOG_AUDIENCE]
            and access.user_id is None
            and access.application.authorization_grant_type == "client-credentials"
            and usable(access.application)
        )

    def _save_bearer_token(self, token, request, *args, **kwargs):
        # Toolkit calls this inside its transaction. Coordinate with rotation.
        current = Application.objects.select_for_update().get(pk=request.client.pk)
        if current.client_secret != request.client.client_secret:
            raise CustomOAuth2Error(
                error="invalid_client", description="Credentials rotated."
            )
        grant = AppGrant.objects.select_for_update().get(application=request.client)
        if not usable(request.client):
            raise CustomOAuth2Error(
                error="invalid_client", description="Client unavailable."
            )
        minute = int(timezone.now().timestamp()) // 60
        try:
            reserve([(f"app:tokens:client:{grant.pk}:{minute}", 10)])
        except Throttled:
            raise CustomOAuth2Error(
                error="temporarily_unavailable", description="Token limit reached."
            )
        return super()._save_bearer_token(token, request, *args, **kwargs)

"""Firebase proves identity; Django continues to own sessions and application data."""

import time
import uuid
from datetime import timedelta
from functools import lru_cache
from threading import Lock

import firebase_admin
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from firebase_admin import auth, exceptions
from google.auth.exceptions import GoogleAuthError
from rest_framework import serializers
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework.response import Response

from scrape_me.models import FirebaseIdentity

_app_lock = Lock()


class IdentityUnavailable(APIException):
    status_code = 503
    default_detail = "Google sign-in is temporarily unavailable. Please try again."
    default_code = "identity_unavailable"


class LinkRequired(APIException):
    status_code = 409
    default_detail = "Enter your existing FlavorBuddy password once to connect Google and keep your recipes."
    default_code = "account_link_required"


@lru_cache(maxsize=4)
def firebase_app(project_id):
    # Uses the attached Cloud Run identity; no service account key file required.
    with _app_lock:
        try:
            return firebase_admin.get_app(project_id)
        except ValueError:
            return firebase_admin.initialize_app(
                options={"projectId": project_id, "httpTimeout": 10}, name=project_id
            )


class FirebaseCredentials(serializers.Serializer):
    id_token = serializers.CharField(max_length=16384, trim_whitespace=False)
    legacy_password = serializers.CharField(
        max_length=128, trim_whitespace=False, required=False, write_only=True
    )


def firebase_sign_in(request):
    if not settings.FIREBASE_ENABLED:
        raise IdentityUnavailable()
    data = FirebaseCredentials(data=request.data)
    data.is_valid(raise_exception=True)
    token = data.validated_data["id_token"]
    try:
        app = firebase_app(settings.FIREBASE_PROJECT_ID)
        claims = auth.verify_id_token(token, app=app, check_revoked=True)
        auth_time = claims.get("auth_time", 0)
        if (
            claims.get("firebase", {}).get("sign_in_provider") != "google.com"
            or claims.get("email_verified") is not True
            or not isinstance(auth_time, (int, float))
            or not 0 <= time.time() - auth_time <= 300
        ):
            raise AuthenticationFailed("Use a fresh Google sign-in to continue.")
        uid = serializers.CharField(max_length=128).run_validation(claims.get("uid"))
        email = (
            serializers.EmailField(max_length=254)
            .run_validation(claims.get("email"))
            .lower()
        )
        # Mint before changing local identity state so a provider outage cannot half-link.
        session_cookie = auth.create_session_cookie(
            token,
            expires_in=timedelta(seconds=settings.FIREBASE_SESSION_SECONDS),
            app=app,
        )
    except auth.CertificateFetchError:
        raise IdentityUnavailable() from None
    except (
        auth.InvalidIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        auth.UserNotFoundError,
        ValueError,
    ):
        raise AuthenticationFailed(
            "Google sign-in expired or is unavailable for this account. Sign in again."
        ) from None
    except (exceptions.FirebaseError, GoogleAuthError):
        raise IdentityUnavailable() from None

    User = get_user_model()
    try:
        with transaction.atomic():
            identity = (
                FirebaseIdentity.objects.select_related("user")
                .filter(project_id=settings.FIREBASE_PROJECT_ID, uid=uid)
                .first()
            )
            if identity:
                user = User.objects.select_for_update().get(pk=identity.user_id)
                if not user.is_active:
                    raise AuthenticationFailed("This account is unavailable.")
            else:
                # Never merge accounts on email alone: legacy emails were not verified.
                candidates = list(
                    User.objects.select_for_update().filter(
                        Q(email__iexact=email) | Q(username__iexact=email)
                    )[:2]
                )
                if candidates:
                    password = data.validated_data.get("legacy_password", "")
                    if (
                        len(candidates) != 1
                        or not password
                        or not candidates[0].check_password(password)
                    ):
                        raise LinkRequired()
                    user = candidates[0]
                    if (
                        not user.is_active
                        or FirebaseIdentity.objects.filter(user=user).exists()
                    ):
                        raise AuthenticationFailed(
                            "This account cannot be connected. Contact the administrator."
                        )
                else:
                    user = User(username="firebase_" + uuid.uuid4().hex, email=email)
                user.set_unusable_password()
                user.save()
                FirebaseIdentity.objects.create(
                    user=user, project_id=settings.FIREBASE_PROJECT_ID, uid=uid
                )
    except IntegrityError:
        # Concurrent first sign-in/link requests cannot create competing ownership.
        raise AuthenticationFailed(
            "Account sign-in changed. Please try again."
        ) from None
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["firebase_session"] = session_cookie
    request.session["firebase_uid"] = uid
    request.session.set_expiry(settings.FIREBASE_SESSION_SECONDS)
    return Response(
        {"user": {"id": user.pk, "email": user.email}, "csrf_token": get_token(request)}
    )


class FirebaseSessionMiddleware:
    """Check provider revocation/disablement before accepting a Firebase session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie = request.session.get("firebase_session")
        if cookie and not (
            request.method == "POST" and request.path == "/api/v1/auth/logout"
        ):
            try:
                if not settings.FIREBASE_ENABLED or not request.user.is_authenticated:
                    logout(request)
                else:
                    claims = auth.verify_session_cookie(
                        cookie,
                        app=firebase_app(settings.FIREBASE_PROJECT_ID),
                        check_revoked=True,
                    )
                    if (
                        claims.get("uid") != request.session.get("firebase_uid")
                        or not FirebaseIdentity.objects.filter(
                            user=request.user,
                            project_id=settings.FIREBASE_PROJECT_ID,
                            uid=claims.get("uid"),
                        ).exists()
                    ):
                        logout(request)
            except auth.CertificateFetchError:
                return self.unavailable()
            except (
                auth.InvalidSessionCookieError,
                auth.RevokedSessionCookieError,
                auth.UserDisabledError,
                auth.UserNotFoundError,
                ValueError,
            ):
                logout(request)
            except (exceptions.FirebaseError, GoogleAuthError):
                return self.unavailable()
        return self.get_response(request)

    @staticmethod
    def unavailable():
        return JsonResponse(
            {
                "error": {
                    "code": "identity_unavailable",
                    "message": str(IdentityUnavailable.default_detail),
                    "fields": {},
                }
            },
            status=503,
        )

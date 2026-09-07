from smtplib import SMTPException
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, APIException
from scrape_me.services.budgets import auth_limit

User = get_user_model()


class Credentials(serializers.Serializer):
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


def password_check(password, user):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": exc.messages})


@method_decorator(csrf_protect, name="dispatch")
class AccountView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "user": {"id": request.user.pk, "email": request.user.email}
                if request.user.is_authenticated
                else None,
                "csrf_token": get_token(request),
                "recovery_available": settings.EMAIL_BACKEND
                == "django.core.mail.backends.smtp.EmailBackend"
                and bool(settings.EMAIL_HOST),
            }
        )

    def post(self, request, action):
        if not isinstance(request.data, dict):
            raise ValidationError("Send a JSON object.")
        auth_limit(request, str(request.data.get("email", ""))[:150])
        if action == "logout":
            logout(request)
            return Response({"ok": True, "csrf_token": get_token(request)})
        if action == "reset":
            email = serializers.EmailField(max_length=150).run_validation(
                request.data.get("email")
            )
            if (
                settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend"
                or not settings.EMAIL_HOST
            ):
                raise ValidationError(
                    "Email recovery is not configured. Contact the instance administrator."
                )
            user = User.objects.filter(username=email.lower(), is_active=True).first()
            if user:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                try:
                    send_mail(
                        "Reset your FlavorBuddy password",
                        f"Reset your password: {settings.PROJECT_URL}/#/reset/{uid}/{token}",
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                    )
                except (SMTPException, OSError):
                    raise APIException(
                        "Email delivery is unavailable. Please try again later."
                    ) from None

            return Response({"ok": True})
        if action == "reset-confirm":
            try:
                user = User.objects.get(
                    pk=urlsafe_base64_decode(request.data.get("uid", "")).decode(),
                    is_active=True,
                )
            except (
                ValueError,
                TypeError,
                OverflowError,
                UnicodeError,
                User.DoesNotExist,
            ):
                raise ValidationError("This reset link is invalid or expired.")
            if not default_token_generator.check_token(
                user, request.data.get("token", "")
            ):
                raise ValidationError("This reset link is invalid or expired.")
            password = serializers.CharField(
                max_length=128, trim_whitespace=False
            ).run_validation(request.data.get("password"))
            password_check(password, user)
            user.set_password(password)
            user.save(update_fields=["password"])
            return Response({"ok": True})
        if action not in ("login", "register"):
            raise ValidationError("Unknown account action.")
        data = Credentials(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"].lower()
        password = data.validated_data["password"]
        if action == "register":
            user = User(username=email, email=email)
            password_check(password, user)
            user.set_password(password)
            try:
                user.save()
            except IntegrityError:
                raise ValidationError(
                    "Unable to create this account. Try signing in or recovering your password."
                )
        else:
            user = authenticate(request, username=email, password=password)
            if user is None:
                raise ValidationError("Email or password is incorrect.")
        login(request, user)
        return Response(
            {
                "user": {"id": user.pk, "email": user.email},
                "csrf_token": get_token(request),
            }
        )

from .models import AppAudit


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(("/api/integrations/v1/", "/api/integrations/v2/")):
            match = request.resolver_match
            # Never store request bodies, query strings, credentials or raw URLs.
            AppAudit.objects.create(
                application_id=getattr(request, "app_id", None),
                action=(
                    "token"
                    if request.path.endswith("/token")
                    else "revoke"
                    if request.path.endswith("/revoke")
                    else "catalog"
                ),
                resource_id=match.kwargs.get("pk") if match else None,
                recipe_uuid=match.kwargs.get("public_id") if match else None,
                status=response.status_code,
                request_id=request.request_id,
            )
        return response

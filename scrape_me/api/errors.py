import logging
import uuid
from rest_framework.views import exception_handler as drf_handler
from rest_framework.exceptions import APIException

logger = logging.getLogger("flavorbuddy")


class ImportFailure(APIException):
    status_code = 422
    default_code = "extraction_failed"
    default_detail = (
        "We could not extract this recipe. Paste text or enter it manually."
    )


def exception_handler(exc, context):
    response = drf_handler(exc, context)
    if response is None:
        return None
    code = getattr(exc, "default_code", "invalid_request")
    fields = (
        response.data
        if isinstance(response.data, dict) and "detail" not in response.data
        else {}
    )
    message = (
        str(response.data.get("detail", "Please check the highlighted fields."))
        if isinstance(response.data, dict)
        else "Please check your request."
    )
    request_id = getattr(context["request"], "request_id", str(uuid.uuid4()))
    response.data = {
        "error": {
            "code": code,
            "message": message,
            "fields": fields,
            "request_id": request_id,
        }
    }
    logger.info(
        "api_failure code=%s status=%s request_id=%s",
        code,
        response.status_code,
        request_id,
    )
    return response

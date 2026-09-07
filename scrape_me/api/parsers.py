import json
from rest_framework.parsers import BaseParser
from rest_framework.exceptions import ParseError, APIException


class BodyTooLarge(APIException):
    status_code = 413
    default_code = "body_too_large"
    default_detail = "This recipe is too large. Limit text to 50,000 characters."


class BoundedJSONParser(BaseParser):
    media_type = "application/json"

    def parse(self, stream, media_type=None, parser_context=None):
        body = stream.read(262145)
        if len(body) > 262144:
            raise BodyTooLarge()
        try:
            return json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError):
            raise ParseError("Send valid UTF-8 JSON.") from None

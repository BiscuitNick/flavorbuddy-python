from django.urls import path
from django.http import JsonResponse
from .views import home


def retired(request):
    return JsonResponse(
        {
            "error": {
                "code": "endpoint_retired",
                "message": "Use the private /api/v1 APIs.",
                "fields": {},
            }
        },
        status=410,
    )


urlpatterns = [
    path("", home, name="home"),
    path("parse-recipe-url", retired, name="parse-recipe-url"),
    path("get-recipes", retired, name="get-recipes"),
    path("convert-raw-recipe", retired, name="convert-raw-recipe"),
]

from django.urls import path
from oauth2_provider.views import RevokeTokenView
from .views import CatalogView, LimitedTokenView, ContractView

urlpatterns = [
    path("openapi.json", ContractView.as_view()),
    path("oauth/token", LimitedTokenView.as_view()),
    path("oauth/revoke", RevokeTokenView.as_view()),
    path("catalogs", CatalogView.as_view()),
    path("catalogs/<slug:catalog>/recipes", CatalogView.as_view()),
    path("catalogs/<slug:catalog>/recipes/<int:pk>", CatalogView.as_view()),
]

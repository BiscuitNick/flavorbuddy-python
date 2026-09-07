from django.urls import path
from .v2 import SearchView, RecipeView, V2ContractView, DocumentSchemaView

urlpatterns = [
    path("openapi.json", V2ContractView.as_view()),
    path("recipe-document.schema.json", DocumentSchemaView.as_view()),
    path("catalogs/<slug:catalog>/recipes", SearchView.as_view()),
    path("recipes/<uuid:public_id>", RecipeView.as_view()),
]

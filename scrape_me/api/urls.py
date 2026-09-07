from django.urls import path
from .accounts import AccountView
from .views import RecipesView, RecipeView, ExportView, ImportsView, CookView

from .starter import StarterView, SaveStarterView

from .lifecycle import FinalizeView, VisibilityView, VariationView, SharedView

urlpatterns = [
    path("shared-recipes", SharedView.as_view()),
    path("shared-recipes/<uuid:public_id>", SharedView.as_view()),
    path("recipes/<int:pk>/finalize", FinalizeView.as_view()),
    path("recipes/<int:pk>/visibility", VisibilityView.as_view()),
    path("recipes/<int:pk>/variations", VariationView.as_view()),
    path("starters", StarterView.as_view()),
    path("starters/<int:pk>", StarterView.as_view()),
    path("starters/<int:pk>/save", SaveStarterView.as_view()),
    path("me", AccountView.as_view()),
    path("auth/<str:action>", AccountView.as_view()),
    path("recipes", RecipesView.as_view()),
    path("recipes/export", ExportView.as_view()),
    path("recipes/<int:pk>/cook", CookView.as_view()),
    path("recipes/<int:pk>", RecipeView.as_view()),
    path("imports", ImportsView.as_view()),
    path("imports/<int:pk>", ImportsView.as_view()),
]

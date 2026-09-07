from .pantry import KitchenExportView
from django.urls import path
from .pantry import PantryView, PreferenceView, MatchView, CapabilitiesView
from .jobs import CaptureView, JobView
from .photos import PhotosView, PhotoView

urlpatterns = [
    path("kitchen/export", KitchenExportView.as_view()),
    path("capabilities", CapabilitiesView.as_view()),
    path("pantry/captures", CaptureView.as_view()),
    path("pantry/captures/<int:pk>", JobView.as_view()),
    path("pantry", PantryView.as_view()),
    path("pantry/<int:pk>", PantryView.as_view()),
    path("preferences", PreferenceView.as_view()),
    path("pantry/matches", MatchView.as_view()),
    path("recipes/<int:recipe_id>/photos", PhotosView.as_view()),
    path("photos/<int:pk>/content", PhotoView.as_view()),
    path("photos/<int:pk>", PhotoView.as_view()),
]

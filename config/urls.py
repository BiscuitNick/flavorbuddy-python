"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

from .health import live, ready

urlpatterns = [
    path("api/integrations/v2/", include("integrations.urls_v2")),
    path("health/live", live),
    path("health/ready", ready),
    path("api/integrations/v1/", include("integrations.urls")),
    path("api/v1/", include("kitchen.urls")),
    path("api/v1/", include("scrape_me.api.urls")),
    path("admin/", admin.site.urls),
    path("", include("scrape_me.urls")),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG and settings.STARTER_IMAGE_STORAGE == "local":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

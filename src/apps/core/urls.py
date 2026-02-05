from django.contrib import admin
from django.urls import path, include

from . import views  # si aquí están api_pending_counts, api_live_status, etc.
from apps.core.views import home  # home inteligente (login -> bandeja)

urlpatterns = [
    # Home inteligente
    path("", home, name="home"),

    # Admin + Auth
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),

    # APIs (si realmente están en config/views.py)
    path("api/pending-counts/", views.api_pending_counts, name="api_pending_counts"),
    path("api/live-status/", views.api_live_status, name="api_live_status"),

    # Apps (asegúrate de tener estos includes en tus apps)
    path("", include("apps.core.urls")),          # aquí vive /bandeja/
    path("", include("apps.procurement.urls")),   # /cuadros/...
    path("", include("apps.payments.urls")),      # /ordenes/...
    path("", include("apps.catalog.urls")),       # /proveedores/, /productos/...
]


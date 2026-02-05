from django.urls import path
from . import views

urlpatterns = [
    # ✅ Home del sistema ("/")
    path("", views.home, name="home"),

    # ✅ Bandeja
    path("bandeja/", views.workbench, name="workbench"),

    # (Opcional) dashboard clásico
    path("dashboard/", views.dashboard, name="dashboard"),

    # APIs (si las estabas usando desde config)
    path("api/pending-counts/", views.api_pending_counts, name="api_pending_counts"),
    path("api/live-status/", views.api_live_status, name="api_live_status"),
]

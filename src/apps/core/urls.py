from django.urls import path
from .views import home

urlpatterns = [
    path("", home, name="home"),
]

from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    # === Live UI (polling) ===
    path("api/pending-counts/", views.api_pending_counts, name="api_pending_counts"),
    path("api/live-status/", views.api_live_status, name="api_live_status"),
]

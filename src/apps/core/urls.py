from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("api/pending-counts/", views.api_pending_counts, name="api_pending_counts"),
    path("api/live-status/", views.api_live_status, name="api_live_status"),
]

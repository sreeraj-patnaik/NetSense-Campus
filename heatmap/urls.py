from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("heatmap/", views.heatmap_view, name="heatmap_view"),
    path("scan/", views.scan_view, name="scan"),
    path("api/heatmap/", views.heatmap_api, name="heatmap_api"),
    path("api/scan/", views.scan_api, name="scan_api"),
    path("api/config/", views.config_api, name="config_api"),
]

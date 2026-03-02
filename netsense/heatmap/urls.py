from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("scan/", views.scan_view, name="scan"),
    path("api/heatmap/", views.heatmap_api, name="heatmap_api"),
]

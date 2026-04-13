from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("manifest.webmanifest", views.manifest_view, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("heatmap/", views.heatmap_view, name="heatmap_view"),
    path("architecture/", views.dti_view, name="dti"),
    path("project-structure/", views.project_structure_view, name="project_structure"),
    path("data-models-apis/", views.data_models_view, name="data_models"),
    path("workflow/", views.workflow_view, name="workflow"),
    path("scan/", views.scan_view, name="scan"),
    path("api/heatmap/", views.heatmap_api, name="heatmap_api"),
    path("api/scan/", views.scan_api, name="scan_api"),
    path("api/config/", views.config_api, name="config_api"),
    path("api/chatbot/", views.chatbot_api, name="chatbot_api"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("manifest.webmanifest", views.manifest_view, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("heatmap/", views.heatmap_view, name="heatmap_view"),
    path("dashboard/", views.heatmap_view, name="dashboard"),
    path("architecture/", views.dti_view, name="dti"),
    path("project-structure/", views.project_structure_view, name="project_structure"),
    path("data-models-apis/", views.data_models_view, name="data_models"),
    path("workflow/", views.workflow_view, name="workflow"),
    path("signup/", views.signup_view, name="signup"),
    path("institution-requests/", views.institution_requests_view, name="institution_requests"),
    path("scan/", views.scan_view, name="scan"),
    path("dashboard-preferences/", views.dashboard_preferences_view, name="dashboard_preferences"),
    path("api/heatmap/", views.heatmap_api, name="heatmap_api"),
    path("api/dashboard-insights/", views.dashboard_insights_api, name="dashboard_insights_api"),
    path("api/weak-clusters/", views.weak_clusters_api, name="weak_clusters_api"),
    path("api/best-provider/", views.best_provider_api, name="best_provider_api"),
    path("api/next-scan/", views.next_scan_api, name="next_scan_api"),
    path("api/scan/", views.scan_api, name="scan_api"),
    path("api/config/", views.config_api, name="config_api"),
    path("api/chatbot/", views.chatbot_api, name="chatbot_api"),
]

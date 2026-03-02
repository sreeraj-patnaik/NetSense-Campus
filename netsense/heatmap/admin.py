from django.contrib import admin

from .models import Scan


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "block",
        "floor",
        "cell_x",
        "cell_y",
        "mode",
        "network_name",
        "signal_strength",
        "created_at",
    )
    list_filter = ("block", "floor", "mode", "created_at")
    search_fields = ("network_name", "block")
    ordering = ("-created_at",)

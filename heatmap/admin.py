from django.contrib import admin

from .models import Block, FloorPlan, Scan


class FloorPlanInline(admin.TabularInline):
    model = FloorPlan
    extra = 1
    fields = ("number", "name", "grid_rows", "grid_cols", "image", "is_active")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    inlines = (FloorPlanInline,)


@admin.register(FloorPlan)
class FloorPlanAdmin(admin.ModelAdmin):
    list_display = ("block", "number", "name", "grid_rows", "grid_cols", "image", "is_active")
    list_filter = ("block", "is_active")
    search_fields = ("block__code", "name")
    ordering = ("block__code", "number")


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "block",
        "floor",
        "cell_x",
        "cell_y",
        "mode",
        "service_provider",
        "network_name",
        "signal_strength",
        "created_at",
    )
    list_filter = ("block", "floor", "mode", "service_provider", "created_at")
    search_fields = ("network_name", "service_provider", "block")
    ordering = ("-created_at",)

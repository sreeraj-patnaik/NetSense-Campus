from django.contrib import admin
from django.utils.html import format_html

from .models import Block, CellAggregate, FloorPlan, Scan, ServiceProvider


class FloorPlanInline(admin.TabularInline):
    model = FloorPlan
    extra = 0
    show_change_link = True
    fields = ("number", "name", "grid_rows", "grid_cols", "blocked_cells", "image", "image_preview", "is_active")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" style="max-height: 72px; border-radius: 4px;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Preview"


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    inlines = (FloorPlanInline,)


@admin.register(FloorPlan)
class FloorPlanAdmin(admin.ModelAdmin):
    list_display = ("block", "number", "name", "grid_rows", "grid_cols", "image_preview", "is_active")
    list_filter = ("block", "is_active")
    search_fields = ("block__code", "name")
    ordering = ("block__code", "number")
    list_editable = ("is_active",)
    fields = (
        "block",
        "number",
        "name",
        "grid_rows",
        "grid_cols",
        "blocked_cells",
        "image",
        "image_preview",
        "is_active",
    )
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" style="max-height: 120px; border-radius: 4px;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Preview"


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "floor_plan",
        "cell_x",
        "cell_y",
        "cell_id",
        "mode",
        "service_provider",
        "network_name",
        "signal_strength",
        "created_at",
    )
    list_filter = ("floor_plan", "mode", "service_provider", "created_at")
    search_fields = ("network_name", "service_provider", "floor_plan__block__code")
    ordering = ("-created_at",)


@admin.register(CellAggregate)
class CellAggregateAdmin(admin.ModelAdmin):
    list_display = (
        "floor_plan",
        "cell_x",
        "cell_y",
        "cell_id",
        "mode",
        "service_provider",
        "is_all_providers",
        "median_signal",
        "scan_count",
        "updated_at",
    )
    list_filter = ("floor_plan", "mode", "is_all_providers", "service_provider")
    search_fields = ("floor_plan__block__code", "service_provider")
    ordering = ("floor_plan__block__code", "floor_plan__number", "cell_y", "cell_x")


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "mode", "is_active", "created_at")
    list_filter = ("mode", "is_active")
    search_fields = ("name",)
    ordering = ("mode", "name")

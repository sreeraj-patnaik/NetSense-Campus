from django.contrib import admin
from django.utils.html import format_html

from .models import Block, FloorPlan, Scan


class FloorPlanInline(admin.TabularInline):
    model = FloorPlan
    extra = 0
    show_change_link = True
    fields = ("number", "name", "grid_rows", "grid_cols", "image", "image_preview", "is_active")
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
    fields = ("block", "number", "name", "grid_rows", "grid_cols", "image", "image_preview", "is_active")
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

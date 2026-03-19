from django.db import models


class Block(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}" if self.name else self.code


class FloorPlan(models.Model):
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="floors")
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=120, blank=True)
    grid_rows = models.PositiveIntegerField(default=12)
    grid_cols = models.PositiveIntegerField(default=8)
    image = models.ImageField(upload_to="floor_maps/", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["block__code", "number"]
        constraints = [
            models.UniqueConstraint(fields=["block", "number"], name="uniq_floorplan_block_number"),
        ]

    def __str__(self) -> str:
        label = self.name or f"Floor {self.number}"
        return f"{self.block.code} - {label}"


class Scan(models.Model):
    WIFI = "wifi"
    MOBILE = "mobile"

    MODE_CHOICES = [
        (WIFI, "WiFi"),
        (MOBILE, "Mobile"),
    ]

    block = models.CharField(max_length=10)
    floor = models.IntegerField()
    cell_x = models.IntegerField()
    cell_y = models.IntegerField()
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=WIFI)
    service_provider = models.CharField(max_length=60, blank=True)
    network_name = models.CharField(max_length=100, blank=True)
    signal_strength = models.IntegerField(help_text="Signal strength in dBm")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["block", "floor", "mode"]),
            models.Index(fields=["cell_x", "cell_y"]),
        ]

    def __str__(self) -> str:
        provider = f"{self.service_provider} " if self.service_provider else ""
        return (
            f"{self.block}-F{self.floor} ({self.cell_x},{self.cell_y}) "
            f"{self.mode} {provider}{self.signal_strength} dBm"
        )





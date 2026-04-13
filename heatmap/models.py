from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class Institution(models.Model):
    name = models.CharField(max_length=160, unique=True)
    code = models.CharField(max_length=40, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class InstitutionMembership(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    MEMBER = "member"
    ADMIN = "admin"

    ROLE_CHOICES = [
        (MEMBER, "Member"),
        (ADMIN, "Admin"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="institution_memberships")
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name="memberships")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default=MEMBER)
    can_scan = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "institution"], name="uniq_institution_membership"),
        ]

    def __str__(self) -> str:
        return f"{self.user} -> {self.institution} ({self.status})"


class Block(models.Model):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        related_name="blocks",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}" if self.name else self.code


class ServiceProvider(models.Model):
    WIFI = "wifi"
    MOBILE = "mobile"

    MODE_CHOICES = [
        (WIFI, "WiFi"),
        (MOBILE, "Mobile"),
    ]

    name = models.CharField(max_length=60)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=WIFI)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["mode", "name"]
        constraints = [
            models.UniqueConstraint(fields=["mode", "name"], name="uniq_service_provider_mode_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.mode})"


class FloorPlan(models.Model):
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="floors")
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=120, blank=True)
    grid_rows = models.PositiveIntegerField(default=12)
    grid_cols = models.PositiveIntegerField(default=8)
    blocked_cells = models.JSONField(default=list, blank=True)
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

    def blocked_cell_ids(self):
        ids = []
        cols = int(self.grid_cols or 1)
        for item in self.blocked_cells or []:
            if isinstance(item, int):
                ids.append(int(item))
                continue
            if isinstance(item, str):
                try:
                    ids.append(int(item))
                except ValueError:
                    continue
                continue
            if isinstance(item, (list, tuple)) and len(item) == 2:
                try:
                    cell_x = int(item[0])
                    cell_y = int(item[1])
                except (TypeError, ValueError):
                    continue
                ids.append(cell_y * cols + cell_x)
                continue
            if isinstance(item, dict):
                if "cell_id" in item:
                    try:
                        ids.append(int(item["cell_id"]))
                    except (TypeError, ValueError):
                        continue
                elif "cell_x" in item and "cell_y" in item:
                    try:
                        cell_x = int(item["cell_x"])
                        cell_y = int(item["cell_y"])
                    except (TypeError, ValueError):
                        continue
                    ids.append(cell_y * cols + cell_x)
        return ids


class Scan(models.Model):
    WIFI = "wifi"
    MOBILE = "mobile"

    MODE_CHOICES = [
        (WIFI, "WiFi"),
        (MOBILE, "Mobile"),
    ]

    floor_plan = models.ForeignKey(FloorPlan, on_delete=models.CASCADE, related_name="scans")
    cell_x = models.IntegerField()
    cell_y = models.IntegerField()
    cell_id = models.IntegerField()
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=WIFI)
    service_provider = models.CharField(max_length=60, blank=True)
    network_name = models.CharField(max_length=100, blank=True)
    signal_strength = models.IntegerField(help_text="Signal strength in dBm")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["floor_plan", "mode"]),
            models.Index(fields=["cell_x", "cell_y"]),
            models.Index(fields=["cell_id"]),
        ]

    def __str__(self) -> str:
        provider = f"{self.service_provider} " if self.service_provider else ""
        return (
            f"{self.block_code}-F{self.floor_number} ({self.cell_x},{self.cell_y}) "
            f"{self.mode} {provider}{self.signal_strength} dBm"
        )

    @property
    def block_code(self):
        return self.floor_plan.block.code if self.floor_plan_id else ""

    @property
    def floor_number(self):
        return self.floor_plan.number if self.floor_plan_id else None

    def save(self, *args, **kwargs):
        if self.floor_plan_id:
            self.cell_id = int(self.cell_y) * int(self.floor_plan.grid_cols) + int(self.cell_x)
        super().save(*args, **kwargs)


class CellAggregate(models.Model):
    floor_plan = models.ForeignKey(FloorPlan, on_delete=models.CASCADE, related_name="aggregates")
    cell_x = models.IntegerField()
    cell_y = models.IntegerField()
    cell_id = models.IntegerField()
    mode = models.CharField(max_length=10, choices=Scan.MODE_CHOICES, default=Scan.WIFI)
    service_provider = models.CharField(max_length=60, blank=True)
    is_all_providers = models.BooleanField(default=False)
    median_signal = models.FloatField()
    signal_variance = models.FloatField(default=0)
    scan_count = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["floor_plan__block__code", "floor_plan__number", "cell_y", "cell_x"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "floor_plan",
                    "cell_x",
                    "cell_y",
                    "mode",
                    "service_provider",
                    "is_all_providers",
                ],
                name="uniq_cellaggregate_key",
            ),
        ]
        indexes = [
            models.Index(fields=["floor_plan", "mode", "is_all_providers"]),
            models.Index(fields=["cell_x", "cell_y"]),
            models.Index(fields=["cell_id"]),
        ]

    def __str__(self) -> str:
        provider = "all" if self.is_all_providers else (self.service_provider or "unknown")
        block_code = self.floor_plan.block.code if self.floor_plan_id else ""
        floor_number = self.floor_plan.number if self.floor_plan_id else ""
        return f"{block_code}-F{floor_number} ({self.cell_x},{self.cell_y}) {self.mode} {provider}"







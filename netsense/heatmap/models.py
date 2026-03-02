from django.db import models


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
        return (
            f"{self.block}-F{self.floor} ({self.cell_x},{self.cell_y}) "
            f"{self.mode} {self.signal_strength} dBm"
        )

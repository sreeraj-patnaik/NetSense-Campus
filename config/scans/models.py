from django.db import models

# Create your models here.
from core.models import Block, Floor

class ScanRawWifi(models.Model):
    block = models.ForeignKey(Block, on_delete=models.CASCADE)
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    ssid = models.CharField(max_length=255)
    bssid = models.CharField(max_length=255)
    rssi = models.IntegerField()
    frequency = models.IntegerField()
    device_id = models.CharField(max_length=255)
    def __str__(self):
        return f"{self.block.name} - {self.floor.number} - {self.ssid} ({self.bssid}) at {self.timestamp}"
    
class ScanRawMobile(models.Model):

    floor = models.ForeignKey(Floor, on_delete=models.CASCADE)

    cell_id = models.IntegerField()

    provider = models.CharField(max_length=50)
    network_type = models.CharField(max_length=10)

    signal_strength = models.IntegerField()

    device_id = models.CharField(max_length=100)

    timestamp = models.DateTimeField()

    def __str__(self):
        return f"{self.floor.block.name} - {self.floor.number} - Cell {self.cell_id} ({self.provider} {self.network_type}) at {self.timestamp}"
    
    
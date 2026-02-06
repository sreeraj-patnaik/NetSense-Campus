

from django.db import models

# Create your models here.

from django.db import models
from core.models import Floor

class ScanRawWiFi(models.Model):

    floor = models.ForeignKey(Floor, on_delete=models.CASCADE)

    cell_id = models.IntegerField()

    ssid = models.CharField(max_length=100)
    bssid = models.CharField(max_length=50)

    rssi = models.IntegerField()
    frequency = models.IntegerField()

    timestamp = models.DateTimeField()
    device_id = models.CharField(max_length=100)

class ScanRawMobile(models.Model):

    floor = models.ForeignKey(Floor, on_delete=models.CASCADE)

    cell_id = models.IntegerField()

    provider = models.CharField(max_length=50)
    network_type = models.CharField(max_length=10)

    signal_strength = models.IntegerField()

    timestamp = models.DateTimeField()
    device_id = models.CharField(max_length=100)
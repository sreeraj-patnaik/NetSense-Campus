from rest_framework import serializers
from .models import ScanRawWiFi, ScanRawMobile
from core.models import Floor

class WiFiScanSerializer(serializers.ModelSerializer):

    class Meta:
        model = ScanRawWiFi
        fields = "__all__"

class MobileScanSerializer(serializers.ModelSerializer):

    class Meta:
        model = ScanRawMobile
        fields = "__all__"
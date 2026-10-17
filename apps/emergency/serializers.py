from rest_framework import serializers
from .models import EmergencyRecord


class EmergencyRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyRecord
        fields = '__all__'

from rest_framework import serializers
from .models import ReportsRecord


class ReportsRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportsRecord
        fields = '__all__'

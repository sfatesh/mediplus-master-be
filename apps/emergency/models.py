from django.db import models
from apps.common.models import TimeStampedModel


class EmergencyRecord(TimeStampedModel):
    """Foundational domain entity for emergency."""
    reference_code = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=50, default='ACTIVE', db_index=True)

    class Meta:
        managed = False
        db_table = 'domain_emergency'
        verbose_name = 'Emergency Record'
        verbose_name_plural = 'Emergency Records'

    def __str__(self):
        return f"{self.reference_code} ({self.status})"


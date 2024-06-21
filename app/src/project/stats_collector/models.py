from django.db import models

from ..core.models import Validator


class ValidatorSystemEvent(models.Model):
    type = models.CharField(max_length=255, db_index=True)
    subtype = models.CharField(max_length=255, db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    data = models.JSONField()
    validator = models.ForeignKey(Validator, on_delete=models.CASCADE, db_index=True)

    def __str__(self) -> str:
        return f"SystemEvent({self.id}, {self.validator.ss58_address}, {self.type}, {self.subtype})"

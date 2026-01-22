from django.db import models

class DocumentSequence(models.Model):
    doc_type = models.CharField(max_length=10)  # "CC" o "OP"
    year = models.IntegerField()
    last_number = models.IntegerField(default=0)

    class Meta:
        unique_together = ("doc_type", "year")

    def __str__(self):
        return f"{self.doc_type}-{self.year}: {self.last_number}"

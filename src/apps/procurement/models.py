from django.db import models, transaction
from django.conf import settings
from django.utils import timezone

from apps.core.models import DocumentSequence
from apps.catalog.models import Provider, Product


def next_document_number(doc_type: str) -> str:
    year = timezone.now().year
    with transaction.atomic():
        seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
            doc_type=doc_type,
            year=year,
            defaults={"last_number": 0},
        )
        seq.last_number += 1
        seq.save()
        return f"{doc_type}-{year}-{seq.last_number:06d}"


class ComparativeQuote(models.Model):
    class Status(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        EN_REVISION = "EN_REVISION", "En revisión"   # (en UI lo mostraremos como Pendiente)
        REVISADO = "REVISADO", "Revisado"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    number = models.CharField(max_length=20, unique=True, blank=True)
    item_cotizado = models.CharField(max_length=200)
    proyecto = models.CharField(max_length=200)
    expresado_en = models.CharField(max_length=50, default="Bolivianos")

    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cc_creados")
    creado_en = models.DateTimeField(auto_now_add=True)

    # Revisión (rol revisor)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="cc_revisados",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)

    # Aprobación final (rol aprobador)
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="cc_aprobados",
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)

    estado = models.CharField(max_length=20, choices=Status.choices, default=Status.BORRADOR)

    proveedor_seleccionado = models.ForeignKey(
        "procurement.ComparativeSupplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seleccionado_en",
    )

    motivo_seleccion = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_document_number("CC")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number


class ComparativeItem(models.Model):
    cuadro = models.ForeignKey(ComparativeQuote, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Product, on_delete=models.PROTECT)
    unidad = models.CharField(max_length=30, default="Und")
    cantidad = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("cuadro", "producto")

    def __str__(self):
        return f"{self.cuadro.number} - {self.producto.nombre}"


class ComparativeSupplier(models.Model):
    cuadro = models.ForeignKey(ComparativeQuote, on_delete=models.CASCADE, related_name="proveedores")
    proveedor = models.ForeignKey(Provider, on_delete=models.PROTECT)
    detalle = models.CharField(max_length=250, blank=True)

    class Meta:
        unique_together = ("cuadro", "proveedor")

    def __str__(self):
        return f"{self.cuadro.number} - {self.proveedor.nombre_empresa}"


class ComparativePrice(models.Model):
    cuadro = models.ForeignKey(ComparativeQuote, on_delete=models.CASCADE, related_name="precios")
    proveedor = models.ForeignKey(Provider, on_delete=models.PROTECT)
    producto = models.ForeignKey(Product, on_delete=models.PROTECT)
    precio_unit = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("cuadro", "proveedor", "producto")

    def __str__(self):
        return f"{self.cuadro.number} - {self.proveedor} - {self.producto}"

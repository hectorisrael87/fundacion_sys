from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

from apps.catalog.models import Provider, Product
from apps.procurement.models import ComparativeQuote, next_document_number


class PaymentOrder(models.Model):
    class Status(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        EN_REVISION = "EN_REVISION", "En revisión"
        REVISADO = "REVISADO", "Revisado"
        APROBADO = "APROBADO", "Aprobado"

    number = models.CharField(max_length=30, unique=True, blank=True)

    cuadro = models.ForeignKey(
        ComparativeQuote, on_delete=models.PROTECT, related_name="ordenes_pago"
    )
    proveedor = models.ForeignKey(
        Provider, on_delete=models.PROTECT, related_name="ordenes_pago"
    )

    para = models.CharField(max_length=200, blank=True)
    cargo_para = models.CharField(max_length=200, blank=True)
    de = models.CharField(max_length=200, blank=True)
    cargo_de = models.CharField(max_length=200, blank=True)

    fecha_solicitud = models.DateField(default=timezone.localdate)
    proyecto = models.CharField(max_length=200, blank=True)
    partida_contable = models.CharField(max_length=200, blank=True)
    con_factura = models.CharField(max_length=50, blank=True)
    efectivo = models.CharField(max_length=50, blank=True)
    descripcion = models.TextField(blank=True)

    es_parcial = models.BooleanField(default=False)
    monto_manual = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    pago_parcial_de = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="complementos",
    )

    estado = models.CharField(
        max_length=20, choices=Status.choices, default=Status.BORRADOR
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="op_creadas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    # ✅ Nuevo: registro de revisión
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="op_revisadas",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)

    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="op_aprobadas",
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_document_number("OP")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number


class PaymentOrderItem(models.Model):
    orden = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Product, on_delete=models.PROTECT)

    unidad = models.CharField(max_length=30, blank=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_unit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    from decimal import Decimal

    @property
    def subtotal(self):
        return (self.cantidad or Decimal("0")) * (self.precio_unit or Decimal("0"))

    def __str__(self):
        return f"{self.orden.number} - {self.producto.nombre}"

# ...imports...
from django.conf import settings
from django.db import models

class PaymentOrder(models.Model):
    class Status(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        EN_REVISION = "EN_REVISION", "En revisión"
        REVISADO = "REVISADO", "Revisado"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"  # ✅ nuevo

    estado = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.BORRADOR,
    )

    # ...campos existentes...
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="op_revisadas",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)

    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="op_aprobadas",
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)

    # ✅ nuevos (rechazo)
    rechazado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="op_rechazadas",
    )
    rechazado_en = models.DateTimeField(null=True, blank=True)

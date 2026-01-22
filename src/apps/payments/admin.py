from django.contrib import admin
from .models import PaymentOrder, PaymentOrderItem


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "proveedor", "monto_a_pagar", "estado", "creado_en")
    list_filter = ("estado",)
    search_fields = ("number", "proveedor__nombre_empresa")

    def monto_a_pagar(self, obj):
        return obj.monto_manual if obj.monto_manual is not None else "-"
    monto_a_pagar.short_description = "Monto a pagar"


@admin.register(PaymentOrderItem)
class PaymentOrderItemAdmin(admin.ModelAdmin):
    list_display = ("orden", "producto", "cantidad", "precio_unit")
    search_fields = ("orden__number", "producto__nombre")

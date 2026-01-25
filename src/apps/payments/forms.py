from django import forms
from django.utils import timezone

from .models import PaymentOrder


class PaymentOrderForm(forms.ModelForm):
    class Meta:
        model = PaymentOrder
        fields = [
            "para", "cargo_para",
            "de", "cargo_de",
            "fecha_solicitud",
            "proyecto",
            "partida_contable",
            "con_factura",
            "efectivo",
            "descripcion",
            "es_parcial",
            "monto_manual",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Defaults editables (solo si el campo está vacío)
        if not self.initial.get("para") and getattr(self.instance, "para", "") == "":
            self.initial["para"] = "Maria Teresa Vargas"
        if not self.initial.get("cargo_para") and getattr(self.instance, "cargo_para", "") == "":
            self.initial["cargo_para"] = "Directora Ejecutiva"

        if not self.initial.get("proyecto") and getattr(self.instance, "proyecto", "") == "":
            self.initial["proyecto"] = "Uso Contable"
        if not self.initial.get("partida_contable") and getattr(self.instance, "partida_contable", "") == "":
            self.initial["partida_contable"] = "Uso Contable"

        if not self.initial.get("con_factura") and getattr(self.instance, "con_factura", "") == "":
            self.initial["con_factura"] = "Si"
        if not self.initial.get("efectivo") and getattr(self.instance, "efectivo", "") == "":
            self.initial["efectivo"] = "No"

        # Fecha por defecto si está vacío
        if not self.initial.get("fecha_solicitud") and getattr(self.instance, "fecha_solicitud", None) is None:
            self.initial["fecha_solicitud"] = timezone.localdate()

                # UI: clases reutilizables (evitar estilos inline)
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput, forms.RadioSelect)):
                continue

            existing = w.attrs.get("class", "")
            w.attrs["class"] = (existing + " control").strip()


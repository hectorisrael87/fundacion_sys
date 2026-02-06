from django import forms
from .models import ComparativeQuote, ComparativeItem, ComparativeSupplier, ComparativeQuoteAttachment
from apps.catalog.models import Product

def _add_control(form: forms.Form):
    for field in form.fields.values():
        w = field.widget
        if isinstance(w, (forms.CheckboxInput, forms.RadioSelect)):
            continue
        existing = w.attrs.get("class", "")
        w.attrs["class"] = (existing + " control").strip()


class ComparativeQuoteForm(forms.ModelForm):
    class Meta:
        model = ComparativeQuote
        fields = ["item_cotizado", "proyecto", "expresado_en"]
        widgets = {
            "item_cotizado": forms.TextInput(attrs={"class": "control"}),
            "proyecto": forms.TextInput(attrs={"class": "control"}),
            "expresado_en": forms.TextInput(attrs={"class": "control"}),
        }

class ComparativeItemForm(forms.ModelForm):
    class Meta:
        model = ComparativeItem
        fields = ["producto", "unidad", "cantidad"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_control(self)

        # ✅ Solo productos activos
        self.fields["producto"].queryset = Product.objects.filter(activo=True).order_by("nombre")

class ComparativeSupplierForm(forms.ModelForm):
    class Meta:
        model = ComparativeSupplier
        fields = ["proveedor", "detalle"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_control(self)


class ComparativeSelectionForm(forms.ModelForm):
    class Meta:
        model = ComparativeQuote
        fields = ["proveedor_seleccionado", "motivo_seleccion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_control(self)


class ComparativeAttachmentForm(forms.ModelForm):
    class Meta:
        model = ComparativeQuoteAttachment
        fields = ["archivo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_control(self)
        self.fields["archivo"].widget.attrs["class"] = "control control-file"

        # opcional: hint
        self.fields["archivo"].help_text = "Adjunta cotizaciones (PDF/imagen)."

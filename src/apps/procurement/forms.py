from django import forms
from .models import ComparativeQuote

class ComparativeQuoteForm(forms.ModelForm):
    class Meta:
        model = ComparativeQuote
        fields = ["item_cotizado", "proyecto", "expresado_en"]
        widgets = {
            "item_cotizado": forms.TextInput(attrs={"class": "input"}),
            "proyecto": forms.TextInput(attrs={"class": "input"}),
            "expresado_en": forms.TextInput(attrs={"class": "input"}),
        }
from .models import ComparativeItem, ComparativeSupplier

class ComparativeItemForm(forms.ModelForm):
    class Meta:
        model = ComparativeItem
        fields = ["producto", "unidad", "cantidad"]

class ComparativeSupplierForm(forms.ModelForm):
    class Meta:
        model = ComparativeSupplier
        fields = ["proveedor", "detalle"]

from .models import ComparativeQuote, ComparativeSupplier

class ComparativeSelectionForm(forms.ModelForm):
    class Meta:
        model = ComparativeQuote
        fields = ["proveedor_seleccionado", "motivo_seleccion"]


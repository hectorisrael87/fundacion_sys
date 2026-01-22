from django import forms
from .models import Provider

class ProviderForm(forms.ModelForm):
    class Meta:
        model = Provider
        exclude = ["codigo"]
        fields = [
            "codigo", "nombre_empresa", "direccion", "telefono",
            "datos_transferencia", "entidad", "nro_cuenta",
            "ci", "nit", "descripcion", "activo",
        ]
from django import forms
from .models import Provider, Product

class ProviderForm(forms.ModelForm):
    class Meta:
        model = Provider
        exclude = ["codigo"]  # como ya definimos


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["nombre", "unidad", "activo"]

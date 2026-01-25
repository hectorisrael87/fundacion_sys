from django import forms
from .models import Provider, Product


def _add_control(form: forms.Form):
    for field in form.fields.values():
        w = field.widget
        # no aplicar a checkbox/radio (se ven mejor nativos)
        if isinstance(w, (forms.CheckboxInput, forms.RadioSelect)):
            continue
        existing = w.attrs.get("class", "")
        w.attrs["class"] = (existing + " control").strip()


class ProviderForm(forms.ModelForm):
    class Meta:
        model = Provider
        # No editamos "codigo" (se asume autogenerado)
        fields = [
            "nombre_empresa",
            "direccion",
            "telefono",
            "datos_transferencia",
            "entidad",
            "nro_cuenta",
            "ci",
            "nit",
            "descripcion",
            "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_control(self)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["nombre", "unidad", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _add_control(self)

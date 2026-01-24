from django.urls import path
from .views import provider_create, provider_edit, product_create, provider_list

urlpatterns = [
    path("proveedores/nuevo/", provider_create, name="provider_create"),
    path("proveedores/<int:pk>/editar/", provider_edit, name="provider_edit"),
    path("productos/nuevo/", product_create, name="product_create"),
    path("proveedores/", provider_list, name="provider_list"),
]

from django.urls import path
from . import views

urlpatterns = [
    path("proveedores/nuevo/", views.provider_create, name="provider_create"),
    path("proveedores/<int:pk>/editar/", views.provider_edit, name="provider_edit"),
    path("proveedores/", views.provider_list, name="provider_list"),

    path("productos/nuevo/", views.product_create, name="product_create"),
    path("productos/<int:pk>/editar/", views.product_edit, name="product_edit"),
    path("productos/<int:pk>/eliminar/", views.product_delete, name="product_delete"),
]

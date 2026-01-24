from django.urls import path
from .views import provider_create
from .views import provider_create, product_create
from .views import provider_list


urlpatterns = [
    path("proveedores/nuevo/", provider_create, name="provider_create"),
    path("productos/nuevo/", product_create, name="product_create"),
    path("proveedores/", provider_list, name="provider_list"),

]

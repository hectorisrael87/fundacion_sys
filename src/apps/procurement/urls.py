from django.urls import path
from . import views

from .views import (
    cc_list,
    cc_create,
    cc_detail,
    cc_add_item,
    cc_add_supplier,
    cc_prices,
    cc_select_supplier,
    cc_send_review,
    cc_approve,
    cc_back_to_draft,
    cc_generate_ops,
    cc_edit_item,
    cc_delete_item,
    cc_edit_supplier,
    cc_delete_supplier,
    cc_print,
)

urlpatterns = [
    # Cuadros comparativos
    path("cuadros/", cc_list, name="cc_list"),
    path("cuadros/nuevo/", cc_create, name="cc_create"),
    path("cuadros/<int:pk>/", cc_detail, name="cc_detail"),

    # Productos
    path("cuadros/<int:pk>/producto/", cc_add_item, name="cc_add_item"),
    path("cuadros/<int:pk>/items/<int:item_id>/editar/", cc_edit_item, name="cc_edit_item"),
    path("cuadros/<int:pk>/items/<int:item_id>/eliminar/", cc_delete_item, name="cc_delete_item"),

    # Proveedores
    path("cuadros/<int:pk>/proveedor/", cc_add_supplier, name="cc_add_supplier"),
    path("cuadros/<int:pk>/proveedores/<int:supplier_id>/editar/", cc_edit_supplier, name="cc_edit_supplier"),
    path("cuadros/<int:pk>/proveedores/<int:supplier_id>/eliminar/", cc_delete_supplier, name="cc_delete_supplier"),

    # Precios
    path("cuadros/<int:pk>/precios/", cc_prices, name="cc_prices"),

    # Selección y flujo
    path("cuadros/<int:pk>/seleccionar/", cc_select_supplier, name="cc_select_supplier"),
    path("cuadros/<int:pk>/enviar-revision/", cc_send_review, name="cc_send_review"),
    path("cuadros/<int:pk>/aprobar/", cc_approve, name="cc_approve"),
    path("cuadros/<int:pk>/borrador/", cc_back_to_draft, name="cc_back_to_draft"),

    # Órdenes de pago
    path("cuadros/<int:pk>/generar-ops/", cc_generate_ops, name="cc_generate_ops"),
    path("cuadros/<int:pk>/imprimir/", cc_print, name="cc_print"),
    
]

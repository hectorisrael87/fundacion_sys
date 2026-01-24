from django.urls import path
from apps.procurement import views

from apps.procurement.views import (
    cc_list,
    cc_create,
    cc_detail,
    cc_add_item,
    cc_add_supplier,
    cc_prices,          # ✅ IMPORTA DIRECTO
    cc_select_supplier,
    cc_send_review,
    cc_back_to_draft,
    cc_generate_ops,
    cc_print,
    cc_edit_item,
    cc_delete_item,
    cc_edit_supplier,
    cc_delete_supplier,
)

urlpatterns = [
    path("cuadros/", cc_list, name="cc_list"),
    path("cuadros/nuevo/", cc_create, name="cc_create"),
    path("cuadros/<int:pk>/", cc_detail, name="cc_detail"),

    path("cuadros/<int:pk>/producto/", cc_add_item, name="cc_add_item"),
    path("cuadros/<int:pk>/proveedor/", cc_add_supplier, name="cc_add_supplier"),

    path("cuadros/<int:pk>/precios/", cc_prices, name="cc_prices"),  # ✅ ya no usa views.cc_prices

    path("cuadros/<int:pk>/seleccionar/", cc_select_supplier, name="cc_select_supplier"),
    path("cuadros/<int:pk>/enviar-revision/", cc_send_review, name="cc_send_review"),
    path("cuadros/<int:pk>/borrador/", cc_back_to_draft, name="cc_back_to_draft"),

    path("cuadros/<int:pk>/generar-ops/", cc_generate_ops, name="cc_generate_ops"),

    path("cuadros/<int:pk>/items/<int:item_id>/editar/", cc_edit_item, name="cc_edit_item"),
    path("cuadros/<int:pk>/items/<int:item_id>/eliminar/", cc_delete_item, name="cc_delete_item"),

    path("cuadros/<int:pk>/proveedores/<int:supplier_id>/editar/", cc_edit_supplier, name="cc_edit_supplier"),
    path("cuadros/<int:pk>/proveedores/<int:supplier_id>/eliminar/", cc_delete_supplier, name="cc_delete_supplier"),

    path("cuadros/<int:pk>/imprimir/", cc_print, name="cc_print"),
]

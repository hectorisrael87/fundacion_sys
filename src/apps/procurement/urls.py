from django.urls import path
from . import views

urlpatterns = [
    # Cuadros comparativos
    path("cuadros/", views.cc_list, name="cc_list"),
    path("cuadros/nuevo/", views.cc_create, name="cc_create"),
    path("cuadros/<int:pk>/", views.cc_detail, name="cc_detail"),

    # Agregar productos y proveedores
    path("cuadros/<int:pk>/producto/", views.cc_add_item, name="cc_add_item"),
    path("cuadros/<int:pk>/proveedor/", views.cc_add_supplier, name="cc_add_supplier"),

    # Matriz de precios
    path("cuadros/<int:pk>/precios/", views.cc_prices, name="cc_prices"),

    # Selección / flujo
    path("cuadros/<int:pk>/seleccionar/", views.cc_select_supplier, name="cc_select_supplier"),
    path("cuadros/<int:pk>/enviar-revision/", views.cc_send_review, name="cc_send_review"),
    path("cuadros/<int:pk>/aprobar/", views.cc_approve, name="cc_approve"),
    path("cuadros/<int:pk>/borrador/", views.cc_back_to_draft, name="cc_back_to_draft"),

    # Generar OPs
    path("cuadros/<int:pk>/generar-ops/", views.cc_generate_ops, name="cc_generate_ops"),

    # ✅ Editar/Eliminar ítems
    path("cuadros/<int:pk>/items/<int:item_id>/editar/", views.cc_edit_item, name="cc_edit_item"),
    path("cuadros/<int:pk>/items/<int:item_id>/eliminar/", views.cc_delete_item, name="cc_delete_item"),

    # ✅ Editar/Eliminar proveedores
    path("cuadros/<int:pk>/proveedores/<int:supplier_id>/editar/", views.cc_edit_supplier, name="cc_edit_supplier"),
    path("cuadros/<int:pk>/proveedores/<int:supplier_id>/eliminar/", views.cc_delete_supplier, name="cc_delete_supplier"),

    # (si ya implementaste el print)
    path("cuadros/<int:pk>/imprimir/", views.cc_print, name="cc_print"),
]

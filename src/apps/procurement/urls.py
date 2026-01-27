from django.urls import path

from apps.procurement.views import (
    cc_list,
    cc_create,
    cc_detail,
    cc_add_item,
    cc_add_supplier,
    cc_prices,
    cc_select_supplier,

    # flujo
    cc_send_review,
    cc_mark_reviewed,
    cc_back_to_review,
    cc_approve_final,
    cc_back_to_draft,
    cc_reject,

    # ops / print
    cc_generate_ops,
    cc_print,

    # editar/eliminar
    cc_edit_item,
    cc_delete_item,
    cc_edit_supplier,
    cc_delete_supplier,

    # eliminar cuadro
    cc_delete,

    # editar cabecera
    cc_edit_header,

    # adjuntos
    cc_attachment_upload,
    cc_attachment_delete,
)

urlpatterns = [
    path("cuadros/", cc_list, name="cc_list"),
    path("cuadros/nuevo/", cc_create, name="cc_create"),
    path("cuadros/<int:pk>/", cc_detail, name="cc_detail"),

    # editar cabecera (Item/Proyecto/Expresado en)
    path("cuadros/<int:pk>/editar/", cc_edit_header, name="cc_edit_header"),

    # eliminar cuadro (listado)
    path("cuadros/<int:pk>/eliminar/", cc_delete, name="cc_delete"),

    # productos/proveedores
    path("cuadros/<int:pk>/producto/", cc_add_item, name="cc_add_item"),
    path("cuadros/<int:pk>/proveedor/", cc_add_supplier, name="cc_add_supplier"),

    # matriz precios
    path("cuadros/<int:pk>/precios/", cc_prices, name="cc_prices"),

    # seleccionar proveedor
    path("cuadros/<int:pk>/seleccionar/", cc_select_supplier, name="cc_select_supplier"),

    # adjuntos (cotizaciones)
    path("cuadros/<int:pk>/adjuntos/upload/", cc_attachment_upload, name="cc_attachment_upload"),
    path("cuadros/<int:pk>/adjuntos/<int:att_id>/eliminar/", cc_attachment_delete, name="cc_attachment_delete"),

    # flujo
    path("cuadros/<int:pk>/enviar-revision/", cc_send_review, name="cc_send_review"),
    path("cuadros/<int:pk>/marcar-revisado/", cc_mark_reviewed, name="cc_mark_reviewed"),
    path("cuadros/<int:pk>/devolver-revision/", cc_back_to_review, name="cc_back_to_review"),
    path("cuadros/<int:pk>/aprobar/", cc_approve_final, name="cc_approve_final"),
    path("cuadros/<int:pk>/rechazar/", cc_reject, name="cc_reject"),
    path("cuadros/<int:pk>/borrador/", cc_back_to_draft, name="cc_back_to_draft"),

    # generar ops
    path("cuadros/<int:pk>/generar-ops/", cc_generate_ops, name="cc_generate_ops"),

    # editar/eliminar items
    path("cuadros/<int:pk>/items/<int:item_id>/editar/", cc_edit_item, name="cc_edit_item"),
    path("cuadros/<int:pk>/items/<int:item_id>/eliminar/", cc_delete_item, name="cc_delete_item"),

    # editar/eliminar proveedores del cuadro
    path("cuadros/<int:pk>/proveedores/<int:supplier_id>/editar/", cc_edit_supplier, name="cc_edit_supplier"),
    path("cuadros/<int:pk>/proveedores/<int:supplier_id>/eliminar/", cc_delete_supplier, name="cc_delete_supplier"),

    # imprimir
    path("cuadros/<int:pk>/imprimir/", cc_print, name="cc_print"),
]

from django.urls import path
from . import views

urlpatterns = [
    path("ordenes/", views.op_list, name="op_list"),
    path("ordenes/<int:pk>/", views.op_detail, name="op_detail"),

    # flujo
    path("<int:pk>/send-review/", views.op_send_review, name="op_send_review"),
    path("<int:pk>/mark-reviewed/", views.op_mark_reviewed, name="op_mark_reviewed"),
    path("<int:pk>/approve/", views.op_approve, name="op_approve"),
    path("<int:pk>/back-to-draft/", views.op_back_to_draft, name="op_back_to_draft"),
    path("<int:pk>/back-to-review/", views.op_back_to_review, name="op_back_to_review"),
    path("<int:pk>/reject/", views.op_reject, name="op_reject"),

    # imprimir
    path("ordenes/<int:pk>/imprimir/", views.op_print, name="op_print"),

    # pago complementario (anticipo)
    path(
        "ordenes/<int:pk>/complemento/",
        views.op_create_complement,
        name="op_create_complement",
    ),
    # eliminar
    path("ordenes/<int:pk>/eliminar/", views.op_delete, name="op_delete"),
]

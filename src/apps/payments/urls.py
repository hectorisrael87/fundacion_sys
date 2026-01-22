from django.urls import path
from . import views

urlpatterns = [
    path("ordenes/", views.op_list, name="op_list"),
    path("ordenes/<int:pk>/", views.op_detail, name="op_detail"),

    # flujo
    path("ordenes/<int:pk>/enviar/", views.op_send_review, name="op_send_review"),
    path("ordenes/<int:pk>/aprobar/", views.op_approve, name="op_approve"),
    path("ordenes/<int:pk>/borrador/", views.op_back_to_draft, name="op_back_to_draft"),

    # imprimir
    path("ordenes/<int:pk>/imprimir/", views.op_print, name="op_print"),

    # pago complementario (anticipo)
    path(
        "ordenes/<int:pk>/complemento/",
        views.op_create_complement,
        name="op_create_complement",
    ),
]

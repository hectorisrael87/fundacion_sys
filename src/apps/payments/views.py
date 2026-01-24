from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.permissions import is_creator, is_reviewer, is_approver

from .forms import PaymentOrderForm
from .models import PaymentOrder


@login_required
def op_list(request):
    qs = PaymentOrder.objects.select_related(
        "creado_por", "revisado_por", "aprobado_por", "proveedor", "cuadro"
    ).order_by("-creado_en")

    # Visibilidad:
    # - Revisor/Aprobador/Superuser: ven todo
    # - Creador: ve solo lo suyo
    if not (
        request.user.is_superuser
        or is_reviewer(request.user)
        or is_approver(request.user)
    ):
        qs = qs.filter(creado_por=request.user)

    return render(
        request,
        "payments/op_list.html",
        {
            "ordenes": qs,
            "is_reviewer": (request.user.is_superuser or is_reviewer(request.user)),
            "is_approver": (request.user.is_superuser or is_approver(request.user)),
        },
    )


@login_required
def op_detail(request, pk: int):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # Lectura:
    # - creador (dueño), revisor, aprobador o superuser
    if not (
        request.user.is_superuser
        or is_reviewer(request.user)
        or is_approver(request.user)
        or op.creado_por_id == request.user.id
    ):
        return HttpResponseForbidden("No tienes permiso para ver esta Orden de Pago.")

    # Edición: SOLO creador (o superuser) y SOLO en BORRADOR
    puede_editar = (
        (request.user.is_superuser or op.creado_por_id == request.user.id)
        and op.estado == PaymentOrder.Status.BORRADOR
    )

    if request.method == "POST":
        if not puede_editar:
            return HttpResponseForbidden("No tienes permiso para editar esta Orden de Pago.")

        form = PaymentOrderForm(request.POST, instance=op)
        if form.is_valid():
            form.save()
            messages.success(request, "Orden de Pago actualizada.")
            return redirect("op_detail", pk=op.pk)
    else:
        form = PaymentOrderForm(instance=op)

    # Totales (no tocar lógica si ya la tienes en template/print)
    total_items = Decimal("0")
    for it in op.items.all():
        total_items += (it.cantidad or Decimal("0")) * (it.precio_unit or Decimal("0"))

    # Monto mostrado (respeta parcial/manual existente)
    monto_total = op.monto_manual if op.monto_manual is not None else total_items

    return render(
        request,
        "payments/op_detail.html",
        {
            "op": op,
            "form": form,
            "items": op.items.select_related("producto").all(),
            "monto_total": monto_total,
            "puede_editar": puede_editar,
            "is_reviewer": (request.user.is_superuser or is_reviewer(request.user)),
            "is_approver": (request.user.is_superuser or is_approver(request.user)),
        },
    )


# =========================
# FLUJO: BORRADOR -> EN_REVISION -> REVISADO -> APROBADO
# =========================

@login_required
def op_send_review(request, pk: int):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # Solo creador (o superuser) puede enviar a revisión
    if not (request.user.is_superuser or op.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para enviar esta OP a revisión.")

    # No puede moverse si ya está aprobada
    if op.estado == PaymentOrder.Status.APROBADO:
        messages.error(request, "La OP ya está aprobada y no puede volver a revisión.")
        return redirect("op_detail", pk=pk)

    if op.estado != PaymentOrder.Status.BORRADOR:
        messages.error(request, "Solo se puede enviar a revisión una OP en estado BORRADOR.")
        return redirect("op_detail", pk=pk)

    op.estado = PaymentOrder.Status.EN_REVISION
    op.revisado_por = None
    op.revisado_en = None
    op.aprobado_por = None
    op.aprobado_en = None
    op.save(update_fields=["estado", "revisado_por", "revisado_en", "aprobado_por", "aprobado_en"])

    messages.success(request, "OP enviada a revisión.")
    return redirect("op_detail", pk=pk)


@login_required
def op_mark_reviewed(request, pk: int):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # Solo revisor (o superuser)
    if not (request.user.is_superuser or is_reviewer(request.user)):
        return HttpResponseForbidden("No tienes permiso para revisar.")

    # Creador no puede revisar su propia OP
    if op.creado_por_id == request.user.id and not request.user.is_superuser:
        return HttpResponseForbidden("No puedes revisar una OP que tú creaste.")

    # Debe estar EN_REVISION
    if op.estado != PaymentOrder.Status.EN_REVISION:
        messages.error(request, "La OP no está en revisión.")
        return redirect("op_detail", pk=pk)

    op.estado = PaymentOrder.Status.REVISADO
    op.revisado_por = request.user
    op.revisado_en = timezone.now()
    # No tocamos aprobado aquí (debe estar vacío)
    op.save(update_fields=["estado", "revisado_por", "revisado_en"])

    messages.success(request, "OP marcada como revisada.")
    return redirect("op_detail", pk=pk)


@login_required
def op_approve(request, pk: int):
    """
    Se mantiene el nombre por compatibilidad con tus URLs/templates existentes.
    Ahora APRUEBA DEFINITIVAMENTE y solo lo hace el APROBADOR (o superuser),
    y solo si la OP está REVISADA.
    """
    op = get_object_or_404(PaymentOrder, pk=pk)

    # Solo aprobador (o superuser)
    if not (request.user.is_superuser or is_approver(request.user)):
        return HttpResponseForbidden("No tienes permiso para aprobar.")

    # Creador no puede aprobar su propia OP
    if op.creado_por_id == request.user.id and not request.user.is_superuser:
        return HttpResponseForbidden("No puedes aprobar una OP que tú creaste.")

    # No permitir re-aprobación
    if op.estado == PaymentOrder.Status.APROBADO:
        messages.error(request, "La OP ya está aprobada.")
        return redirect("op_detail", pk=pk)

    # Debe estar REVISADO
    if op.estado != PaymentOrder.Status.REVISADO:
        messages.error(request, "Solo se puede aprobar una OP en estado REVISADO.")
        return redirect("op_detail", pk=pk)

    op.estado = PaymentOrder.Status.APROBADO
    op.aprobado_por = request.user
    op.aprobado_en = timezone.now()
    op.save(update_fields=["estado", "aprobado_por", "aprobado_en"])

    messages.success(request, "OP aprobada.")
    return redirect("op_detail", pk=pk)


@login_required
def op_back_to_draft(request, pk: int):
    """
    Se mantiene para compatibilidad.
    Ahora SOLO permite devolver EN_REVISION -> BORRADOR (revisor/superuser).
    Nunca permite volver atrás si está REVISADO o APROBADO.
    """
    op = get_object_or_404(PaymentOrder, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user)):
        return HttpResponseForbidden("No tienes permiso para devolver a borrador.")

    if op.estado == PaymentOrder.Status.APROBADO:
        messages.error(request, "La OP está aprobada y no puede volver a borrador.")
        return redirect("op_detail", pk=pk)

    if op.estado != PaymentOrder.Status.EN_REVISION:
        messages.error(request, "Solo se puede devolver a borrador una OP en EN_REVISION.")
        return redirect("op_detail", pk=pk)

    op.estado = PaymentOrder.Status.BORRADOR
    op.revisado_por = None
    op.revisado_en = None
    op.aprobado_por = None
    op.aprobado_en = None
    op.save(update_fields=["estado", "revisado_por", "revisado_en", "aprobado_por", "aprobado_en"])

    messages.success(request, "OP devuelta a borrador.")
    return redirect("op_detail", pk=pk)

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.permissions import is_reviewer
from apps.core.utils import monto_en_letras

from .forms import PaymentOrderForm
from .models import PaymentOrder


@login_required
def op_list(request):
    ops = (
        PaymentOrder.objects.select_related("cuadro", "proveedor", "creado_por", "aprobado_por")
        .order_by("-creado_en")
    )

    # Creador ve lo suyo; revisor y superuser ven todo
    if not (request.user.is_superuser or is_reviewer(request.user)):
        ops = ops.filter(creado_por=request.user)

    return render(request, "payments/op_list.html", {"ops": ops})


@login_required
def op_detail(request, pk):
    op = get_object_or_404(
        PaymentOrder.objects.select_related("cuadro", "proveedor", "creado_por", "aprobado_por"),
        pk=pk,
    )

    # seguridad: creador ve lo suyo; revisor y superuser ven todo
    if not (request.user.is_superuser or is_reviewer(request.user) or op.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para ver esta orden.")

    # bloquear edición si APROBADO (solo admin puede)
    puede_editar = True
    if op.estado == "APROBADO" and not request.user.is_superuser:
        puede_editar = False

    # POST = editar en la misma pantalla
    if request.method == "POST":
        if not puede_editar:
            return HttpResponseForbidden("La orden está aprobada y no se puede editar.")

        form = PaymentOrderForm(request.POST, instance=op)
        if form.is_valid():
            form.save()
            messages.success(request, "Orden actualizada.")
            return redirect("op_detail", pk=op.pk)
    else:
        form = PaymentOrderForm(instance=op)

    items = op.items.select_related("producto").all()

    total_calc = Decimal("0")
    for it in items:
        total_calc += (it.cantidad * it.precio_unit)

    # monto a pagar = monto_manual si existe, sino total calculado
    monto_a_pagar = op.monto_manual if op.monto_manual is not None else total_calc

    # lógica de parcial/complemento
    complementos_qs = op.complementos.all()  # related_name="complementos"
    complemento = complementos_qs.first()

    restante = None
    if op.monto_manual is not None:
        restante = total_calc - (op.monto_manual or Decimal("0"))

    puede_crear_complemento = (
        (op.es_parcial is True)                 # marcado como parcial
        and (op.monto_manual is not None)       # tiene anticipo
        and (restante is not None and restante > 0)  # hay saldo
        and (complemento is None)               # aún no existe complemento
    )

    return render(
        request,
        "payments/op_detail.html",
        {
            "op": op,
            "form": form,
            "items": items,
            "total": total_calc,
            "monto_a_pagar": monto_a_pagar,
            "monto_letras": monto_en_letras(monto_a_pagar),
            "is_reviewer": (request.user.is_superuser or is_reviewer(request.user)),
            "puede_editar": puede_editar,
            # parcial / complemento
            "restante": restante,
            "puede_crear_complemento": puede_crear_complemento,
            "complemento": complemento,
        },
    )


@login_required
def op_print(request, pk):
    op = get_object_or_404(PaymentOrder, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or op.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para ver esta orden.")

    items = op.items.select_related("producto").all()

    total_calc = Decimal("0")
    for it in items:
        total_calc += (it.cantidad * it.precio_unit)

    monto_a_pagar = op.monto_manual if op.monto_manual is not None else total_calc

    return render(
        request,
        "payments/op_print.html",
        {
            "op": op,
            "items": items,
            "total": total_calc,
            "monto_a_pagar": monto_a_pagar,
            "monto_letras": monto_en_letras(monto_a_pagar),
            "is_reviewer": (request.user.is_superuser or is_reviewer(request.user)),
        },
    )


# -------------------------
# Flujo de aprobación (OP)
# -------------------------

@login_required
def op_send_review(request, pk):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # Solo creador o superuser
    if not (request.user.is_superuser or op.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para enviar esta orden a revisión.")

    op.estado = "EN_REVISION"
    op.save(update_fields=["estado"])
    messages.success(request, "Orden enviada a revisión.")
    return redirect("op_detail", pk=pk)


@login_required
def op_approve(request, pk):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # Solo revisor o superuser
    if not (request.user.is_superuser or is_reviewer(request.user)):
        return HttpResponseForbidden("No tienes permiso para aprobar.")

    # Regla: el creador no aprueba (excepto superuser)
    if (not request.user.is_superuser) and (op.creado_por_id == request.user.id):
        return HttpResponseForbidden("No puedes aprobar una orden que tú creaste.")

    op.estado = "APROBADO"
    op.aprobado_por = request.user
    op.aprobado_en = timezone.now()
    op.save(update_fields=["estado", "aprobado_por", "aprobado_en"])
    messages.success(request, "Orden aprobada.")
    return redirect("op_detail", pk=pk)


@login_required
def op_back_to_draft(request, pk):
    op = get_object_or_404(PaymentOrder, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user)):
        return HttpResponseForbidden("No tienes permiso para devolver.")

    op.estado = "BORRADOR"
    op.aprobado_por = None
    op.aprobado_en = None
    op.save(update_fields=["estado", "aprobado_por", "aprobado_en"])
    messages.success(request, "Orden devuelta a borrador.")
    return redirect("op_detail", pk=pk)


# ---------------------------------------
# Mantener compatibilidad con urls op_edit
# (pero toda la edición es en op_detail)
# ---------------------------------------
@login_required
def op_edit(request, pk):
    return redirect("op_detail", pk=pk)


# -------------------------
# Pago complementario
# -------------------------
@login_required
def op_create_complement(request, pk):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # seguridad: creador, revisor o admin
    if not (request.user.is_superuser or is_reviewer(request.user) or op.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para esta acción.")

    # Debe ser una OP parcial
    if not op.es_parcial or op.monto_manual is None:
        messages.error(request, "Esta orden no está marcada como pago parcial o no tiene monto solicitado.")
        return redirect("op_detail", pk=op.pk)

    items = list(op.items.all())
    total_calc = sum((it.cantidad * it.precio_unit) for it in items) or Decimal("0")
    ya_solicitado = op.monto_manual or Decimal("0")
    restante = total_calc - ya_solicitado

    if restante <= 0:
        messages.error(request, "No hay monto restante para complementar.")
        return redirect("op_detail", pk=op.pk)

    # si ya existe complemento, no duplicar
    existente = op.complementos.first()
    if existente:
        messages.info(request, f"Ya existe un complemento: {existente.number}")
        return redirect("op_detail", pk=existente.pk)

    nueva = PaymentOrder.objects.create(
        cuadro=op.cuadro,
        proveedor=op.proveedor,
        para=op.para,
        cargo_para=op.cargo_para,
        de=op.de,
        cargo_de=op.cargo_de,
        fecha_solicitud=timezone.localdate(),
        proyecto=op.proyecto,
        partida_contable=op.partida_contable,
        con_factura=op.con_factura,
        efectivo=op.efectivo,
        descripcion=f"Complemento de {op.number}. {op.descripcion or ''}".strip(),
        creado_por=request.user,
        monto_manual=restante,      # lo que falta pagar
        es_parcial=False,           # complemento = pago final
        pago_parcial_de=op,         # link a la parcial
    )

    for it in items:
        nueva.items.create(
            producto=it.producto,
            unidad=it.unidad,
            cantidad=it.cantidad,
            precio_unit=it.precio_unit,
        )

    messages.success(request, f"Complemento creado: {nueva.number}")
    return redirect("op_detail", pk=nueva.pk)

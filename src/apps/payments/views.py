from collections import defaultdict
from decimal import Decimal
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from apps.core.permissions import is_reviewer, is_approver
from apps.core.utils import monto_en_letras

from .forms import PaymentOrderForm
from .models import PaymentOrder, PaymentOrderItem

@login_required
def op_list(request):
    qs = (
        PaymentOrder.objects.select_related(
            "creado_por", "revisado_por", "aprobado_por", "proveedor", "cuadro"
        )
        .prefetch_related("items__producto")
        .order_by("-creado_en")
    )

    is_rev = (request.user.is_superuser or is_reviewer(request.user))
    is_app = (request.user.is_superuser or is_approver(request.user))

    # Visibilidad:
    # - Superuser: ve todo (incluye borradores de cualquiera)
    # - Revisor/Aprobador: ve todo EXCEPTO borradores ajenos (solo ve sus borradores)
    # - Creador sin rol: ve solo lo suyo
    if request.user.is_superuser:
        pass
    elif is_rev or is_app:
        qs = qs.filter(
            Q(estado__in=[
                PaymentOrder.Status.EN_REVISION,
                PaymentOrder.Status.REVISADO,
                PaymentOrder.Status.APROBADO,
            ]) | Q(creado_por=request.user)
        )
    else:
        qs = qs.filter(creado_por=request.user)

    # Tabs (filtros)
    status = (request.GET.get("status") or "all").lower()

    if status in ("draft", "borrador"):
        # Para revisor/aprobador esto mostrará SOLO sus borradores (por la regla de visibilidad)
        qs = qs.filter(estado=PaymentOrder.Status.BORRADOR)

    elif status in ("pending", "pendiente"):
        # Pendiente significa "lo que te toca":
        # - Revisor: EN_REVISION
        # - Aprobador: REVISADO
        # - Creador: EN_REVISION o REVISADO
        if is_rev and not is_app:
            qs = qs.filter(estado=PaymentOrder.Status.EN_REVISION)
        elif is_app and not is_rev:
            qs = qs.filter(estado=PaymentOrder.Status.REVISADO)
        else:
            qs = qs.filter(
                estado__in=[PaymentOrder.Status.EN_REVISION, PaymentOrder.Status.REVISADO]
            )

    elif status in ("approved", "aprobado"):
        qs = qs.filter(estado=PaymentOrder.Status.APROBADO)

    else:
        status = "all"

    return render(
        request,
        "payments/op_list.html",
        {
            "ordenes": qs,
            "is_reviewer": is_rev,
            "is_approver": is_app,
            "status": status,
        },
    )


@login_required
def op_detail(request, pk: int):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # =========================
    # Navegación guiada desde CC: OP1 -> OP2 -> ... -> volver al CC
    # =========================
    return_cc_pk = None
    next_op_pk = None

    raw_return_cc = request.GET.get("return_cc") or request.POST.get("return_cc")
    if raw_return_cc and raw_return_cc.isdigit():
        return_cc_pk = int(raw_return_cc)

        # seguridad: solo si coincide con el CC real de esta OP
        if op.cuadro_id == return_cc_pk:
            op_ids = list(
                op.cuadro.ordenes_pago.order_by("id").values_list("id", flat=True)
            )
            try:
                idx = op_ids.index(op.id)
                if idx < len(op_ids) - 1:
                    next_op_pk = op_ids[idx + 1]
            except ValueError:
                pass

            # ✅ Círculo de lectura (APROBADOR): al entrar por GET desde el CC, marcamos sesión
            if (request.user.is_superuser or is_approver(request.user)) and not is_reviewer(request.user):
                request.session[f"cc_seen_ops_{return_cc_pk}"] = True
                request.session.modified = True
        else:
            # si no coincide, ignoramos navegación
            return_cc_pk = None
            next_op_pk = None



    # Si está en BORRADOR, solo el creador o superuser pueden verlo
    if op.estado == PaymentOrder.Status.BORRADOR and not (
        request.user.is_superuser or op.creado_por_id == request.user.id
    ):
        messages.error(request, "Esta OP está en borrador y aún no está disponible para revisión.")
        return redirect("op_list")

    # Lectura:
    # - creador (dueño), revisor, aprobador o superuser
    if not (
        request.user.is_superuser
        or is_reviewer(request.user)
        or is_approver(request.user)
        or op.creado_por_id == request.user.id
    ):
        return HttpResponseForbidden("No tienes permiso para ver esta Orden de Pago.")

    # Edición:
    # - Creador (o superuser): SOLO en BORRADOR
    # - Revisor (o superuser): SOLO en EN_REVISION (para correcciones)
    # - Aprobador: NO edita (solo aprueba cuando está REVISADO)
    puede_editar = (
        request.user.is_superuser
        or (
            op.estado == PaymentOrder.Status.BORRADOR
            and op.creado_por_id == request.user.id
        )
        or (
            op.estado == PaymentOrder.Status.EN_REVISION
            and is_reviewer(request.user)
            and op.creado_por_id != request.user.id
        )
    )

    # Items (para totales)
    items_qs = op.items.select_related("producto").all()

    # Total calculado (por ítems)
    total = Decimal("0")
    for it in items_qs:
        total += (it.cantidad or Decimal("0")) * (it.precio_unit or Decimal("0"))

    # Total calculado para mostrar como "Monto solicitado" en OP normal (no vacío)
    total_calculado = total

    # Monto a pagar (respeta monto_manual)
    monto_a_pagar = op.monto_manual if op.monto_manual is not None else total
    monto_letras = monto_en_letras(monto_a_pagar)

    # Pago parcial / complemento
    restante = None
    complemento = None

    if op.es_parcial:
        restante = total - monto_a_pagar
        if restante < 0:
            restante = Decimal("0")
        complemento = op.complementos.order_by("-creado_en").first()

    puede_crear_complemento = (
        (request.user.is_superuser or op.creado_por_id == request.user.id)
        and op.es_parcial
        and (restante is not None and restante > 0)
        and complemento is None
        and op.estado == PaymentOrder.Status.APROBADO
    )
    # =========================
    # Guardar / Guardar y enviar a revisión
    # =========================
    if request.method == "POST":
        if not puede_editar:
            return HttpResponseForbidden("No tienes permiso para editar esta Orden de Pago.")

        action = request.POST.get("action", "save")  # save | send_review | save_next | save_return_cc

        form = PaymentOrderForm(request.POST, instance=op)
        if form.is_valid():
            form.save()
            messages.success(request, "Orden de Pago actualizada.")

            # ✅ Si estamos en círculo, mantenemos la marca (por si edita/corrige)
            if return_cc_pk and op.cuadro_id == return_cc_pk:
                if (request.user.is_superuser or is_approver(request.user)) and not is_reviewer(request.user):
                    request.session[f"cc_seen_ops_{return_cc_pk}"] = True
                    request.session.modified = True

            # 1) Guardar y enviar a revisión (solo si NO estás en círculo)
            if action == "send_review":
                if return_cc_pk:
                    messages.error(
                        request,
                        "Esta OP se está completando desde el Cuadro. Envía a revisión desde el Cuadro."
                    )
                    return redirect(f"{reverse('op_detail', kwargs={'pk': op.pk})}?return_cc={return_cc_pk}")
                return redirect("op_send_review", pk=op.pk)

            # 2) Guardar y siguiente OP (círculo)
            if action == "save_next":
                nxt = request.POST.get("next_op_pk")
                if nxt and nxt.isdigit():
                    if return_cc_pk:
                        return redirect(f"{reverse('op_detail', kwargs={'pk': int(nxt)})}?return_cc={return_cc_pk}")
                    return redirect("op_detail", pk=int(nxt))

            # 3) Guardar y volver al cuadro (círculo)
            if action == "save_return_cc":
                if return_cc_pk and op.cuadro_id == return_cc_pk:
                    return redirect("cc_detail", pk=return_cc_pk)

            # 4) Guardar normal (preservando return_cc si aplica)
            if return_cc_pk:
                return redirect(f"{reverse('op_detail', kwargs={'pk': op.pk})}?return_cc={return_cc_pk}")
            return redirect("op_detail", pk=op.pk)

        # si no es válido cae al render con errores
    else:
        form = PaymentOrderForm(instance=op)

    return render(
        request,
        "payments/op_detail.html",
        {
            "op": op,
            "form": form,
            "items": items_qs,
            "total": total,
            "total_calculado": total_calculado,  # ✅ para OP normal (Monto solicitado)
            "monto_a_pagar": monto_a_pagar,
            "monto_letras": monto_letras,
            "restante": restante,
            "complemento": complemento,
            "puede_crear_complemento": puede_crear_complemento,
            "puede_editar": puede_editar,
            "is_reviewer": (request.user.is_superuser or is_reviewer(request.user)),
            "is_approver": (request.user.is_superuser or is_approver(request.user)),
            "return_cc_pk": return_cc_pk,
            "next_op_pk": next_op_pk,         
        },
    )


# =========================
# FLUJO: BORRADOR -> EN_REVISION -> REVISADO -> APROBADO
# =========================

@login_required
def op_send_review(request, pk: int):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # ✅ Si esta OP pertenece a un CC que aún está en flujo, no se envía sola.
    if op.cuadro_id:
        cc_estado = getattr(op.cuadro, "estado", None)
        if cc_estado in {"BORRADOR", "EN_REVISION", "REVISADO"}:
            messages.error(
                request,
                "Esta Orden pertenece a un Cuadro en flujo. Envíala a revisión desde el Cuadro Comparativo."
            )
            return redirect("cc_detail", pk=op.cuadro_id)

    return_cc = request.GET.get("return_cc") or request.POST.get("return_cc")
    return_cc_pk = int(return_cc) if (return_cc and return_cc.isdigit()) else None

    # Solo creador (o superuser) puede enviar a revisión
    if not (request.user.is_superuser or op.creado_por_id == request.user.id):
        messages.error(request, "No tienes permiso para enviar esta OP a revisión.")
        return redirect("op_detail", pk=pk)

    if op.estado == PaymentOrder.Status.APROBADO:
        messages.error(request, "La OP ya está aprobada y no puede volver a revisión.")
        return redirect("op_detail", pk=op.pk)

    if op.estado not in {PaymentOrder.Status.BORRADOR, PaymentOrder.Status.RECHAZADO}:
        messages.error(request, "Solo puedes enviar a revisión desde Borrador o Rechazado.")
        return redirect("op_detail", pk=op.pk)

    errores = []

    if not (op.descripcion or "").strip():
        errores.append("Debes registrar la DESCRIPCIÓN antes de enviar a revisión.")

    items = list(op.items.all())
    total = Decimal("0")
    for it in items:
        total += (it.cantidad or Decimal("0")) * (it.precio_unit or Decimal("0"))

    if op.es_parcial:
        if op.monto_manual is None:
            errores.append("Esta OP es PAGO PARCIAL: debes registrar el MONTO antes de enviar a revisión.")
        else:
            if op.monto_manual <= 0:
                errores.append("El MONTO del pago parcial debe ser mayor a 0.")
            if total > 0 and op.monto_manual > total:
                errores.append("El MONTO del pago parcial no puede ser mayor al TOTAL de la orden.")
    else:
        if total <= 0 and op.monto_manual is None:
            errores.append("Debes tener ítems con total mayor a 0 o registrar un MONTO antes de enviar a revisión.")

    if errores:
        for e in errores:
            messages.error(request, e)
        if return_cc_pk:
            return redirect(f"{reverse('op_detail', kwargs={'pk': op.pk})}?return_cc={return_cc_pk}")
        return redirect("op_detail", pk=op.pk)

    op.estado = PaymentOrder.Status.EN_REVISION
    op.revisado_por = None
    op.revisado_en = None
    op.aprobado_por = None
    op.aprobado_en = None
    op.rechazado_por = None
    op.rechazado_en = None
    op.save(update_fields=[
        "estado",
        "revisado_por", "revisado_en",
        "aprobado_por", "aprobado_en",
        "rechazado_por", "rechazado_en",
    ])

    messages.success(request, "OP enviada a revisión.")

    if return_cc_pk and op.cuadro_id == return_cc_pk:
        return redirect("cc_detail", pk=return_cc_pk)

    return redirect("op_detail", pk=op.pk)

@login_required
def op_mark_reviewed(request, pk: int):
    op = get_object_or_404(PaymentOrder, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user)):
        return HttpResponseForbidden("No tienes permiso para revisar.")

    if op.creado_por_id == request.user.id and not request.user.is_superuser:
        return HttpResponseForbidden("No puedes revisar una OP que tú creaste.")

    if op.estado != PaymentOrder.Status.EN_REVISION:
        messages.error(request, "La OP no está en revisión.")
        return redirect("op_detail", pk=pk)

    return_cc = request.GET.get("return_cc")
    return_cc_pk = int(return_cc) if (return_cc and return_cc.isdigit()) else None

    op.estado = PaymentOrder.Status.REVISADO
    op.revisado_por = request.user
    op.revisado_en = timezone.now()
    op.save(update_fields=["estado", "revisado_por", "revisado_en"])

    messages.success(request, "OP marcada como revisada.")

    # ✅ Círculo: si venías desde CC, ir a la siguiente OP o volver al CC
    if return_cc_pk and op.cuadro_id == return_cc_pk:
        op_ids = list(op.cuadro.ordenes_pago.order_by("id").values_list("id", flat=True))
        try:
            idx = op_ids.index(op.id)
            if idx < len(op_ids) - 1:
                next_op_pk = op_ids[idx + 1]
                return redirect(f"{reverse('op_detail', kwargs={'pk': next_op_pk})}?return_cc={return_cc_pk}")
        except ValueError:
            pass
        return redirect("cc_detail", pk=return_cc_pk)

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


# =========================
# IMPRIMIR
# =========================

@login_required
def op_print(request, pk: int):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # Permiso de impresión: creador, reviewer, approver o superuser
    if not (
        request.user.is_superuser
        or is_reviewer(request.user)
        or is_approver(request.user)
        or op.creado_por_id == request.user.id
    ):
        return HttpResponseForbidden("No tienes permiso para ver esta Orden de Pago.")

    items = list(op.items.select_related("producto").all())

    total = Decimal("0")
    for it in items:
        total += (it.cantidad or Decimal("0")) * (it.precio_unit or Decimal("0"))

    monto_a_pagar = op.monto_manual if op.monto_manual is not None else total
    monto_letras = monto_en_letras(monto_a_pagar)

    return render(
        request,
        "payments/op_print.html",
        {
            "op": op,
            "items": items,
            "total": total,
            "monto_a_pagar": monto_a_pagar,
            "monto_letras": monto_letras,
        },
    )

@login_required
def op_delete(request, pk: int):
    op = get_object_or_404(PaymentOrder, pk=pk)

    # Solo creador o superuser
    if not (request.user.is_superuser or op.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para eliminar esta Orden de Pago.")

    # Solo se elimina en BORRADOR (salvo superuser)
    if op.estado != PaymentOrder.Status.BORRADOR and not request.user.is_superuser:
        return HttpResponseForbidden("Solo se puede eliminar una OP en BORRADOR.")

    if request.method == "POST":
        num = op.number
        op.delete()
        messages.success(request, f"Orden eliminada: {num}")
        return redirect("op_list")

    # Si alguien entra por GET, lo devolvemos al detalle
    return redirect("op_detail", pk=pk)

# =========================
# PAGO COMPLEMENTARIO (ANTICIPO)
# =========================

@login_required
def op_create_complement(request, pk: int):
    """
    Crea una OP complemento (restante) a partir de una OP parcial (anticipo).
    Mantiene la lógica existente: mismo cuadro, proveedor y copia de ítems;
    monto_manual = restante.
    """
    base = get_object_or_404(PaymentOrder, pk=pk)

    # Solo el creador (o superuser) puede crear complemento
    if not (request.user.is_superuser or base.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para crear un complemento de esta OP.")

    if not base.es_parcial:
        messages.error(request, "Esta OP no es un pago parcial (anticipo).")
        return redirect("op_detail", pk=base.pk)

    if base.estado != PaymentOrder.Status.APROBADO:
        messages.error(request, "Solo puedes crear el complemento cuando el anticipo está APROBADO.")
        return redirect("op_detail", pk=base.pk)

    existente = base.complementos.order_by("-creado_en").first()
    if existente:
        messages.info(request, "Ya existe un complemento para este anticipo.")
        return redirect("op_detail", pk=existente.pk)

    items_base = list(base.items.select_related("producto").all())

    total = Decimal("0")
    for it in items_base:
        total += (it.cantidad or Decimal("0")) * (it.precio_unit or Decimal("0"))

    monto_base = base.monto_manual if base.monto_manual is not None else total
    restante = total - monto_base
    if restante <= 0:
        messages.error(request, "No hay restante para crear complemento.")
        return redirect("op_detail", pk=base.pk)

    with transaction.atomic():
        op = PaymentOrder.objects.create(
            cuadro=base.cuadro,
            proveedor=base.proveedor,
            para=base.para,
            cargo_para=base.cargo_para,
            de=base.de,
            cargo_de=base.cargo_de,
            fecha_solicitud=timezone.localdate(),
            proyecto=base.proyecto,
            partida_contable=base.partida_contable,
            con_factura=base.con_factura,
            efectivo=base.efectivo,
            descripcion=base.descripcion,
            es_parcial=False,
            monto_manual=restante,
            pago_parcial_de=base,
            estado=PaymentOrder.Status.BORRADOR,
            creado_por=request.user,
        )

        PaymentOrderItem.objects.bulk_create(
            [
                PaymentOrderItem(
                    orden=op,
                    producto=it.producto,
                    unidad=it.unidad,
                    cantidad=it.cantidad,
                    precio_unit=it.precio_unit,
                )
                for it in items_base
            ]
        )

    messages.success(request, f"Complemento creado: {op.number}")
    return redirect("op_detail", pk=op.pk)

@login_required
def op_back_to_review(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    op = get_object_or_404(PaymentOrder, pk=pk)
    user = request.user

    if not (user.is_superuser or is_approver(user)):
        return HttpResponseForbidden("No tiene permisos para devolver a revisión.")

    if op.estado != PaymentOrder.Status.REVISADO:
        messages.error(request, "Solo puedes devolver a revisión una OP en estado 'Revisado'.")
        return redirect("op_detail", pk=op.pk)

    if (not user.is_superuser) and op.creado_por_id == user.id:
        messages.error(request, "No puedes devolver a revisión tu propia OP.")
        return redirect("op_detail", pk=op.pk)

    op.estado = PaymentOrder.Status.EN_REVISION
    op.aprobado_por = None
    op.aprobado_en = None
    op.save(update_fields=["estado", "aprobado_por", "aprobado_en"])

    messages.success(request, "OP devuelta a revisión.")
    return redirect("op_detail", pk=op.pk)
@login_required
def op_reject(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    op = get_object_or_404(PaymentOrder, pk=pk)
    user = request.user

    if not (user.is_superuser or is_approver(user)):
        return HttpResponseForbidden("No tiene permisos para rechazar.")

    if op.estado != PaymentOrder.Status.REVISADO:
        messages.error(request, "Solo se puede rechazar una OP en estado 'Revisado'.")
        return redirect("op_detail", pk=op.pk)

    if (not user.is_superuser) and op.creado_por_id == user.id:
        messages.error(request, "No puedes rechazar tu propia OP.")
        return redirect("op_detail", pk=op.pk)

    op.estado = PaymentOrder.Status.RECHAZADO
    op.rechazado_por = user
    op.rechazado_en = timezone.now()
    op.aprobado_por = None
    op.aprobado_en = None
    op.save(update_fields=["estado", "rechazado_por", "rechazado_en", "aprobado_por", "aprobado_en"])

    messages.success(request, "OP rechazada.")
    return redirect("op_detail", pk=op.pk)

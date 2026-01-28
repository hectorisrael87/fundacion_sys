from collections import defaultdict
from decimal import Decimal
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.catalog.models import Provider
from apps.core.permissions import is_creator, is_reviewer, is_approver
from apps.payments.models import PaymentOrder, PaymentOrderItem
from django.db.models.deletion import ProtectedError


from .forms import (
    ComparativeItemForm,
    ComparativeQuoteForm,
    ComparativeSelectionForm,
    ComparativeSupplierForm,
    ComparativeAttachmentForm,
)
from .models import ComparativeQuote, ComparativeQuoteAttachment


LOCKED_CC_STATES = {ComparativeQuote.Status.APROBADO, ComparativeQuote.Status.RECHAZADO}

def _can_edit_cc(user, cc: ComparativeQuote) -> bool:
    # ✅ aprobador (solo aprobador) NO edita nunca
    return user.is_superuser or is_reviewer(user) or (cc.creado_por_id == user.id)


@login_required
def cc_list(request):
    qs = ComparativeQuote.objects.select_related(
        "creado_por", "revisado_por", "aprobado_por"
    ).order_by("-creado_en")

    is_rev = (request.user.is_superuser or is_reviewer(request.user))
    is_app = (request.user.is_superuser or is_approver(request.user))

    # Visibilidad:
    # - Revisor/Aprobador/Superuser: ven todo EXCEPTO BORRADORES de otros usuarios.
    # - Creador (sin rol): ve solo lo suyo.
    if is_rev or is_app:
        qs = qs.filter(
            Q(estado__in=[
                ComparativeQuote.Status.EN_REVISION,
                ComparativeQuote.Status.REVISADO,
                ComparativeQuote.Status.APROBADO,
            ]) | Q(creado_por=request.user)
        )
    else:
        qs = qs.filter(creado_por=request.user)

    # Tabs (filtros)
    status = (request.GET.get("status") or "all").lower()

    if status in ("draft", "borrador"):
        # Para revisor/aprobador esto mostrará SOLO sus borradores (por la regla de visibilidad)
        qs = qs.filter(estado=ComparativeQuote.Status.BORRADOR)

    elif status in ("pending", "pendiente"):
        if is_rev and not is_app:
            qs = qs.filter(estado=ComparativeQuote.Status.EN_REVISION)
        elif is_app and not is_rev:
            qs = qs.filter(estado=ComparativeQuote.Status.REVISADO)
        else:
            qs = qs.filter(
                estado__in=[ComparativeQuote.Status.EN_REVISION, ComparativeQuote.Status.REVISADO]
            )

    elif status in ("approved", "aprobado"):
        qs = qs.filter(estado=ComparativeQuote.Status.APROBADO)

    else:
        status = "all"

    return render(
        request,
        "procurement/cc_list.html",
        {
            "cuadros": qs,
            "is_reviewer": is_rev,
            "is_approver": is_app,
            "status": status,
        },
    )




@login_required
def cc_create(request):
    if not is_creator(request.user):
        return HttpResponseForbidden("No tienes permiso para crear cuadros.")

    if request.method == "POST":
        form = ComparativeQuoteForm(request.POST)
        if form.is_valid():
            cc = form.save(commit=False)
            cc.creado_por = request.user
            cc.save()
            messages.success(request, f"Cuadro creado: {cc.number}")
            return redirect("cc_detail", pk=cc.pk)
    else:
        form = ComparativeQuoteForm()

    return render(request, "procurement/cc_form.html", {"form": form})

@login_required
def cc_edit_header(request, pk: int):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    # Solo creador o revisor (o superuser)
    if not (
        request.user.is_superuser
        or is_reviewer(request.user)
        or cc.creado_por_id == request.user.id
    ):
        messages.error(request, "No tienes permiso para editar la cabecera de este cuadro.")
        return redirect("cc_detail", pk=pk)

    # Si está aprobado: no se puede editar (excepto superuser)
    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        messages.error(request, "Este cuadro está APROBADO: la cabecera está bloqueada.")
        return redirect("cc_detail", pk=pk)

    if request.method == "POST":
        form = ComparativeQuoteForm(request.POST, instance=cc)
        if form.is_valid():
            form.save()
            messages.success(request, "Cabecera actualizada.")
            return redirect("cc_detail", pk=pk)
    else:
        form = ComparativeQuoteForm(instance=cc)

    return render(request, "procurement/cc_edit_header.html", {"cc": cc, "form": form})

@login_required
def cc_detail(request, pk: int):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    user = request.user
    is_rev = (user.is_superuser or is_reviewer(user))
    is_app = (user.is_superuser or is_approver(user))

    # Si está en BORRADOR, solo el creador o superuser pueden verlo
    if cc.estado == ComparativeQuote.Status.BORRADOR and not (
        user.is_superuser or cc.creado_por_id == user.id
    ):
        messages.error(request, "Este cuadro está en borrador y aún no está disponible para revisión.")
        return redirect("cc_list")

    # Permiso de lectura (evita acceso por URL directa)
    if not (
        user.is_superuser
        or is_reviewer(user)
        or is_approver(user)
        or cc.creado_por_id == user.id
    ):
        return HttpResponseForbidden("No tienes permiso para ver este cuadro.")

    items = list(cc.items.select_related("producto").all())
    proveedores = list(cc.proveedores.select_related("proveedor").all())

    precios = defaultdict(dict)
    for p in cc.precios.all():
        precios[p.proveedor_id][p.producto_id] = p.precio_unit

    totales_por_proveedor = {}
    for ps in proveedores:
        prov_id = ps.proveedor_id
        total = Decimal("0")
        for it in items:
            precio_unit = precios.get(prov_id, {}).get(it.producto_id)
            if precio_unit is not None:
                total += (it.cantidad * precio_unit)
        totales_por_proveedor[str(prov_id)] = total

    total_general = sum(totales_por_proveedor.values(), Decimal("0"))

    # 🔒 Bloqueo visual/funcional cuando está en estados bloqueados (excepto superuser)
    cc_bloqueado = (cc.estado in LOCKED_CC_STATES and not user.is_superuser)

    # ✅ Permiso de edición del cuadro (creador + revisor + superuser), pero bloqueado si estado bloqueado
    can_edit_cc = (
        not cc_bloqueado
        and (
            user.is_superuser
            or is_reviewer(user)
            or cc.creado_por_id == user.id
        )
    )

    adjuntos = list(
        cc.adjuntos.select_related("subido_por").all().order_by("-subido_en")
    )

    # ✅ Adjuntos: solo creador + superuser (y bloqueado si estado bloqueado)
    can_edit_docs = (
        not cc_bloqueado
        and (
            user.is_superuser
            or cc.creado_por_id == user.id
        )
    )

    return render(
        request,
        "procurement/cc_detail.html",
        {
            "cc": cc,
            "items": items,
            "proveedores": proveedores,
            "precios": precios,
            "totales_por_proveedor": totales_por_proveedor,
            "total_general": total_general,
            "ordenes": cc.ordenes_pago.all(),

            "is_reviewer": is_rev,
            "is_approver": is_app,

            "cc_bloqueado": cc_bloqueado,
            "can_edit_cc": can_edit_cc,

            # Adjuntos (cotizaciones)
            "adjuntos": adjuntos,
            "attachment_form": ComparativeAttachmentForm(),
            "can_edit_docs": can_edit_docs,
        },
    )


@login_required
def cc_delete(request, pk: int):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    # Solo creador o superuser
    if not (request.user.is_superuser or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para eliminar este cuadro.")

    # Solo se elimina en BORRADOR (para evitar romper flujo)
    if not request.user.is_superuser and cc.estado != ComparativeQuote.Status.BORRADOR:
        messages.error(request, "Solo puedes eliminar un cuadro en estado BORRADOR.")
        return redirect("cc_list")

    # POST obligatorio
    if request.method != "POST":
        return redirect("cc_list")

    try:
        cc.delete()
        messages.success(request, f"Cuadro eliminado: {cc.number}")
    except ProtectedError:
        # Por si existen OPs u otras relaciones PROTECT
        messages.error(
            request,
            "No se puede eliminar este cuadro porque tiene órdenes de pago u otros registros asociados.",
        )

    return redirect("cc_list")

@login_required
def cc_add_item(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if cc.estado in LOCKED_CC_STATES:
        messages.error(request, "El cuadro está bloqueado y no se puede editar.")
        return redirect("cc_detail", pk=cc.pk)

    if not _can_edit_cc(request.user, cc):
        messages.error(request, "No tienes permisos para editar este cuadro (solo ver).")
        return redirect("cc_detail", pk=cc.pk)


    # 🔒 Si está aprobado: no se puede editar (excepto superuser)
    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        messages.error(request, "El cuadro está APROBADO y no se puede editar.")
        return redirect("cc_detail", pk=pk)

    if request.method == "POST":
        form = ComparativeItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.cuadro = cc

            existente = cc.items.filter(producto=item.producto).first()
            if existente:
                existente.cantidad = existente.cantidad + item.cantidad
                existente.unidad = item.unidad
                existente.save()
                messages.success(request, "Producto ya existía: se actualizó la cantidad.")
            else:
                item.save()
                messages.success(request, "Producto agregado.")

            return redirect("cc_detail", pk=pk)
    else:
        form = ComparativeItemForm()

    return render(request, "procurement/cc_add_item.html", {"form": form, "cc": cc})

@login_required
def cc_add_supplier(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if cc.estado in LOCKED_CC_STATES:
        messages.error(request, "El cuadro está bloqueado y no se puede editar.")
        return redirect("cc_detail", pk=cc.pk)

    if not _can_edit_cc(request.user, cc):
        messages.error(request, "No tienes permisos para editar este cuadro (solo ver).")
        return redirect("cc_detail", pk=cc.pk)


    # 🔒 Si está aprobado: no se puede editar (excepto superuser)
    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        messages.error(request, "El cuadro está APROBADO y no se puede editar.")
        return redirect("cc_detail", pk=pk)

    if request.method == "POST":
        form = ComparativeSupplierForm(request.POST)
        if form.is_valid():
            sup = form.save(commit=False)
            sup.cuadro = cc
            sup.save()
            messages.success(request, "Proveedor agregado")
            return redirect("cc_detail", pk=pk)
    else:
        form = ComparativeSupplierForm()

    return render(request, "procurement/cc_add_supplier.html", {"form": form, "cc": cc})


@login_required
def cc_edit_item(request, pk, item_id):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

    item = get_object_or_404(cc.items.select_related("producto"), pk=item_id)

    if request.method == "POST":
        form = ComparativeItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado.")
            return redirect("cc_detail", pk=cc.pk)
    else:
        form = ComparativeItemForm(instance=item)

    return render(request, "procurement/cc_edit_item.html", {"cc": cc, "item": item, "form": form})


@login_required
def cc_delete_item(request, pk, item_id):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

    item = get_object_or_404(cc.items.select_related("producto"), pk=item_id)

    if request.method == "POST":
        with transaction.atomic():
            cc.precios.filter(producto_id=item.producto_id).delete()
            item.delete()

        messages.success(request, "Producto eliminado del cuadro.")
        return redirect("cc_detail", pk=cc.pk)

    return render(request, "procurement/cc_delete_item.html", {"cc": cc, "item": item})


@login_required
def cc_edit_supplier(request, pk, supplier_id):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

    sup = get_object_or_404(cc.proveedores.select_related("proveedor"), pk=supplier_id)

    if request.method == "POST":
        form = ComparativeSupplierForm(request.POST, instance=sup)
        if form.is_valid():
            form.save()
            messages.success(request, "Proveedor actualizado.")
            return redirect("cc_detail", pk=cc.pk)
    else:
        form = ComparativeSupplierForm(instance=sup)

    return render(request, "procurement/cc_edit_supplier.html", {"cc": cc, "sup": sup, "form": form})


@login_required
def cc_delete_supplier(request, pk, supplier_id):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

    sup = get_object_or_404(cc.proveedores.select_related("proveedor"), pk=supplier_id)

    if request.method == "POST":
        with transaction.atomic():
            if cc.proveedor_seleccionado_id == sup.id:
                cc.proveedor_seleccionado = None
                cc.save(update_fields=["proveedor_seleccionado"])

            cc.precios.filter(proveedor_id=sup.proveedor_id).delete()
            sup.delete()

        messages.success(request, "Proveedor eliminado del cuadro.")
        return redirect("cc_detail", pk=cc.pk)

    return render(request, "procurement/cc_delete_supplier.html", {"cc": cc, "sup": sup})


# ✅ IMPORTANTE: este bloque debe existir sí o sí, si urls.py lo llama
@login_required
def cc_prices(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)
    if cc.estado in LOCKED_CC_STATES:
        messages.error(request, "El cuadro está bloqueado y no se puede editar.")
        return redirect("cc_detail", pk=cc.pk)

    if not _can_edit_cc(request.user, cc):
        messages.error(request, "No tienes permisos para editar este cuadro (solo ver).")
        return redirect("cc_detail", pk=cc.pk)

    # 🔒 Si está aprobado: se permite VER, pero no GUARDAR (excepto superuser)
    cc_bloqueado = (cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser)

    items = list(cc.items.select_related("producto").all())
    proveedores = list(cc.proveedores.select_related("proveedor").all())

    precios_existentes = {
        f"{p.proveedor_id}_{p.producto_id}": p.precio_unit
        for p in cc.precios.all()
    }

    if request.method == "POST":
        if cc_bloqueado:
            messages.error(request, "El cuadro está APROBADO: la matriz está bloqueada (no se puede guardar).")
            return redirect("cc_prices", pk=pk)

        with transaction.atomic():
            for ps in proveedores:
                for it in items:
                    field_name = f"precio_{ps.proveedor_id}_{it.producto_id}"
                    raw = (request.POST.get(field_name) or "").strip()
                    if raw == "":
                        continue

                    raw = raw.replace(",", ".")
                    precio = Decimal(raw)

                    obj = cc.precios.filter(
                        proveedor_id=ps.proveedor_id,
                        producto_id=it.producto_id,
                    ).first()

                    if obj:
                        obj.precio_unit = precio
                        obj.save()
                    else:
                        cc.precios.create(
                            proveedor_id=ps.proveedor_id,
                            producto_id=it.producto_id,
                            precio_unit=precio,
                        )

                    precios_existentes[f"{ps.proveedor_id}_{it.producto_id}"] = precio

        messages.success(request, "Precios guardados.")
        return redirect("cc_prices", pk=pk)

    matriz = []
    for it in items:
        fila = {"item": it, "celdas": []}
        for ps in proveedores:
            key = f"{ps.proveedor_id}_{it.producto_id}"
            fila["celdas"].append(
                {
                    "proveedor_id": ps.proveedor_id,
                    "producto_id": it.producto_id,
                    "precio_unit": precios_existentes.get(key, ""),
                }
            )
        matriz.append(fila)

    return render(
        request,
        "procurement/cc_prices.html",
        {"cc": cc, "items": items, "proveedores": proveedores, "matriz": matriz, "cc_bloqueado": cc_bloqueado},
    )


@login_required
def cc_select_supplier(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)
    if cc.estado in LOCKED_CC_STATES:
        messages.error(request, "El cuadro está bloqueado y no se puede editar.")
        return redirect("cc_detail", pk=cc.pk)

    if not _can_edit_cc(request.user, cc):
        messages.error(request, "No tienes permisos para editar este cuadro (solo ver).")
        return redirect("cc_detail", pk=cc.pk)

    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        messages.error(request, "El cuadro está APROBADO: no se puede cambiar el proveedor seleccionado.")
        return redirect("cc_detail", pk=pk)

    if request.method == "POST":
        form = ComparativeSelectionForm(request.POST, instance=cc)
        if form.is_valid():
            form.save()
            messages.success(request, "Proveedor seleccionado guardado.")
            return redirect("cc_detail", pk=pk)
    else:
        form = ComparativeSelectionForm(instance=cc)

    form.fields["proveedor_seleccionado"].queryset = cc.proveedores.all()
    return render(request, "procurement/cc_select_supplier.html", {"cc": cc, "form": form})


# =========================
# FLUJO NUEVO
# BORRADOR -> EN_REVISION -> REVISADO -> APROBADO
# =========================

@login_required
def cc_send_review(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    # Solo el creador (o superuser) puede enviar a revisión
    if not (request.user.is_superuser or cc.creado_por_id == request.user.id):
        messages.error(request, "No tienes permiso para enviar este cuadro a revisión.")
        return redirect("cc_detail", pk=pk)

    if cc.estado == ComparativeQuote.Status.APROBADO:
        messages.error(request, "Este cuadro ya está aprobado y no puede volver a revisión.")
        return redirect("cc_detail", pk=pk)

    if cc.estado not in {ComparativeQuote.Status.BORRADOR, ComparativeQuote.Status.RECHAZADO}:
        messages.error(request, "Solo puedes enviar a revisión desde Borrador o Rechazado.")
        return redirect("cc_detail", pk=cc.pk)

    # =========================
    # ✅ VALIDACIONES (completo antes de revisión)
    # Proveedores / Precios y Totales / Proveedor seleccionado / Motivo / OPs
    # =========================
    errores = []

    items = list(cc.items.select_related("producto").all())
    proveedores = list(cc.proveedores.select_related("proveedor").all())

    if not items:
        errores.append("Debes agregar al menos un producto.")
    if not proveedores:
        errores.append("Debes agregar al menos un proveedor.")

    # Validar proveedor seleccionado + motivo
    if not cc.proveedor_seleccionado_id:
        errores.append("Debes seleccionar un proveedor ganador.")
    if not (cc.motivo_seleccion or "").strip():
        errores.append("Debes registrar el motivo de la selección.")

    # Validar matriz completa (precio por cada proveedor y producto)
    if items and proveedores:
        existentes = set(
            cc.precios.values_list("proveedor_id", "producto_id")
        )
        faltantes = []
        for ps in proveedores:
            for it in items:
                key = (ps.proveedor_id, it.producto_id)
                if key not in existentes:
                    faltantes.append(f"{ps.proveedor.nombre_empresa} → {it.producto.nombre}")

        if faltantes:
            # Mostramos solo algunos para no saturar mensajes
            preview = ", ".join(faltantes[:10])
            extra = "" if len(faltantes) <= 10 else f" … (+{len(faltantes) - 10} más)"
            errores.append(f"Faltan precios en la matriz para: {preview}{extra}")

    # Validar que existan OPs generadas antes de enviar a revisión
    if not cc.ordenes_pago.exists():
        errores.append("Antes de enviar a revisión, genera la(s) órdenes de pago desde este cuadro.")

    if errores:
        for e in errores:
            messages.error(request, e)
        return redirect("cc_detail", pk=cc.pk)

    # =========================
    # ✅ OK: pasar a EN_REVISION
    # =========================
    cc.estado = ComparativeQuote.Status.EN_REVISION
    cc.revisado_por = None
    cc.revisado_en = None
    cc.aprobado_por = None
    cc.aprobado_en = None
    cc.rechazado_por = None
    cc.rechazado_en = None
    cc.save(
        update_fields=[
            "estado",
            "revisado_por",
            "revisado_en",
            "aprobado_por",
            "aprobado_en",
            "rechazado_por",
            "rechazado_en",
        ]
    )
    messages.success(request, "Cuadro enviado a revisión.")
    return redirect("cc_detail", pk=cc.pk)

@login_required
def cc_mark_reviewed(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user)):
        return HttpResponseForbidden("No tienes permiso para revisar.")

    if cc.creado_por_id == request.user.id:
        return HttpResponseForbidden("No puedes revisar un cuadro que tú creaste.")

    if cc.estado != ComparativeQuote.Status.EN_REVISION:
        messages.error(request, "El cuadro no está en revisión.")
        return redirect("cc_detail", pk=pk)

    cc.estado = ComparativeQuote.Status.REVISADO
    cc.revisado_por = request.user
    cc.revisado_en = timezone.now()
    cc.save(update_fields=["estado", "revisado_por", "revisado_en"])

    messages.success(request, "Cuadro marcado como revisado.")
    return redirect("cc_detail", pk=pk)


@login_required
def cc_back_to_review(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_approver(request.user)):
        return HttpResponseForbidden("No tienes permiso para devolver a revisión.")

    if cc.estado != ComparativeQuote.Status.REVISADO:
        messages.error(request, "Solo se puede devolver a revisión un cuadro en estado REVISADO.")
        return redirect("cc_detail", pk=pk)

    cc.estado = ComparativeQuote.Status.EN_REVISION
    cc.aprobado_por = None
    cc.aprobado_en = None
    cc.save(update_fields=["estado", "aprobado_por", "aprobado_en"])

    messages.success(request, "Devuelto a revisión.")
    return redirect("cc_detail", pk=pk)


@login_required
def cc_approve_final(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_approver(request.user)):
        return HttpResponseForbidden("No tienes permiso para aprobar.")

    if cc.creado_por_id == request.user.id:
        return HttpResponseForbidden("No puedes aprobar un cuadro que tú creaste.")

    if cc.estado != ComparativeQuote.Status.REVISADO:
        messages.error(request, "Solo se puede aprobar un cuadro en estado REVISADO.")
        return redirect("cc_detail", pk=pk)

    cc.estado = ComparativeQuote.Status.APROBADO
    cc.aprobado_por = request.user
    cc.aprobado_en = timezone.now()
    cc.save(update_fields=["estado", "aprobado_por", "aprobado_en"])

    messages.success(request, "Cuadro aprobado.")
    return redirect("cc_detail", pk=pk)


@login_required
def cc_back_to_draft(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    # si quieres, esto lo restringimos solo a reviewer/approver,
    # pero por ahora lo dejamos como lo venías usando
    cc.estado = ComparativeQuote.Status.BORRADOR
    cc.revisado_por = None
    cc.revisado_en = None
    cc.aprobado_por = None
    cc.aprobado_en = None
    cc.save(update_fields=["estado", "revisado_por", "revisado_en", "aprobado_por", "aprobado_en"])

    messages.success(request, "Devuelto a borrador.")
    return redirect("cc_detail", pk=pk)


@login_required
def cc_generate_ops(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)
    user = request.user

    if not (user.is_superuser or cc.creado_por_id == user.id):
        return HttpResponseForbidden("No tiene permisos para generar OPs desde este cuadro.")

    items = list(cc.items.select_related("producto").all())
    proveedores = list(cc.proveedores.select_related("proveedor").all())

    precios = defaultdict(dict)
    for p in cc.precios.all():
        precios[p.proveedor_id][p.producto_id] = p.precio_unit

    if request.method == "POST":
        asignados = defaultdict(list)

        for it in items:
            proveedor_id = request.POST.get(f"asignado_{it.id}")
            if proveedor_id:
                asignados[int(proveedor_id)].append(it)

        if not asignados:
            messages.error(request, "No seleccionaste ningún proveedor para los productos.")
            return redirect("cc_generate_ops", pk=pk)

        faltan = []
        for proveedor_id, items_lista in asignados.items():
            for it in items_lista:
                precio_unit = precios.get(proveedor_id, {}).get(it.producto_id)
                if precio_unit is None:
                    faltan.append(f"{it.producto.nombre} (prov_id={proveedor_id})")

        if faltan:
            messages.error(
                request,
                "No se puede generar OP: faltan precios en la matriz para: " + ", ".join(faltan),
            )
            return redirect("cc_generate_ops", pk=pk)

        creadas_ops = []

        for proveedor_id, items_lista in asignados.items():
            proveedor = Provider.objects.get(pk=proveedor_id)

            op = PaymentOrder.objects.create(
                cuadro=cc,
                proveedor=proveedor,
                para="Maria Teresa Vargas",
                cargo_para="Directora Ejecutiva",
                de=request.user.get_full_name() or request.user.username,
                cargo_de=getattr(getattr(request.user, "userprofile", None), "cargo", "") or "",
                fecha_solicitud=timezone.localdate(),
                proyecto="Uso Contable",
                partida_contable="Uso Contable",
                con_factura="Si",
                efectivo="No",
                descripcion=f"Orden generada desde {cc.number}",
                creado_por=request.user,
            )

            for it in items_lista:
                precio_unit = precios.get(proveedor_id, {}).get(it.producto_id, Decimal("0"))
                PaymentOrderItem.objects.create(
                    orden=op,
                    producto=it.producto,
                    unidad=it.unidad,
                    cantidad=it.cantidad,
                    precio_unit=precio_unit,
                )

            creadas_ops.append(op)

        messages.success(request, f"Órdenes creadas: {', '.join([o.number for o in creadas_ops])}")

        # ✅ PASO A: volver siempre al CC (no te saca a otras pantallas)
        return redirect("cc_detail", pk=cc.pk)

    return render(
        request,
        "procurement/cc_generate_ops.html",
        {"cc": cc, "items": items, "proveedores": proveedores},
    )

@login_required
def cc_print(request, pk: int):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    # Permiso de impresión: creador, reviewer, approver o superuser
    if not (
        request.user.is_superuser
        or is_reviewer(request.user)
        or is_approver(request.user)
        or cc.creado_por_id == request.user.id
    ):
        return HttpResponseForbidden("No tienes permiso para ver este cuadro.")

    items = list(cc.items.select_related("producto").all())
    proveedores = list(cc.proveedores.select_related("proveedor").all())

    precios = defaultdict(dict)
    for p in cc.precios.all():
        precios[p.proveedor_id][p.producto_id] = p.precio_unit

    totales_por_proveedor = {}
    for ps in proveedores:
        prov_id = ps.proveedor_id
        total = Decimal("0")
        for it in items:
            pu = precios.get(prov_id, {}).get(it.producto_id)
            if pu is not None:
                total += (it.cantidad * pu)
        totales_por_proveedor[str(prov_id)] = total

    total_general = sum(totales_por_proveedor.values(), Decimal("0"))

    return render(
        request,
        "procurement/cc_print.html",
        {
            "cc": cc,
            "items": items,
            "proveedores": proveedores,
            "precios": precios,
            "totales_por_proveedor": totales_por_proveedor,
            "total_general": total_general,
        },
    )

@login_required
def cc_attachment_upload(request, pk: int):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    # Si está en BORRADOR, solo el creador o superuser pueden verlo/subir
    if cc.estado == ComparativeQuote.Status.BORRADOR and not (
        request.user.is_superuser or cc.creado_por_id == request.user.id
    ):
        messages.error(request, "Este cuadro está en borrador y aún no está disponible para revisión.")
        return redirect("cc_list")

    # Permiso: solo creador (o superuser) puede adjuntar
    if not (request.user.is_superuser or cc.creado_por_id == request.user.id):
        messages.error(request, "No tienes permiso para adjuntar documentos a este cuadro.")
        return redirect("cc_detail", pk=pk)


    # Si está aprobado, no se permite adjuntar (excepto superuser)
    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        messages.error(request, "El cuadro está APROBADO: no se pueden adjuntar documentos.")
        return redirect("cc_detail", pk=pk)

    if request.method != "POST":
        return redirect("cc_detail", pk=pk)

    form = ComparativeAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        att = form.save(commit=False)
        att.cuadro = cc
        att.subido_por = request.user
        att.save()
        messages.success(request, "Documento adjuntado.")
    else:
        messages.error(request, "No se pudo adjuntar el documento. Verifica el archivo.")

    return redirect("cc_detail", pk=pk)


@login_required
def cc_attachment_delete(request, pk: int, att_id: int):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    # Permiso: solo creador (o superuser) puede eliminar adjuntos
    if not (request.user.is_superuser or cc.creado_por_id == request.user.id):
        messages.error(request, "No tienes permiso para eliminar adjuntos de este cuadro.")
        return redirect("cc_detail", pk=pk)


    # Si está aprobado, no se permite eliminar (excepto superuser)
    if cc.estado == ComparativeQuote.Status.APROBADO and not request.user.is_superuser:
        messages.error(request, "El cuadro está APROBADO: no se pueden eliminar documentos.")
        return redirect("cc_detail", pk=pk)

    if request.method != "POST":
        return redirect("cc_detail", pk=pk)

    att = get_object_or_404(ComparativeQuoteAttachment, pk=att_id, cuadro=cc)
    att.delete()
    messages.success(request, "Documento eliminado.")
    return redirect("cc_detail", pk=pk)

@login_required
def cc_reject(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    cc = get_object_or_404(ComparativeQuote, pk=pk)
    user = request.user

    if not (user.is_superuser or is_approver(user)):
        return HttpResponseForbidden("No tiene permisos para rechazar.")

    if cc.estado != ComparativeQuote.Status.REVISADO:
        messages.error(request, "Solo se puede rechazar un cuadro en estado 'Revisado'.")
        return redirect("cc_detail", pk=cc.pk)

    if (not user.is_superuser) and cc.creado_por_id == user.id:
        messages.error(request, "No puedes rechazar tu propio cuadro.")
        return redirect("cc_detail", pk=cc.pk)

    cc.estado = ComparativeQuote.Status.RECHAZADO
    cc.rechazado_por = user
    cc.rechazado_en = timezone.now()
    cc.aprobado_por = None
    cc.aprobado_en = None
    cc.save(update_fields=["estado", "rechazado_por", "rechazado_en", "aprobado_por", "aprobado_en"])

    messages.success(request, "Cuadro rechazado.")
    return redirect("cc_detail", pk=cc.pk)

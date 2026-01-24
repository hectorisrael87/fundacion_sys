# src/apps/procurement/views.py
from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.catalog.models import Provider
from apps.core.permissions import is_creator, is_reviewer
from apps.payments.models import PaymentOrder, PaymentOrderItem

from .forms import (
    ComparativeItemForm,
    ComparativeQuoteForm,
    ComparativeSelectionForm,
    ComparativeSupplierForm,
)
from .models import ComparativeQuote


# -------------------------
# LISTADO
# -------------------------
@login_required
def cc_list(request):
    qs = ComparativeQuote.objects.select_related("creado_por", "revisado_por").order_by("-creado_en")

    # Creador ve lo suyo; revisor/superuser ve todo
    if not (request.user.is_superuser or is_reviewer(request.user)):
        qs = qs.filter(creado_por=request.user)

    return render(
        request,
        "procurement/cc_list.html",
        {
            "cuadros": qs,
            "is_reviewer": (request.user.is_superuser or is_reviewer(request.user)),
        },
    )


# -------------------------
# CREAR / DETALLE
# -------------------------
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
def cc_detail(request, pk: int):
    cc = get_object_or_404(ComparativeQuote.objects.select_related("creado_por", "revisado_por"), pk=pk)

    # seguridad: creador ve lo suyo; revisor/admin ve todo
    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso para ver este cuadro.")

    items = list(cc.items.select_related("producto").all())
    proveedores = list(cc.proveedores.select_related("proveedor").all())

    # precios[proveedor_id][producto_id] = precio_unit
    precios = defaultdict(dict)
    for p in cc.precios.all():
        precios[p.proveedor_id][p.producto_id] = p.precio_unit

    # totales por proveedor (key proveedor_id como string)
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
        "procurement/cc_detail.html",
        {
            "cc": cc,
            "items": items,
            "proveedores": proveedores,
            "precios": precios,
            "totales_por_proveedor": totales_por_proveedor,
            "total_general": total_general,
            "ordenes": cc.ordenes_pago.all(),
            "is_reviewer": (request.user.is_superuser or is_reviewer(request.user)),
        },
    )


# -------------------------
# PRODUCTOS
# -------------------------
@login_required
def cc_add_item(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == "APROBADO" and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

    if request.method == "POST":
        form = ComparativeItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.cuadro = cc

            # si ya existe ese producto, actualiza en vez de duplicar
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
def cc_edit_item(request, pk, item_id):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == "APROBADO" and not request.user.is_superuser:
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

    if cc.estado == "APROBADO" and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

    item = get_object_or_404(cc.items.select_related("producto"), pk=item_id)

    if request.method == "POST":
        with transaction.atomic():
            # borrar precios del producto para este cuadro
            cc.precios.filter(producto_id=item.producto_id).delete()
            item.delete()
        messages.success(request, "Producto eliminado del cuadro.")
        return redirect("cc_detail", pk=cc.pk)

    return render(request, "procurement/cc_delete_item.html", {"cc": cc, "item": item})


# -------------------------
# PROVEEDORES
# -------------------------
@login_required
def cc_add_supplier(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == "APROBADO" and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

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
def cc_edit_supplier(request, pk, supplier_id):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == "APROBADO" and not request.user.is_superuser:
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

    if cc.estado == "APROBADO" and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

    sup = get_object_or_404(cc.proveedores.select_related("proveedor"), pk=supplier_id)

    if request.method == "POST":
        with transaction.atomic():
            # si estaba seleccionado, lo limpiamos
            if cc.proveedor_seleccionado_id == sup.id:
                cc.proveedor_seleccionado = None
                cc.save(update_fields=["proveedor_seleccionado"])

            # borrar precios de ese proveedor para este cuadro
            cc.precios.filter(proveedor_id=sup.proveedor_id).delete()
            sup.delete()

        messages.success(request, "Proveedor eliminado del cuadro.")
        return redirect("cc_detail", pk=cc.pk)

    return render(request, "procurement/cc_delete_supplier.html", {"cc": cc, "sup": sup})


# -------------------------
# MATRIZ PRECIOS
# -------------------------
@login_required
def cc_prices(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == "APROBADO" and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

    items = list(cc.items.select_related("producto").all())
    proveedores = list(cc.proveedores.select_related("proveedor").all())

    precios_existentes = {
        f"{p.proveedor_id}_{p.producto_id}": p.precio_unit
        for p in cc.precios.all()
    }

    if request.method == "POST":
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
        {"cc": cc, "items": items, "proveedores": proveedores, "matriz": matriz},
    )


# -------------------------
# SELECCIÓN PROVEEDOR
# -------------------------
@login_required
def cc_select_supplier(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
        return HttpResponseForbidden("No tienes permiso.")

    if cc.estado == "APROBADO" and not request.user.is_superuser:
        return HttpResponseForbidden("El cuadro está aprobado y no se puede editar.")

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


# -------------------------
# FLUJO (Borrador -> Revisión -> Aprobado)
# -------------------------
@login_required
def cc_send_review(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if cc.estado == "APROBADO":
        messages.error(request, "Este cuadro ya está aprobado y no puede volver a revisión.")
        return redirect("cc_detail", pk=pk)

    cc.estado = "EN_REVISION"
    cc.save(update_fields=["estado"])
    messages.success(request, "Enviado a revisión.")
    return redirect("cc_detail", pk=pk)


@login_required
def cc_approve(request, pk):
    """
    Mantengo este nombre porque tu urls.py lo usa.
    Aprobación (por ahora) = marcar APROBADO + registrar revisado_por/en.
    """
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not is_reviewer(request.user):
        return HttpResponseForbidden("No tienes permiso para aprobar.")

    if cc.creado_por_id == request.user.id:
        return HttpResponseForbidden("No puedes aprobar un cuadro que tú creaste.")

    cc.estado = "APROBADO"
    cc.revisado_por = request.user
    cc.revisado_en = timezone.now()
    cc.save(update_fields=["estado", "revisado_por", "revisado_en"])

    messages.success(request, "Cuadro aprobado.")
    return redirect("cc_detail", pk=pk)


# Si en algún lado habías creado cc_approve_final, lo dejo como alias
cc_approve_final = cc_approve


@login_required
def cc_back_to_draft(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    cc.estado = "BORRADOR"
    cc.revisado_por = None
    cc.revisado_en = None
    cc.save(update_fields=["estado", "revisado_por", "revisado_en"])

    messages.success(request, "Devuelto a borrador.")
    return redirect("cc_detail", pk=pk)


# -------------------------
# GENERAR OPS
# -------------------------
@login_required
def cc_generate_ops(request, pk):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

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
                "No se puede generar OP: faltan precios en la matriz para: " + ", ".join(faltan)
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
                cargo_de=getattr(getattr(request.user, "profile", None), "cargo", "") or "",
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

        if len(creadas_ops) == 1:
            return redirect("op_detail", pk=creadas_ops[0].pk)

        return redirect("op_list")

    return render(
        request,
        "procurement/cc_generate_ops.html",
        {"cc": cc, "items": items, "proveedores": proveedores},
    )


# -------------------------
# IMPRESIÓN
# -------------------------
@login_required
def cc_print(request, pk: int):
    cc = get_object_or_404(ComparativeQuote, pk=pk)

    if not (request.user.is_superuser or is_reviewer(request.user) or cc.creado_por_id == request.user.id):
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

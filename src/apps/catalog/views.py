from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from apps.catalog.models import Product
from apps.catalog.models import Provider
from .forms import ProviderForm, ProductForm
from django.db import models


@login_required
def provider_create(request):
    next_url = request.GET.get("next") or "/"

    if request.method == "POST":
        form = ProviderForm(request.POST)
        if form.is_valid():
            p = form.save(commit=False)

            # si codigo está vacío, lo guardamos como NULL (None)
            if not getattr(p, "codigo", None):
                p.codigo = None
            p.save()

            messages.success(request, f"Proveedor creado: {p.nombre_empresa}")
            return redirect(next_url)
    else:
        form = ProviderForm()

    return render(
        request,
        "catalog/provider_form.html",
        {"form": form, "next_url": next_url, "title": "Nuevo proveedor"},
    )


@login_required
def provider_edit(request, pk: int):
    proveedor = get_object_or_404(Provider, pk=pk)
    next_url = request.GET.get("next") or "/"

    if request.method == "POST":
        form = ProviderForm(request.POST, instance=proveedor)
        if form.is_valid():
            p = form.save(commit=False)
            if not getattr(p, "codigo", None):
                p.codigo = None
            p.save()

            messages.success(request, f"Proveedor actualizado: {p.nombre_empresa}")
            return redirect(next_url)
    else:
        form = ProviderForm(instance=proveedor)

    return render(
        request,
        "catalog/provider_form.html",
        {"form": form, "next_url": next_url, "title": "Editar proveedor"},
    )


@login_required
def product_create(request):
    next_url = request.GET.get("next") or request.POST.get("next") or "/"

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            p = form.save()
            messages.success(request, f"Producto creado: {p.nombre}")

            sep = "&" if "?" in next_url else "?"
            return redirect(f"{next_url}{sep}created_product={p.pk}")
    else:
        form = ProductForm()

    return render(request, "catalog/product_form.html", {"form": form, "next_url": next_url})


@login_required
def provider_list(request):
    proveedores = Provider.objects.order_by("nombre_empresa")

    f = (request.GET.get("f") or "all").lower()

    if f == "incomplete":
        # Incompleto = faltan datos importantes (campos vacíos)
        proveedores = proveedores.filter(
            models.Q(nit="") |
            models.Q(telefono="") |
            models.Q(direccion="") |
            models.Q(entidad="") |
            models.Q(nro_cuenta="") |
            models.Q(datos_transferencia="")
        )
    elif f == "with_nit":
        proveedores = proveedores.exclude(nit="")
    elif f == "no_nit":
        proveedores = proveedores.filter(nit="")
    else:
        f = "all"

    return render(
        request,
        "catalog/provider_list.html",
        {"proveedores": proveedores, "f": f},
    )
@login_required
def product_edit(request, pk: int):
    producto = get_object_or_404(Product, pk=pk)
    next_url = request.GET.get("next") or request.POST.get("next") or "/"

    if request.method == "POST":
        form = ProductForm(request.POST, instance=producto)
        if form.is_valid():
            p = form.save()
            messages.success(request, f"Producto actualizado: {p.nombre}")
            return redirect(next_url)
    else:
        form = ProductForm(instance=producto)

    return render(
        request,
        "catalog/product_form.html",
        {"form": form, "next_url": next_url, "title": "Editar producto"},
    )


@login_required
def product_delete(request, pk: int):
    producto = get_object_or_404(Product, pk=pk)
    next_url = request.GET.get("next") or request.POST.get("next") or "/"

    if request.method == "POST":
        # ✅ Recomendado: desactivar en vez de borrar
        if hasattr(producto, "activo"):
            producto.activo = False
            producto.save(update_fields=["activo"])
            messages.success(request, f"Producto desactivado: {producto.nombre}")
        else:
            producto.delete()
            messages.success(request, f"Producto eliminado: {producto.nombre}")

        return redirect(next_url)

    return render(
        request,
        "catalog/product_confirm_delete.html",
        {"producto": producto, "next_url": next_url},
    )

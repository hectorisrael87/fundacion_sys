from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Provider
from .forms import ProviderForm, ProductForm


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
    next_url = request.GET.get("next") or "/"

    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            p = form.save()
            messages.success(request, f"Producto creado: {p.nombre}")
            return redirect(next_url)
    else:
        form = ProductForm()

    return render(request, "catalog/product_form.html", {"form": form, "next_url": next_url})


@login_required
def provider_list(request):
    proveedores = Provider.objects.order_by("nombre_empresa")
    return render(request, "catalog/provider_list.html", {"proveedores": proveedores})

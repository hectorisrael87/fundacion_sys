from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def home(request):
    return render(request, "core/home.html")

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from apps.core.permissions import is_reviewer, is_approver
from apps.procurement.models import ComparativeQuote
from apps.payments.models import PaymentOrder


@login_required
def home(request):
    return render(request, "home.html")


def _bucket_for_estado(estado: str, *, is_rev: bool, is_app: bool) -> str:
    # buckets que usan tus tabs: all / draft / pending / approved
    if estado == ComparativeQuote.Status.BORRADOR:
        return "draft"
    if estado == ComparativeQuote.Status.APROBADO:
        return "approved"

    if estado == ComparativeQuote.Status.EN_REVISION:
        # En tus listados, el aprobador “pending” es REVISADO, no EN_REVISION
        if is_app and not is_rev:
            return "other"
        return "pending"

    if estado == ComparativeQuote.Status.REVISADO:
        # En tus listados, el revisor “pending” es EN_REVISION, no REVISADO
        if is_rev and not is_app:
            return "other"
        return "pending"

    if estado == ComparativeQuote.Status.RECHAZADO:
        return "other"


def _label_and_badge_for_estado(estado: str, *, kind: str, is_rev: bool, is_app: bool):
    # kind: "cc" o "op" (por si luego quieres textos distintos)
    if estado == ComparativeQuote.Status.BORRADOR:
        return ("Borrador", "badge-draft")
    if estado == ComparativeQuote.Status.APROBADO:
        return ("Aprobado", "badge-approved")

    if estado == ComparativeQuote.Status.EN_REVISION:
        # Para revisor: “Pendiente” (tarea de revisar)
        if is_rev and not is_app:
            return ("Pendiente", "badge-pending")
        # Para creador y otros: “En revisión”
        return ("En revisión", "badge-pending")

    if estado == ComparativeQuote.Status.REVISADO:
        # Para aprobador: “Pendiente” (tarea de aprobar)
        if is_app and not is_rev:
            return ("Pendiente", "badge-pending")
        # Para creador y otros: “Revisado”
        return ("Revisado", "badge-reviewed")

    
    if estado == ComparativeQuote.Status.RECHAZADO:
    return ("Rechazado", "badge-rejected")


@login_required
def api_pending_counts(request):
    user = request.user
    is_rev = is_reviewer(user)
    is_app = is_approver(user)

    cc_pending = 0
    op_pending = 0

    if user.is_superuser:
        # superuser: considera pending como "en cola" por flujo (revisión / aprobación)
        cc_pending = ComparativeQuote.objects.filter(
            estado__in=[ComparativeQuote.Status.EN_REVISION, ComparativeQuote.Status.REVISADO]
        ).count()
        op_pending = PaymentOrder.objects.filter(
            estado__in=[PaymentOrder.Status.EN_REVISION, PaymentOrder.Status.REVISADO]
        ).count()
    elif is_rev and not is_app:
        cc_pending = ComparativeQuote.objects.filter(estado=ComparativeQuote.Status.EN_REVISION).count()
        op_pending = PaymentOrder.objects.filter(estado=PaymentOrder.Status.EN_REVISION).count()
    elif is_app and not is_rev:
        cc_pending = ComparativeQuote.objects.filter(estado=ComparativeQuote.Status.REVISADO).count()
        op_pending = PaymentOrder.objects.filter(estado=PaymentOrder.Status.REVISADO).count()
    else:
        # creador (sin rol revisor/aprobador): no mostramos “pendientes” en menú
        cc_pending = 0
        op_pending = 0

    return JsonResponse(
        {"cc_pending": cc_pending, "op_pending": op_pending},
        json_dumps_params={"ensure_ascii": False},
    )


@login_required
def api_live_status(request):
    kind = (request.GET.get("kind") or "").strip()
    ids_raw = (request.GET.get("ids") or "").strip()

    ids = []
    if ids_raw:
        for part in ids_raw.split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))

    if kind not in {"cc", "op"} or not ids:
        return JsonResponse({"items": []})

    user = request.user
    is_rev = is_reviewer(user)
    is_app = is_approver(user)

    if kind == "cc":
        Model = ComparativeQuote
        Status = ComparativeQuote.Status
    else:
        Model = PaymentOrder
        Status = PaymentOrder.Status

    qs = Model.objects.filter(id__in=ids)

    # Respeta visibilidad base de tus listados: revisor/aprobador no ven BORRADOR, creador ve lo suyo.
    if not user.is_superuser:
        if is_rev or is_app:
            qs = qs.exclude(estado=Status.BORRADOR)
        else:
            qs = qs.filter(creado_por=user)

    items = []
    for obj in qs:
        estado = obj.estado
        # Reutilizamos el enum de CC para bucket/label (mismos valores)
        bucket = _bucket_for_estado(estado, is_rev=is_rev, is_app=is_app)
        label, badge_class = _label_and_badge_for_estado(estado, kind=kind, is_rev=is_rev, is_app=is_app)
        items.append(
            {
                "id": obj.id,
                "estado": estado,
                "bucket": bucket,
                "label": label,
                "badge_class": badge_class,
            }
        )

    return JsonResponse(
        {"items": items},
        json_dumps_params={"ensure_ascii": False},
    )

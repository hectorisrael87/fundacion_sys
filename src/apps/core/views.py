from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect

from apps.core.permissions import is_creator, is_reviewer, is_approver
from apps.procurement.models import ComparativeQuote
from apps.payments.models import PaymentOrder


@login_required
def dashboard(request):
    # Dashboard clásico (si lo necesitas)
    return render(request, "core/home.html")


def _bucket_for_estado(estado: str, *, Status, is_rev: bool, is_app: bool) -> str:
    """
    Buckets que usan tus tabs: all / draft / pending / approved (+ other)
    """
    if estado == Status.BORRADOR:
        return "draft"
    if estado == Status.APROBADO:
        return "approved"

    if estado == Status.EN_REVISION:
        # En tus listados, el aprobador “pending” es REVISADO, no EN_REVISION
        if is_app and not is_rev:
            return "other"
        return "pending"

    if estado == Status.REVISADO:
        # En tus listados, el revisor “pending” es EN_REVISION, no REVISADO
        if is_rev and not is_app:
            return "other"
        return "pending"

    return "other"


def _label_and_badge_for_estado(estado: str, *, Status, kind: str, is_rev: bool, is_app: bool):
    """
    kind: "cc" u "op" (por si luego quieres textos distintos)
    """
    if estado == Status.BORRADOR:
        return ("Borrador", "badge-draft")
    if estado == Status.APROBADO:
        return ("Aprobado", "badge-approved")

    if estado == Status.EN_REVISION:
        # Para revisor: “Pendiente” (tarea de revisar)
        if is_rev and not is_app:
            return ("Pendiente", "badge-pending")
        # Para creador y otros: “En revisión”
        return ("En revisión", "badge-pending")

    if estado == Status.REVISADO:
        # Para aprobador: “Pendiente” (tarea de aprobar)
        if is_app and not is_rev:
            return ("Pendiente", "badge-pending")
        # Para creador y otros: “Revisado”
        return ("Revisado", "badge-reviewed")

    if hasattr(Status, "RECHAZADO") and estado == Status.RECHAZADO:
        return ("Rechazado", "badge-rejected")

    return ("—", "badge-neutral")


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

    # Respeta visibilidad base: revisor/aprobador no ven BORRADOR ajeno; creador ve lo suyo.
    if not user.is_superuser:
        if is_rev or is_app:
            qs = qs.exclude(estado=Status.BORRADOR)
        else:
            qs = qs.filter(creado_por=user)

    items = []
    for obj in qs:
        estado = obj.estado
        bucket = _bucket_for_estado(estado, Status=Status, is_rev=is_rev, is_app=is_app)
        label, badge_class = _label_and_badge_for_estado(
            estado, Status=Status, kind=kind, is_rev=is_rev, is_app=is_app
        )
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


@login_required
def workbench(request):
    user = request.user
    is_rev = user.is_superuser or is_reviewer(user)
    is_app = user.is_superuser or is_approver(user)
    is_cre = is_creator(user) or user.is_superuser

    # Revisor: CC EN_REVISION
    pending_cc_review = ComparativeQuote.objects.none()
    if is_rev:
        pending_cc_review = (
            ComparativeQuote.objects.select_related("creado_por")
            .prefetch_related("ordenes_pago")
            .filter(estado=ComparativeQuote.Status.EN_REVISION)
            .order_by("creado_en")
        )

    # Aprobador: CC REVISADO
    pending_cc_approve = ComparativeQuote.objects.none()
    if is_app:
        pending_cc_approve = (
            ComparativeQuote.objects.select_related("creado_por")
            .prefetch_related("ordenes_pago")
            .filter(estado=ComparativeQuote.Status.REVISADO)
            .order_by("creado_en")
        )

    # OP sueltas (sin CC) — para evitar ruido del círculo
    pending_op_review = PaymentOrder.objects.none()
    if is_rev:
        pending_op_review = (
            PaymentOrder.objects.select_related("creado_por", "proveedor")
            .filter(cuadro__isnull=True, estado=PaymentOrder.Status.EN_REVISION)
            .order_by("creado_en")
        )

    pending_op_approve = PaymentOrder.objects.none()
    if is_app:
        pending_op_approve = (
            PaymentOrder.objects.select_related("creado_por", "proveedor")
            .filter(cuadro__isnull=True, estado=PaymentOrder.Status.REVISADO)
            .order_by("creado_en")
        )

    # Creador: borradores + rechazados propios (CC y OP)
    my_cc_drafts = ComparativeQuote.objects.none()
    my_cc_rejected = ComparativeQuote.objects.none()
    my_op_drafts = PaymentOrder.objects.none()
    my_op_rejected = PaymentOrder.objects.none()

    if is_cre:
        my_cc_drafts = ComparativeQuote.objects.filter(
            creado_por=user, estado=ComparativeQuote.Status.BORRADOR
        ).order_by("-creado_en")

        my_cc_rejected = ComparativeQuote.objects.filter(
            creado_por=user, estado=ComparativeQuote.Status.RECHAZADO
        ).order_by("-creado_en")

        my_op_drafts = PaymentOrder.objects.filter(
            creado_por=user, estado=PaymentOrder.Status.BORRADOR
        ).order_by("-creado_en")

        my_op_rejected = PaymentOrder.objects.filter(
            creado_por=user, estado=PaymentOrder.Status.RECHAZADO
        ).order_by("-creado_en")

    # =========================
    # ✅ “Continuar →” directo a OP (círculo)
    # =========================
    cc_next_op_review = {}   # {cc_id: op_id}
    cc_next_op_approve = {}  # {cc_id: op_id}

    if is_rev:
        for cc in pending_cc_review:
            ops = list(getattr(cc, "ordenes_pago").all())
            # Preferir OP en EN_REVISION (lo que el revisor debe atender)
            ops_pending = [op for op in ops if op.estado == PaymentOrder.Status.EN_REVISION]
            target = (sorted(ops_pending, key=lambda o: o.id) or sorted(ops, key=lambda o: o.id) or [None])[0]
            if target:
                cc_next_op_review[cc.id] = target.id

    if is_app:
        for cc in pending_cc_approve:
            ops = list(getattr(cc, "ordenes_pago").all())
            # Preferir OP en REVISADO (lo que el aprobador debe “ver” antes de aprobar en grupo)
            ops_pending = [op for op in ops if op.estado == PaymentOrder.Status.REVISADO]
            target = (sorted(ops_pending, key=lambda o: o.id) or sorted(ops, key=lambda o: o.id) or [None])[0]
            if target:
                cc_next_op_approve[cc.id] = target.id

    summary = {
        "cc_pending_review": pending_cc_review.count() if is_rev else 0,
        "cc_pending_approve": pending_cc_approve.count() if is_app else 0,
        "op_pending_review": pending_op_review.count() if is_rev else 0,
        "op_pending_approve": pending_op_approve.count() if is_app else 0,
        "my_cc_drafts": my_cc_drafts.count() if is_cre else 0,
        "my_op_drafts": my_op_drafts.count() if is_cre else 0,
        "my_rejected": (my_cc_rejected.count() + my_op_rejected.count()) if is_cre else 0,
    }

    return render(
        request,
        "core/workbench.html",
        {
            "is_reviewer": is_rev,
            "is_approver": is_app,
            "is_creator": is_cre,

            "pending_cc_review": pending_cc_review,
            "pending_cc_approve": pending_cc_approve,
            "pending_op_review": pending_op_review,
            "pending_op_approve": pending_op_approve,

            "my_cc_drafts": my_cc_drafts,
            "my_cc_rejected": my_cc_rejected,
            "my_op_drafts": my_op_drafts,
            "my_op_rejected": my_op_rejected,

            # ✅ nuevos mapas para links “Continuar →”
            "cc_next_op_review": cc_next_op_review,
            "cc_next_op_approve": cc_next_op_approve,

            "summary": summary,
        },
    )



def home(request):
    """
    Home inteligente:
    - Si está autenticado -> Bandeja (Mi trabajo)
    - Si no -> Login
    """
    if request.user.is_authenticated:
        return redirect("workbench")
    return redirect("login")

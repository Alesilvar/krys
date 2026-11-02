"""Consultas de lectura para la tabla histórica y el inventario actual."""

from django.db.models import Count, Q

from .models import Equipment, EquipmentMovement, Evaluation, Letter, Presentation


def filtered_records(params):
    """Combina presentaciones y retiros en una única lista filtrable."""
    presentations = Presentation.objects.select_related(
        "cpc_letter", "cpc_letter__response_letter", "equipment", "evaluation", "evaluation__response_letter"
    )
    movements = EquipmentMovement.objects.select_related(
        "equipment", "request_letter", "response_letter"
    )
    query = params.get("q", "").strip()
    result = params.get("result", "").strip()
    operational_status = params.get("status", "").strip()

    if query:
        presentations = presentations.filter(
            Q(equipment__code__icontains=query)
            | Q(cpc_letter__full_number__icontains=query)
            | Q(equipment_type__icontains=query)
            | Q(evaluation__response_letter__full_number__icontains=query)
        )
        movements = movements.filter(
            Q(equipment__code__icontains=query)
            | Q(request_letter__full_number__icontains=query)
            | Q(response_letter__full_number__icontains=query)
            | Q(equipment_type__icontains=query)
            | Q(brand__icontains=query)
            | Q(model__icontains=query)
            | Q(serial__icontains=query)
        )
    if result:
        presentations = presentations.filter(evaluation__result=result)
        movements = movements.none()
    if operational_status:
        presentations = presentations.filter(
            equipment__operational_status=operational_status
        )
        movement_status = {
            Equipment.OperationalStatus.REQUESTED: EquipmentMovement.Status.REQUESTED,
            Equipment.OperationalStatus.RETIRED: EquipmentMovement.Status.AUTHORIZED,
        }.get(operational_status)
        movements = (
            movements.filter(status=movement_status)
            if movement_status
            else movements.none()
        )

    rows = []
    for presentation in presentations:
        try:
            evaluation = presentation.evaluation
        except Evaluation.DoesNotExist:
            evaluation = None
        rows.append(
            {
                "kind": "presentation",
                "source": presentation,
                "cpc_letter": presentation.cpc_letter,
                "event_label": presentation.procedure_type,
                "equipment": presentation.equipment,
                "equipment_type": presentation.equipment_type,
                "operational_status": presentation.equipment.operational_status,
                "operational_label": presentation.equipment.get_operational_status_display(),
                "evaluation": evaluation,
                "response_letter": getattr(presentation.cpc_letter, "response_letter", None),
                "movement": None,
                "sort_date": presentation.cpc_letter.letter_date,
            }
        )
    for movement in movements:
        rows.append(
            {
                "kind": "movement",
                "source": movement,
                "cpc_letter": movement.request_letter,
                "event_label": "Desmovilización",
                "equipment": movement.equipment,
                "equipment_type": movement.equipment_type,
                "operational_status": (
                    Equipment.OperationalStatus.RETIRED
                    if movement.status == EquipmentMovement.Status.AUTHORIZED
                    else Equipment.OperationalStatus.REQUESTED
                ),
                "operational_label": movement.get_status_display(),
                "evaluation": None,
                "response_letter": movement.response_letter,
                "movement": movement,
                "sort_date": movement.request_letter.letter_date,
            }
        )
    rows.sort(
        key=lambda row: (row["sort_date"], row["cpc_letter"].correlative),
        reverse=True,
    )
    return rows, query, result, operational_status


def current_inventory_by_type():
    """Cuenta placas aprobadas que siguen activas o con retiro solicitado."""
    return list(
        Equipment.objects.filter(
            operational_status__in=[
                Equipment.OperationalStatus.ACTIVE,
                Equipment.OperationalStatus.REQUESTED,
            ],
            presentations__evaluation__result=Evaluation.Result.APPROVED,
        )
        .exclude(equipment_type="")
        .values("equipment_type")
        .annotate(total=Count("id", distinct=True))
        .order_by("equipment_type")
    )


def dashboard_metrics():
    inventory = current_inventory_by_type()
    return {
        "total": Presentation.objects.count() + EquipmentMovement.objects.count(),
        "approved": Evaluation.objects.filter(
            result=Evaluation.Result.APPROVED
        ).count(),
        "observed": Evaluation.objects.filter(
            result=Evaluation.Result.OBSERVED
        ).count(),
        "retired": Equipment.objects.filter(
            operational_status=Equipment.OperationalStatus.RETIRED
        ).count(),
        "pending_letters": Letter.objects.filter(
            direction=Letter.Direction.CPC_AAM, response_letter__isnull=True
        ).count(),
        "inventory_by_type": inventory,
        "inventory_total": sum(item["total"] for item in inventory),
    }


def letter_expedients(params):
    """Agrupa cartas CPC por sus relaciones de subsanación, sin duplicarlas."""
    letters = list(Letter.objects.filter(direction=Letter.Direction.CPC_AAM).select_related(
        "response_letter", "predecessor_response__response_to"
    ).prefetch_related("presentations__equipment", "presentations__evaluation", "requested_movements__equipment"))
    by_id = {letter.pk: letter for letter in letters}
    groups = {}
    for letter in letters:
        current, seen = letter, set()
        while current.predecessor_response_id and current.pk not in seen:
            seen.add(current.pk)
            parent = by_id.get(current.predecessor_response.response_to_id)
            if not parent or parent.pk in seen:
                break
            current = parent
        groups.setdefault(current.pk, []).append(letter)
    query = params.get("q", "").strip().casefold()
    status = params.get("status", "")
    expedients = []
    for group in groups.values():
        group.sort(key=lambda item: (item.letter_date, item.created_at, item.pk))
        def matches(letter):
            response = getattr(letter, "response_letter", None)
            text = [letter.full_number, response.full_number if response else ""]
            text += [p.equipment.code for p in letter.presentations.all()]
            text += [m.equipment.code for m in letter.requested_movements.all()]
            return (not query or any(query in value.casefold() for value in text)) and (
                status not in ("pending", "answered") or bool(response) == (status == "answered")
            )
        if any(matches(letter) for letter in group):
            expedients.append(group)
    expedients.sort(key=lambda group: (group[0].letter_date, group[0].pk), reverse=True)
    return expedients

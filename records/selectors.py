"""Consultas de lectura de registros.

Este modulo concentra la construccion de querysets y los indicadores del
dashboard. Las vistas solo traducen parametros HTTP a llamadas de lectura.
"""

from django.db.models import Q

from .models import Equipment, EquipmentMovement, Evaluation, Letter, Presentation


def filtered_presentations(params):
    """Devuelve presentaciones filtradas y los valores activos del filtro."""
    queryset = Presentation.objects.select_related(
        "cpc_letter", "equipment", "evaluation", "evaluation__response_letter"
    )
    query = params.get("q", "").strip()
    result = params.get("result", "").strip()
    operational_status = params.get("status", "").strip()
    if query:
        queryset = queryset.filter(
            Q(equipment__code__icontains=query)
            | Q(cpc_letter__full_number__icontains=query)
            | Q(equipment_type__icontains=query)
            | Q(evaluation__response_letter__full_number__icontains=query)
        )
    if result:
        queryset = queryset.filter(evaluation__result=result)
    if operational_status:
        queryset = queryset.filter(equipment__operational_status=operational_status)
    return queryset, query, result, operational_status


def demobilization_movements():
    return EquipmentMovement.objects.select_related(
        "equipment", "request_letter", "response_letter"
    ).order_by("-movement_date", "equipment__code")


def dashboard_metrics():
    """Calcula los contadores resumidos que muestra la pantalla principal."""
    return {
        "total": Presentation.objects.count(),
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
    }

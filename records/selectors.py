"""Consultas de lectura de registros.

Este modulo concentra la construccion de querysets y los indicadores del
dashboard. Las vistas solo traducen parametros HTTP a llamadas de lectura.
"""

from django.db.models import Q

from .models import Evaluation, Letter, Presentation


def filtered_presentations(params):
    """Devuelve presentaciones filtradas y los valores activos del filtro."""
    queryset = Presentation.objects.select_related(
        "cpc_letter", "equipment", "evaluation", "evaluation__response_letter"
    )
    query = params.get("q", "").strip()
    result = params.get("result", "").strip()
    if query:
        queryset = queryset.filter(
            Q(equipment__code__icontains=query)
            | Q(cpc_letter__full_number__icontains=query)
            | Q(equipment_type__icontains=query)
            | Q(evaluation__response_letter__full_number__icontains=query)
        )
    if result:
        queryset = queryset.filter(evaluation__result=result)
    return queryset, query, result


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
        "pending_letters": Letter.objects.filter(
            direction=Letter.Direction.CPC_AAM, response_letter__isnull=True
        ).count(),
    }

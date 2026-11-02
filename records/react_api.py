"""Datos del panel para la interfaz React."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from .selectors import dashboard_metrics, filtered_records


def date(value):
    return value.strftime('%d/%m/%Y') if value else '—'


def pdf(letter):
    return reverse("letter_pdf", args=[letter.pk]) if letter and letter.pdf else None


@login_required
def dashboard_data(request):
    records, query, result, status = filtered_records(request.GET)
    rows = []
    for record in records:
        letter, equipment = record['cpc_letter'], record['equipment']
        evaluation, response, movement = record['evaluation'], record['response_letter'], record['movement']
        rows.append({
            'id': f"{record['kind']}-{record['source'].pk}",
            'cpc': letter.correlative, 'number': letter.full_number,
            'date': date(letter.letter_date), 'reception': date(letter.reception_date),
            'event': record['event_label'], 'equipment': equipment.code,
            'equipmentType': record['equipment_type'],
            'movementDetail': f'{movement.brand} {movement.model} · {movement.serial}' if movement else '',
            'status': record['operational_status'], 'statusLabel': record['operational_label'],
            'resolveStatusUrl': reverse('resolve_equipment_status', args=[equipment.pk]) if equipment.operational_status == 'REVIEW' and request.user.has_perm('records.manage_records') else None,
            'statusDate': date(movement.movement_date if movement else equipment.retired_at) if movement or equipment.retired_at else '',
            'result': evaluation.result if evaluation else '',
            'resultLabel': evaluation.get_result_display() if evaluation else ('No aplica' if movement else 'Pendiente'),
            'detail': evaluation.detail if evaluation else '',
            'response': response.correlative if response else '—',
            'responseDate': date(response.letter_date) if response else '',
            'editUrl': reverse('edit_presentation', args=[record['source'].pk]) if record['kind'] == 'presentation' and request.user.has_perm('records.manage_records') else None,
            'deleteUrl': reverse('delete_letter', args=[letter.pk]) if request.user.has_perm('records.remove_records') else None,
            'cpcPdf': pdf(letter), 'responsePdf': pdf(response),
        })
    return JsonResponse({'canEdit': request.user.has_perm('records.manage_records'), 'metrics': dashboard_metrics(), 'records': rows, 'filters': {'q': query, 'result': result, 'status': status}})

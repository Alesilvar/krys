"""Datos de presentación para los componentes React; las validaciones viven en Django."""
from datetime import date, datetime
from django import forms, template
from django.urls import reverse
from django.utils.html import json_script
from django.middleware.csrf import get_token
from records.models import Evaluation

register = template.Library()


def serialize_form(form):
    fields = []
    for field in form:
        widget = field.field.widget
        value = field.value()
        if isinstance(value, (date, datetime)):
            value = value.isoformat()[:10]
        if isinstance(widget, (forms.FileInput, forms.PasswordInput)):
            value = ''
        fields.append({
            'name': field.html_name, 'id': field.id_for_label, 'label': str(field.label),
            'value': str(value) if value is not None else '',
            'type': 'textarea' if isinstance(widget, forms.Textarea) else 'select' if isinstance(widget, forms.Select) else widget.input_type,
            'required': field.field.required, 'help': str(field.help_text or ''),
            'errors': [str(e) for e in field.errors],
            'choices': [[str(v), str(label)] for v, label in getattr(field.field, 'choices', [])],
            'attrs': {**{k: v for k, v in widget.attrs.items() if k in ('accept', 'rows', 'placeholder', 'multiple')}, 'multiple': bool(getattr(widget, 'allow_multiple_selected', False))},
        })
    return {'fields': fields, 'errors': [str(e) for e in form.non_field_errors()]}


def pdf(letter):
    return reverse("letter_pdf", args=[letter.pk]) if letter and letter.pdf else None


def shortdate(value):
    return value.strftime('%d/%m/%Y') if value else ''


def serialize_letter(letter):
    response = getattr(letter, 'response_letter', None)
    presentations = []
    for item in letter.presentations.all():
        try:
            ev = item.evaluation
        except Evaluation.DoesNotExist:
            ev = None
        presentations.append({'id': item.pk, 'code': item.equipment.code, 'type': item.equipment_type,
            'procedure': item.procedure_type, 'additional': item.additional_data,
            'evaluation': f'{ev.get_result_display()}: {ev.detail}' if ev else ''})
    movements = [{'id': m.pk, 'code': m.equipment.code, 'type': m.equipment_type,
        'status': m.get_status_display(), 'date': shortdate(m.movement_date), 'brand': m.brand,
        'model': m.model, 'serial': m.serial, 'year': m.year} for m in letter.requested_movements.all()]
    return {'id': letter.pk, 'number': letter.full_number, 'correlative': letter.correlative,
        'date': shortdate(letter.letter_date), 'reception': shortdate(letter.reception_date),
        'purpose': letter.get_purpose_display(), 'pdf': pdf(letter),
        'response': {'number': response.full_number, 'date': shortdate(response.letter_date), 'pdf': pdf(response)} if response else None,
        'presentations': presentations, 'movements': movements}


def build_payload(context):
    request = context['request']
    page = request.resolver_match.url_name
    data = {'page': page, 'csrf': get_token(request), 'authenticated': request.user.is_authenticated,
            'canEdit': request.user.has_perm('records.manage_records'),
            'canDelete': request.user.has_perm('records.remove_records'),
            'username': (request.user.get_full_name() or request.user.get_username()) if request.user.is_authenticated else '',
            'messages': [{'text': str(m), 'tags': m.tags} for m in context.get('messages', [])]}
    if page == 'profile' and request.user.is_authenticated:
        data['profile'] = {'username': request.user.get_username(), 'name': request.user.get_full_name(), 'email': request.user.email}
    if context.get('form'):
        data['form'] = serialize_form(context['form'])
    if page == 'upload_letters' or page == 'confirm_upload':
        data['page'] = 'upload_letters'
        preview = context.get('preview')
        data['preview'] = ({'rows': preview['rows'], 'movement_rows': preview.get('movement_rows', []),
            'warnings': preview['warnings'], 'documents': [{'correlative': d['correlative'], 'direction': d['direction']} for d in preview['documents']]} if preview else None)
    if page == 'letters':
        data.update(query=context.get('query', ''), status=context.get('status', ''),
                    expedients=[[serialize_letter(letter) for letter in group] for group in context['expedients']])
    if page == 'edit_presentation':
        p = context['presentation']
        data['presentation'] = {'code': p.equipment.code, 'correlative': p.cpc_letter.correlative, 'procedure': p.procedure_type}
    if page in ('edit_letter', 'edit_movement', 'delete_letter'):
        letter = context['letter']
        data['letter'] = {'number': letter.full_number, 'correlative': letter.correlative}
        if page == 'delete_letter':
            response = getattr(letter, 'response_letter', None)
            data['letter'].update(presentations=letter.presentations.count(), movements=letter.requested_movements.count(), response=response.full_number if response else '')
        if context.get('movement'):
            data['movement'] = {'code': context['movement'].equipment.code}
    return data


@register.simple_tag(takes_context=True)
def react_payload(context):
    return json_script(build_payload(context), 'krys-data')

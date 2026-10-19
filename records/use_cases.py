"""Casos de uso de escritura del modulo de registros.

Las operaciones de negocio viven aqui para que puedan invocarse desde vistas,
comandos o una API futura sin duplicar reglas.
"""

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction

from .models import AuditEvent, Equipment, Evaluation, Letter, Presentation


def letter_correlative(full_number):
    return int(full_number.rsplit("-", 1)[-1])


@transaction.atomic
def create_manual_record(data, user):
    """Registra una presentacion manual y devuelve la fila creada."""
    cpc = Letter.objects.filter(full_number=data["cpc_full_number"]).first()
    if cpc:
        if cpc.direction != Letter.Direction.CPC_AAM:
            raise ValidationError("El número indicado no corresponde a una carta CPC.")
        if cpc.letter_date != data["cpc_date"]:
            raise ValidationError("La fecha CPC no coincide con la carta ya registrada.")
        if cpc.reception_date != data["reception_date"]:
            raise ValidationError(
                "La fecha de recepción no coincide con la carta ya registrada."
            )
    else:
        predecessor = None
        if data["predecessor_aam"]:
            predecessor = Letter.objects.filter(
                full_number=data["predecessor_aam"],
                direction=Letter.Direction.AAM_CPC,
            ).first()
            if predecessor is None:
                raise ValidationError("La respuesta AAM anterior aún no está registrada.")
        cpc = Letter.objects.create(
            full_number=data["cpc_full_number"],
            correlative=letter_correlative(data["cpc_full_number"]),
            direction=Letter.Direction.CPC_AAM,
            letter_date=data["cpc_date"],
            reception_date=data["reception_date"],
            predecessor_response=predecessor,
            source=Letter.Source.MANUAL,
            pdf=data["cpc_pdf"],
            created_by=user,
        )
    if data["cpc_pdf"] and not cpc.pdf:
        cpc.pdf = data["cpc_pdf"]
        cpc.save(update_fields=["pdf", "updated_at"])

    response = getattr(cpc, "response_letter", None)
    if data["aam_full_number"]:
        by_number = Letter.objects.filter(full_number=data["aam_full_number"]).first()
        if response and response.full_number != data["aam_full_number"]:
            raise ValidationError("Esta carta CPC ya tiene otra respuesta AAM.")
        if by_number and by_number.response_to_id != cpc.id:
            raise ValidationError("La respuesta AAM ya está vinculada a otra carta CPC.")
        response = response or by_number
        if response and response.letter_date != data["aam_date"]:
            raise ValidationError("La fecha AAM no coincide con la carta ya registrada.")
        if response is None:
            response = Letter.objects.create(
                full_number=data["aam_full_number"],
                correlative=letter_correlative(data["aam_full_number"]),
                direction=Letter.Direction.AAM_CPC,
                letter_date=data["aam_date"],
                source=Letter.Source.MANUAL,
                pdf=data["aam_pdf"],
                response_to=cpc,
                created_by=user,
            )
        elif data["aam_pdf"] and not response.pdf:
            response.pdf = data["aam_pdf"]
            response.save(update_fields=["pdf", "updated_at"])

    equipment, _ = Equipment.objects.get_or_create(
        code=data["equipment_code"].strip().upper()
    )
    presentation = Presentation.objects.create(
        cpc_letter=cpc,
        equipment=equipment,
        equipment_type=data["equipment_type"].strip(),
        additional_data=data["additional_data"].strip(),
        created_by=user,
    )
    if data["result"]:
        Evaluation.objects.create(
            presentation=presentation,
            response_letter=response,
            result=data["result"],
            detail=data["detail"].strip(),
            updated_by=user,
        )
    AuditEvent.objects.create(
        user=user,
        action=AuditEvent.Action.CREATE,
        object_type="Presentation",
        object_id=str(presentation.pk),
        details={"source": "manual"},
    )
    return presentation


@transaction.atomic
def update_presentation(presentation, data, user):
    """Actualiza una presentacion y las cartas compartidas asociadas."""
    old = {
        "cpc_full_number": presentation.cpc_letter.full_number,
        "cpc_date": str(presentation.cpc_letter.letter_date),
        "reception_date": str(presentation.cpc_letter.reception_date),
        "equipment_type": presentation.equipment_type,
        "equipment_code": presentation.equipment.code,
        "additional_data": presentation.additional_data,
    }
    equipment, _ = Equipment.objects.get_or_create(
        code=data["equipment_code"].strip().upper()
    )
    cpc = presentation.cpc_letter
    cpc.full_number = data["cpc_full_number"]
    cpc.correlative = letter_correlative(cpc.full_number)
    cpc.letter_date = data["cpc_date"]
    cpc.reception_date = data["reception_date"]
    if data["cpc_pdf"]:
        cpc.pdf = data["cpc_pdf"]
    cpc.save()

    presentation.equipment = equipment
    presentation.equipment_type = data["equipment_type"].strip()
    presentation.additional_data = data["additional_data"].strip()
    presentation.save()

    result = data["result"]
    response = getattr(cpc, "response_letter", None)
    if data["aam_full_number"]:
        if response is None:
            response = Letter.objects.create(
                full_number=data["aam_full_number"],
                correlative=letter_correlative(data["aam_full_number"]),
                direction=Letter.Direction.AAM_CPC,
                letter_date=data["aam_date"],
                source=Letter.Source.MANUAL,
                pdf=data["aam_pdf"],
                response_to=cpc,
                created_by=user,
            )
        else:
            response.full_number = data["aam_full_number"]
            response.correlative = letter_correlative(response.full_number)
            response.letter_date = data["aam_date"]
            if data["aam_pdf"]:
                response.pdf = data["aam_pdf"]
            response.save()
    if result:
        Evaluation.objects.update_or_create(
            presentation=presentation,
            defaults={
                "response_letter": response,
                "result": result,
                "detail": data["detail"].strip(),
                "updated_by": user,
            },
        )
    else:
        Evaluation.objects.filter(presentation=presentation).delete()

    AuditEvent.objects.create(
        user=user,
        action=AuditEvent.Action.UPDATE,
        object_type="Presentation",
        object_id=str(presentation.pk),
        details={
            "before": old,
            "after": {
                key: str(value) if value is not None else "" for key, value in data.items()
            },
        },
    )
    return presentation


def delete_cpc_letter(letter, user):
    """Elimina una cadena CPC/AAM y sus archivos, conservando la auditoria."""
    response = getattr(letter, "response_letter", None)
    files = [item.pdf.name for item in (letter, response) if item and item.pdf]
    number = letter.full_number
    with transaction.atomic():
        AuditEvent.objects.create(
            user=user,
            action=AuditEvent.Action.DELETE,
            object_type="Letter",
            object_id=number,
            details={"permanent": True},
        )
        letter.delete()
    for name in files:
        default_storage.delete(name)
    return number

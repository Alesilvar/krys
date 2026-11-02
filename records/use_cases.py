"""Casos de uso de escritura del modulo de registros.

Las operaciones de negocio viven aqui para que puedan invocarse desde vistas,
comandos o una API futura sin duplicar reglas.
"""

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction

from .models import AuditEvent, Equipment, Evaluation, Letter, Presentation
from .equipment_rules import ensure_equipment_type, refresh_equipment_status


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
    equipment_type = ensure_equipment_type(equipment, data["equipment_type"])
    presentation = Presentation.objects.create(
        cpc_letter=cpc,
        equipment=equipment,
        equipment_type=equipment_type,
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
    refresh_equipment_status(equipment)
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
    previous_evaluation = Evaluation.objects.filter(presentation=presentation).select_related("response_letter").first()
    previous_response = getattr(presentation.cpc_letter, "response_letter", None)
    old.update({
        "result": previous_evaluation.result if previous_evaluation else "",
        "detail": previous_evaluation.detail if previous_evaluation else "",
        "aam_full_number": previous_response.full_number if previous_response else "",
        "aam_date": str(previous_response.letter_date) if previous_response else "",
        "cpc_pdf": presentation.cpc_letter.pdf.name if presentation.cpc_letter.pdf else "",
        "aam_pdf": previous_response.pdf.name if previous_response and previous_response.pdf else "",
    })
    previous_equipment = presentation.equipment
    equipment, _ = Equipment.objects.get_or_create(
        code=data["equipment_code"].strip().upper()
    )
    equipment_type = ensure_equipment_type(equipment, data["equipment_type"])
    cpc = presentation.cpc_letter
    cpc.full_number = data["cpc_full_number"]
    cpc.correlative = letter_correlative(cpc.full_number)
    cpc.letter_date = data["cpc_date"]
    cpc.reception_date = data["reception_date"]
    if data["cpc_pdf"]:
        cpc.pdf = data["cpc_pdf"]
    cpc.save()

    presentation.equipment = equipment
    presentation.equipment_type = equipment_type
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

    refresh_equipment_status(equipment)
    if previous_equipment.pk != equipment.pk:
        refresh_equipment_status(previous_equipment)
    for sibling in Equipment.objects.filter(presentations__cpc_letter=cpc).exclude(pk__in=[equipment.pk, previous_equipment.pk]).distinct():
        refresh_equipment_status(sibling)

    AuditEvent.objects.create(
        user=user,
        action=AuditEvent.Action.UPDATE,
        object_type="Presentation",
        object_id=str(presentation.pk),
        details={
            "before": old,
            "after": {
                **{key: str(value) if value is not None else "" for key, value in data.items()},
                "cpc_pdf": cpc.pdf.name if cpc.pdf else "",
                "aam_pdf": response.pdf.name if response and response.pdf else "",
            },
        },
    )
    return presentation


def delete_cpc_letter(letter, user):
    """Elimina una cadena CPC/AAM y sus archivos, conservando la auditoria."""
    response = getattr(letter, "response_letter", None)
    files = [item.pdf.name for item in (letter, response) if item and item.pdf]
    equipment_ids = set(letter.presentations.values_list("equipment_id", flat=True))
    equipment_ids.update(
        letter.requested_movements.values_list("equipment_id", flat=True)
    )
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
        for equipment in Equipment.objects.filter(pk__in=equipment_ids):
            refresh_equipment_status(equipment)
    for name in files:
        default_storage.delete(name)
    return number


@transaction.atomic
def update_letter_and_movement(letter, data, user, movement=None):
    """Edita la pareja y, opcionalmente, un equipo de desmovilización."""
    from .models import EquipmentMovement
    from django.utils import timezone
    old_response = getattr(letter, "response_letter", None)
    before = {
        "cpc_full_number": letter.full_number,
        "cpc_date": str(letter.letter_date),
        "reception_date": str(letter.reception_date or ""),
        "cpc_pdf": letter.pdf.name if letter.pdf else "",
        "aam_full_number": old_response.full_number if old_response else "",
        "aam_date": str(old_response.letter_date) if old_response else "",
        "aam_pdf": old_response.pdf.name if old_response and old_response.pdf else "",
    }
    if movement:
        before.update({"equipment_code": movement.equipment.code,
                       "equipment_type": movement.equipment_type,
                       **{field: str(getattr(movement, field) or "") for field in
                          ("movement_date", "brand", "model", "serial", "year")}})
    response = getattr(letter, "response_letter", None)
    if response and not data["aam_full_number"]:
        raise ValidationError("No se puede quitar una respuesta existente desde la edición.")
    letter.full_number = data["cpc_full_number"]
    letter.correlative = letter_correlative(letter.full_number)
    letter.letter_date = data["cpc_date"]
    letter.reception_date = data["reception_date"]
    if data["cpc_pdf"]:
        letter.pdf = data["cpc_pdf"]
    letter.save()
    if data["aam_full_number"]:
        if response is None:
            response = Letter(direction=Letter.Direction.AAM_CPC, response_to=letter, created_by=user, source=Letter.Source.MANUAL, purpose=letter.purpose)
        response.full_number = data["aam_full_number"]
        response.correlative = letter_correlative(response.full_number)
        response.letter_date = data["aam_date"]
        if data["aam_pdf"]:
            response.pdf = data["aam_pdf"]
        response.save()
    affected = set(letter.requested_movements.values_list("equipment_id", flat=True))
    affected.update(letter.presentations.values_list("equipment_id", flat=True))
    if movement:
        affected.add(movement.equipment_id)
        equipment, _ = Equipment.objects.get_or_create(code=data["equipment_code"].strip().upper())
        movement.equipment = equipment
        movement.equipment_type = ensure_equipment_type(equipment, data["equipment_type"])
        for field in ("movement_date", "brand", "model", "serial", "year"):
            setattr(movement, field, data[field])
        movement.save()
        affected.add(equipment.pk)
    if response and letter.purpose == Letter.Purpose.DEMOBILIZATION:
        letter.requested_movements.exclude(response_letter=response, status=EquipmentMovement.Status.AUTHORIZED).update(
            response_letter=response, status=EquipmentMovement.Status.AUTHORIZED, updated_at=timezone.now()
        )
    for equipment in Equipment.objects.filter(pk__in=affected):
        refresh_equipment_status(equipment)
    AuditEvent.objects.create(user=user, action=AuditEvent.Action.UPDATE, object_type="Letter", object_id=str(letter.pk), details={"before": before, "after": {**{key: str(value) if value is not None else "" for key, value in data.items()}, "cpc_pdf": letter.pdf.name if letter.pdf else "", "aam_pdf": response.pdf.name if response and response.pdf else ""}})

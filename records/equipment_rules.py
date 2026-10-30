"""Reglas compartidas de identidad, tipo y estado actual de los equipos."""

from __future__ import annotations

import re
import unicodedata

from django.core.exceptions import ValidationError

from .models import Equipment, EquipmentMovement, Evaluation


TYPE_ALIASES = {
    "camion volquete": "Volquete",
    "volquete": "Volquete",
    "camioneta": "Camioneta",
    "camion grua": "Camión grúa",
    "excavadora": "Excavadora",
    "retroexcavadora": "Retroexcavadora",
    "cisterna de agua": "Cisterna de Agua",
    "cisterna de combustible": "Cisterna de Combustible",
}


def comparable_equipment_type(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def canonical_equipment_type(value):
    clean_value = re.sub(r"\s+", " ", value or "").strip()
    return TYPE_ALIASES.get(comparable_equipment_type(clean_value), clean_value)


def ensure_equipment_type(equipment, equipment_type):
    """Asigna el tipo una vez y rechaza reutilizar la placa para otro tipo."""
    incoming = canonical_equipment_type(equipment_type)
    current = canonical_equipment_type(equipment.equipment_type)
    if current and comparable_equipment_type(current) != comparable_equipment_type(incoming):
        raise ValidationError(
            f"La placa {equipment.code} ya pertenece al tipo {current}; "
            f"no puede registrarse como {incoming}."
        )
    if not current:
        equipment.equipment_type = incoming
        equipment.save(update_fields=["equipment_type"])
    return incoming


def refresh_equipment_status(equipment):
    """Recalcula el estado usando la aprobación o movimiento más reciente."""
    latest_approval = (
        Evaluation.objects.filter(
            presentation__equipment=equipment,
            result=Evaluation.Result.APPROVED,
        )
        .order_by("-updated_at")
        .first()
    )
    latest_movement = (
        EquipmentMovement.objects.filter(equipment=equipment)
        .order_by("-updated_at")
        .first()
    )
    movement_is_latest = bool(
        latest_movement
        and (
            latest_approval is None
            or latest_movement.updated_at >= latest_approval.updated_at
        )
    )
    if movement_is_latest and latest_movement.status == EquipmentMovement.Status.AUTHORIZED:
        equipment.operational_status = Equipment.OperationalStatus.RETIRED
        equipment.retired_at = latest_movement.movement_date
    elif movement_is_latest:
        equipment.operational_status = Equipment.OperationalStatus.REQUESTED
        equipment.retired_at = None
    else:
        equipment.operational_status = Equipment.OperationalStatus.ACTIVE
        equipment.retired_at = None
    equipment.save(update_fields=["operational_status", "retired_at"])

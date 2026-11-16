"""Reglas compartidas de identidad, tipo y estado actual de los equipos."""

from __future__ import annotations

import re
import unicodedata

from django.core.exceptions import ValidationError

from .models import Equipment, EquipmentMovement, Evaluation


EQUIPMENT_TYPES = (
    "Ambulancia", "Automóvil", "Camioneta", "Camión baranda", "Camión furgón",
    "Camión grúa", "Camión volquete", "Cargador frontal",
    "Cisterna de agua no potable", "Cisterna de agua potable", "Cisterna de combustible",
    "Excavadora", "Furgoneta", "Grúa telescópica", "Grúa sobre orugas",
    "Minicargador", "Perforadora hidráulica", "Plataforma elevadora",
    "Retroexcavadora", "Rodillo compactador", "Tractocamión", "Tractor sobre orugas",
)


def comparable_equipment_type(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", normalized).strip().casefold()


TYPE_ALIASES = {comparable_equipment_type(name): name for name in EQUIPMENT_TYPES}
TYPE_ALIASES.update({
    "volquete": "Camión volquete",
    "volquete faw": "Camión volquete",
    "excavadora komatsu": "Excavadora",
    "excavadora sobre orugas": "Excavadora",
    "camion pick-up": "Camioneta",
    "camioneta pick-up": "Camioneta",
    "camioneta suv": "Camioneta",
    "rodillo bomag": "Rodillo compactador",
    "rodillo bermero": "Rodillo compactador",
    "rodillo vibrante": "Rodillo compactador",
    "grua de celosia sobre orugas": "Grúa sobre orugas",
    "grua movil sobre orugas con pluma de celosia": "Grúa sobre orugas",
    "grua telescopica movil": "Grúa telescópica",
    "mini cargador": "Minicargador",
    "camion cisterna de combustible": "Cisterna de combustible",
    "plataforma genie": "Plataforma elevadora",
    "plataforma jlg": "Plataforma elevadora",
    "manlift": "Plataforma elevadora",
    "scissor lift": "Plataforma elevadora",
})


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


def analyze_equipment_status(equipment):
    """Determina el estado por fechas documentales sin modificar datos."""
    import hashlib
    import json

    events = []
    approvals = Evaluation.objects.filter(presentation__equipment=equipment, result=Evaluation.Result.APPROVED).select_related("response_letter", "presentation__cpc_letter")
    for evaluation in approvals:
        response = evaluation.response_letter
        events.append({"key": f"approval:{evaluation.pk}", "kind": "approval", "date": response.letter_date.isoformat(),
                       "label": f"Aprobación {response.full_number}", "letter": response.full_number,
                       "cpc": evaluation.presentation.cpc_letter.full_number,
                       "cpc_date": evaluation.presentation.cpc_letter.letter_date.isoformat(),
                       "detail": evaluation.detail, "response_pdf": response.pdf.name or "",
                       "cpc_pdf": evaluation.presentation.cpc_letter.pdf.name or "", "status": Equipment.OperationalStatus.ACTIVE})
    movements = EquipmentMovement.objects.filter(equipment=equipment).select_related("request_letter", "response_letter")
    for movement in movements:
        authorized = movement.status == EquipmentMovement.Status.AUTHORIZED
        letter = movement.response_letter if authorized else movement.request_letter
        events.append({"key": f"movement:{movement.pk}", "kind": "movement", "date": letter.letter_date.isoformat() if letter else "",
                       "label": f"{'Retiro autorizado' if authorized else 'Retiro solicitado'} {letter.full_number if letter else '(sin respuesta)'}",
                       "letter": letter.full_number if letter else "", "request": movement.request_letter.full_number,
                       "request_date": movement.request_letter.letter_date.isoformat(),
                       "request_pdf": movement.request_letter.pdf.name or "", "response_pdf": movement.response_letter.pdf.name if movement.response_letter and movement.response_letter.pdf else "",
                       "brand": movement.brand, "model": movement.model, "serial": movement.serial, "year": movement.year,
                       "departure": movement.movement_date.isoformat(),
                       "status": Equipment.OperationalStatus.RETIRED if authorized else Equipment.OperationalStatus.REQUESTED})
    events.sort(key=lambda e: e["key"])
    fingerprint = hashlib.sha256(json.dumps(events, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if not events:
        return {"status": Equipment.OperationalStatus.ACTIVE, "retired_at": None, "events": [], "conflicts": [], "fingerprint": fingerprint}
    if any(not event["date"] for event in events):
        return {"status": Equipment.OperationalStatus.REVIEW, "retired_at": None, "events": events, "conflicts": [], "fingerprint": fingerprint}
    latest_date = max(event["date"] for event in events)
    latest = [event for event in events if event["date"] == latest_date]
    kinds = {event["kind"] for event in latest}
    resolution = equipment.status_resolution or {}
    selected = next((event for event in latest if event["key"] == resolution.get("selected")), None) if resolution.get("fingerprint") == fingerprint else None
    if len(kinds) > 1 and not selected:
        return {"status": Equipment.OperationalStatus.REVIEW, "retired_at": None, "events": events, "conflicts": latest, "fingerprint": fingerprint}
    if not selected:
        # Multiple retirements on the same day are ordered deterministically, with an authorization taking precedence.
        selected = max(latest, key=lambda event: (event["status"] == Equipment.OperationalStatus.RETIRED, event["key"]))
    retired_at = selected.get("departure") if selected["status"] == Equipment.OperationalStatus.RETIRED else None
    return {"status": selected["status"], "retired_at": retired_at, "events": events, "conflicts": latest if len(kinds) > 1 else [], "fingerprint": fingerprint}


def refresh_equipment_status(equipment):
    """Actualiza el estado sin usar fechas de modificación administrativa."""
    state = analyze_equipment_status(equipment)
    equipment.operational_status = state["status"]
    equipment.retired_at = state["retired_at"]
    equipment.save(update_fields=["operational_status", "retired_at"])

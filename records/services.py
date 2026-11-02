from __future__ import annotations

import shutil
import uuid
from dataclasses import asdict
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils.text import get_valid_filename

from extractor import (
    ExtractionError,
    extract_documents,
    extract_pdf_text,
    is_demobilization,
    parse_cpc,
    parse_demobilization_request,
    parse_demobilization_response,
    parse_letter_identity,
    parse_response,
    validate_demobilization_pair,
)

from .models import (
    AuditEvent,
    Equipment,
    EquipmentMovement,
    Evaluation,
    Letter,
    Presentation,
    ProcessingWarning,
)
from .equipment_rules import (
    canonical_equipment_type,
    comparable_equipment_type,
    ensure_equipment_type,
    refresh_equipment_status,
)


def prepare_preview(uploaded_files):
    batch_id = uuid.uuid4().hex
    pending_dir = settings.MEDIA_ROOT / "pending" / batch_id
    pending_dir.mkdir(parents=True, exist_ok=True)
    uploaded_paths = []
    uploaded_names = {}

    try:
        for index, uploaded in enumerate(uploaded_files):
            if uploaded.content_type not in {"application/pdf", "application/x-pdf"}:
                raise ExtractionError(f"{uploaded.name} no es un archivo PDF válido.")
            if uploaded.size > 10 * 1024 * 1024:
                raise ExtractionError(f"{uploaded.name} supera el límite de 10 MB.")
            safe_name = get_valid_filename(Path(uploaded.name).name)
            path = pending_dir / f"{index:02d}-{safe_name}"
            with path.open("wb") as target:
                for chunk in uploaded.chunks():
                    target.write(chunk)
            with path.open("rb") as uploaded_pdf:
                header = uploaded_pdf.read(5)
            if path.stat().st_size < 5 or header != b"%PDF-":
                raise ExtractionError(f"{uploaded.name} no contiene una cabecera PDF válida.")
            uploaded_paths.append(path)
            uploaded_names[str(path)] = safe_name

        existing_paths = [
            Path(letter.pdf.path)
            for letter in Letter.objects.exclude(pdf="")
            if letter.pdf and default_storage.exists(letter.pdf.name)
        ]
        all_paths = [*existing_paths, *uploaded_paths]
        texts = {path: extract_pdf_text(path) for path in all_paths}
        presentation_paths = [
            path for path in all_paths if not is_demobilization(texts[path])
        ]
        rows, warnings = (
            extract_documents(presentation_paths, texts=texts) if presentation_paths else ([], [])
        )

        demobilization_requests = {}
        demobilization_responses = []
        for source_order, path in enumerate(all_paths):
            text = texts[path]
            if not is_demobilization(text):
                continue
            identity = parse_letter_identity(text, path, source_order)
            if identity.direction == "CPC_AAM":
                request = parse_demobilization_request(text, path, source_order)
                demobilization_requests[request.letter.full_number] = request
            else:
                demobilization_responses.append(
                    parse_demobilization_response(text, path, source_order)
                )
        for response in demobilization_responses:
            if response.letter.referenced_cpc not in demobilization_requests:
                raise ExtractionError(
                    f"{response.letter.full_number} referencia una solicitud de "
                    f"desmovilizacion no proporcionada: {response.letter.referenced_cpc}"
                )

        parsed_documents = []
        all_cpc_by_correlative = {}
        all_aam_by_correlative = {}
        affected_cpc_numbers = set()

        for source_order, path in enumerate(all_paths):
            text = texts[path]
            identity = parse_letter_identity(text, path, source_order)
            is_uploaded = path in uploaded_paths
            purpose = "DEMOBILIZATION" if is_demobilization(text) else "PRESENTATION"
            if purpose == "DEMOBILIZATION" and identity.direction == "CPC_AAM":
                parsed_request = demobilization_requests[identity.full_number]
                parsed = parsed_request.letter
                all_cpc_by_correlative[parsed.correlative] = parsed.full_number
                if is_uploaded:
                    affected_cpc_numbers.add(parsed.full_number)
            elif purpose == "DEMOBILIZATION":
                parsed_response = next(
                    item
                    for item in demobilization_responses
                    if item.letter.full_number == identity.full_number
                )
                parsed = parsed_response.letter
                all_aam_by_correlative[parsed.correlative] = parsed.full_number
                if is_uploaded:
                    affected_cpc_numbers.add(parsed.referenced_cpc)
            elif identity.direction == "CPC_AAM":
                parsed = parse_cpc(text, path, source_order)
                all_cpc_by_correlative[parsed.correlative] = parsed.full_number
                if is_uploaded:
                    affected_cpc_numbers.add(parsed.full_number)
            else:
                parsed_response = parse_response(text, path, source_order)
                parsed = parsed_response.letter
                all_aam_by_correlative[parsed.correlative] = parsed.full_number
                if is_uploaded:
                    affected_cpc_numbers.add(parsed.referenced_cpc)

            if not is_uploaded:
                continue
            if Letter.objects.filter(full_number=parsed.full_number).exists():
                raise ExtractionError(f"La carta {parsed.full_number} ya está registrada.")
            parsed_documents.append(
                {
                    "path": str(path),
                    "original_name": uploaded_names[str(path)],
                    "full_number": parsed.full_number,
                    "correlative": parsed.correlative,
                    "direction": parsed.direction,
                    "purpose": purpose,
                    "letter_date": parsed.letter_date.isoformat(),
                    "referenced_cpc": parsed.referenced_cpc,
                    "referenced_aam": parsed.referenced_aam,
                }
            )

        serialized_rows = []
        for index, row in enumerate(rows):
            cpc_number = all_cpc_by_correlative.get(row.cpc_correlative)
            if cpc_number not in affected_cpc_numbers:
                continue
            data = asdict(row)
            data["cpc_date"] = row.cpc_date.isoformat()
            data["aam_date"] = row.aam_date.isoformat() if isinstance(row.aam_date, date) else ""
            data["cpc_full_number"] = cpc_number
            data["aam_full_number"] = all_aam_by_correlative.get(row.aam_correlative, "")
            data["row_index"] = index
            serialized_rows.append(data)

        movement_rows = []
        responses_by_request = {
            item.letter.referenced_cpc: item for item in demobilization_responses
        }
        for request_number, request in demobilization_requests.items():
            if request_number not in affected_cpc_numbers:
                continue
            response = responses_by_request.get(request_number)
            if response:
                validate_demobilization_pair(request, response)
            for item in request.items:
                movement_rows.append(
                    {
                        "request_full_number": request_number,
                        "request_correlative": request.letter.correlative,
                        "response_full_number": response.letter.full_number if response else "",
                        "response_correlative": response.letter.correlative if response else "",
                        "equipment_code": item.code,
                        "equipment_type": item.equipment_type,
                        "brand": item.brand,
                        "model": item.model,
                        "serial": item.serial,
                        "year": item.year,
                        "movement_date": item.departure_date.isoformat(),
                        "status": "Retirado" if response else "Retiro solicitado",
                    }
                )

        known_types = {
            equipment.code: equipment.equipment_type
            for equipment in Equipment.objects.exclude(equipment_type="")
        }
        batch_types = {}
        for row in [*serialized_rows, *movement_rows]:
            code = row["equipment_code"].upper()
            incoming = canonical_equipment_type(row["equipment_type"])
            current = batch_types.get(code) or known_types.get(code, "")
            if current and comparable_equipment_type(
                canonical_equipment_type(current)
            ) != comparable_equipment_type(incoming):
                raise ExtractionError(
                    f"La placa {code} ya pertenece al tipo "
                    f"{canonical_equipment_type(current)}; no puede registrarse "
                    f"como {incoming}."
                )
            batch_types[code] = incoming
            row["equipment_type"] = incoming

        if not serialized_rows and not movement_rows:
            raise ExtractionError("No se generaron filas para las cartas cargadas.")
        return {
            "batch_id": batch_id,
            "documents": parsed_documents,
            "rows": serialized_rows,
            "movement_rows": movement_rows,
            "warnings": warnings,
        }
    except Exception:
        shutil.rmtree(pending_dir, ignore_errors=True)
        raise


@transaction.atomic
def persist_preview(preview, post_data, user):
    created_letters = {}
    stored_files = []
    affected_equipment = set()
    try:
        for document in preview["documents"]:
            path = Path(document["path"])
            reception = None
            if document["direction"] == "CPC_AAM":
                raw_reception = post_data.get(f"reception_{document['correlative']}")
                if not raw_reception:
                    raise ExtractionError(
                        f"Debes indicar la fecha de recepción de la carta CPC {document['correlative']}."
                    )
                reception = date.fromisoformat(raw_reception)
            letter = Letter(
                full_number=document["full_number"],
                correlative=document["correlative"],
                direction=document["direction"],
                purpose=document.get("purpose", Letter.Purpose.PRESENTATION),
                letter_date=date.fromisoformat(document["letter_date"]),
                reception_date=reception,
                source=Letter.Source.PDF,
                created_by=user,
            )
            with path.open("rb") as source:
                letter.pdf.save(document["original_name"], File(source), save=False)
            stored_files.append(letter.pdf.name)
            letter.save()
            created_letters[letter.full_number] = letter

        for document in preview["documents"]:
            letter = created_letters[document["full_number"]]
            if letter.direction == Letter.Direction.AAM_CPC:
                letter.response_to = created_letters.get(
                    document["referenced_cpc"]
                ) or Letter.objects.filter(full_number=document["referenced_cpc"]).first()
                if letter.response_to is None:
                    raise ExtractionError(
                        f"No existe la carta CPC referenciada por {letter.full_number}."
                    )
            elif document["referenced_aam"]:
                letter.predecessor_response = created_letters.get(
                    document["referenced_aam"]
                ) or Letter.objects.filter(full_number=document["referenced_aam"]).first()
                if letter.predecessor_response is None:
                    raise ExtractionError(
                        f"No existe la respuesta AAM {document['referenced_aam']} necesaria para calcular el trámite."
                    )
            letter.save(update_fields=["response_to", "predecessor_response", "updated_at"])

        for row in preview["rows"]:
            cpc = created_letters.get(row["cpc_full_number"]) or Letter.objects.get(
                full_number=row["cpc_full_number"]
            )
            equipment, _ = Equipment.objects.get_or_create(code=row["equipment_code"].upper())
            row["equipment_type"] = ensure_equipment_type(
                equipment, row["equipment_type"]
            )
            affected_equipment.add(equipment.pk)
            presentation, _ = Presentation.objects.get_or_create(
                cpc_letter=cpc,
                equipment=equipment,
                defaults={
                    "owner": "CPC",
                    "equipment_type": row["equipment_type"],
                    "additional_data": post_data.get(f"additional_{row['row_index']}", ""),
                    "created_by": user,
                },
            )
            if row["aam_full_number"] and row["result"]:
                response_letter = created_letters.get(row["aam_full_number"]) or Letter.objects.get(
                    full_number=row["aam_full_number"]
                )
                result = (
                    Evaluation.Result.APPROVED
                    if row["result"] == "Aprobado"
                    else Evaluation.Result.OBSERVED
                )
                Evaluation.objects.update_or_create(
                    presentation=presentation,
                    defaults={
                        "response_letter": response_letter,
                        "result": result,
                        "detail": row["detail"],
                        "updated_by": user,
                    },
                )

        for row in preview.get("movement_rows", []):
            request_letter = created_letters.get(
                row["request_full_number"]
            ) or Letter.objects.get(full_number=row["request_full_number"])
            response_letter = None
            if row["response_full_number"]:
                response_letter = created_letters.get(
                    row["response_full_number"]
                ) or Letter.objects.get(full_number=row["response_full_number"])
            equipment, _ = Equipment.objects.get_or_create(
                code=row["equipment_code"].upper()
            )
            row["equipment_type"] = ensure_equipment_type(
                equipment, row["equipment_type"]
            )
            affected_equipment.add(equipment.pk)
            status = (
                EquipmentMovement.Status.AUTHORIZED
                if response_letter
                else EquipmentMovement.Status.REQUESTED
            )
            movement, created = EquipmentMovement.objects.get_or_create(
                request_letter=request_letter,
                equipment=equipment,
                defaults={
                    "response_letter": response_letter,
                    "status": status,
                    "movement_date": date.fromisoformat(row["movement_date"]),
                    "equipment_type": row["equipment_type"],
                    "brand": row["brand"],
                    "model": row["model"],
                    "serial": row["serial"],
                    "year": row["year"],
                    "created_by": user,
                },
            )
            if not created and response_letter:
                movement.response_letter = response_letter
                movement.status = status
                movement.save(update_fields=["response_letter", "status", "updated_at"])
        for equipment in Equipment.objects.filter(pk__in=affected_equipment):
            refresh_equipment_status(equipment)

        if preview["warnings"]:
            warning_letter = next(iter(created_letters.values()))
            for warning in preview["warnings"]:
                ProcessingWarning.objects.create(letter=warning_letter, message=warning)

        for letter in created_letters.values():
            AuditEvent.objects.create(
                user=user,
                action=AuditEvent.Action.UPLOAD,
                object_type="Letter",
                object_id=letter.full_number,
                details={"source": "PDF"},
            )
    except Exception:
        for name in stored_files:
            default_storage.delete(name)
        raise
    pending_dir = settings.MEDIA_ROOT / "pending" / preview["batch_id"]
    shutil.rmtree(pending_dir, ignore_errors=True)
    return list(created_letters.values())

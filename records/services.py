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
    parse_cpc,
    parse_letter_identity,
    parse_response,
)

from .models import AuditEvent, Equipment, Evaluation, Letter, Presentation, ProcessingWarning


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
            safe_name = get_valid_filename(Path(uploaded.name).name)
            path = pending_dir / f"{index:02d}-{safe_name}"
            with path.open("wb") as target:
                for chunk in uploaded.chunks():
                    target.write(chunk)
            if path.stat().st_size < 5 or path.read_bytes()[:5] != b"%PDF-":
                raise ExtractionError(f"{uploaded.name} no contiene una cabecera PDF válida.")
            uploaded_paths.append(path)
            uploaded_names[str(path)] = safe_name

        existing_paths = [
            Path(letter.pdf.path)
            for letter in Letter.objects.exclude(pdf="")
            if letter.pdf and default_storage.exists(letter.pdf.name)
        ]
        all_paths = [*existing_paths, *uploaded_paths]
        rows, warnings = extract_documents(all_paths)

        parsed_documents = []
        all_cpc_by_correlative = {}
        all_aam_by_correlative = {}
        affected_cpc_numbers = set()

        for source_order, path in enumerate(all_paths):
            text = extract_pdf_text(path)
            identity = parse_letter_identity(text, path, source_order)
            is_uploaded = path in uploaded_paths
            if identity.direction == "CPC_AAM":
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

        if not serialized_rows:
            raise ExtractionError("No se generaron filas para las cartas cargadas.")
        return {
            "batch_id": batch_id,
            "documents": parsed_documents,
            "rows": serialized_rows,
            "warnings": warnings,
        }
    except Exception:
        shutil.rmtree(pending_dir, ignore_errors=True)
        raise


@transaction.atomic
def persist_preview(preview, post_data, user):
    created_letters = {}
    stored_files = []
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
                letter_date=date.fromisoformat(document["letter_date"]),
                reception_date=reception,
                source=Letter.Source.PDF,
                created_by=user,
            )
            with path.open("rb") as source:
                letter.pdf.save(document["original_name"], File(source), save=False)
            letter.save()
            stored_files.append(letter.pdf.name)
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
            presentation, _ = Presentation.objects.update_or_create(
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
    finally:
        pending_dir = settings.MEDIA_ROOT / "pending" / preview["batch_id"]
        shutil.rmtree(pending_dir, ignore_errors=True)
    return list(created_letters.values())

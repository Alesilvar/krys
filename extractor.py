#!/usr/bin/env python3
"""Prototipo aislado para extraer cartas CPC y respuestas AAM.

No persiste datos ni forma parte de una arquitectura web. Recibe uno o mas PDF,
relaciona las respuestas con la carta CPC indicada en Referencia y presenta una
fila por equipo.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable


LETTER_RE = re.compile(
    r"CARTA\s+No\.?\s*(PSR2-F2-(?:CPC-AAM|AAM-CPC)-GEN-GLB-CAR-(\d+))",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(
    r"Referencia:\s*(?:a\)\s*)?Carta\s+No\.?\s*"
    r"(PSR2-F2-CPC-AAM-GEN-GLB-CAR-\d+)",
    re.IGNORECASE,
)
CODE_RE = r"[A-Z0-9]{2,}(?:-[A-Z0-9]{2,})+"
EQUIPMENT_TYPE_RE = (
    r"Excavadora|Retroexcavadora|Volquete|Camión\s+Volquete|"
    r"Cisterna\s+de\s+(?:Combustible|Agua)"
)
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


class ExtractionError(RuntimeError):
    """El documento no cumple una condicion necesaria para la extraccion."""


@dataclass(frozen=True)
class Equipment:
    code: str
    equipment_type: str


@dataclass
class Letter:
    full_number: str
    correlative: int
    letter_date: date
    direction: str
    source_path: Path
    source_order: int
    equipment: list[Equipment] = field(default_factory=list)
    referenced_cpc: str | None = None
    referenced_aam: str | None = None


@dataclass(frozen=True)
class Evaluation:
    code: str
    result: str
    detail: str


@dataclass
class ParsedResponse:
    letter: Letter
    evaluations: dict[str, Evaluation]
    response_only_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OutputRow:
    owner: str
    cpc_correlative: int
    cpc_date: date
    reception_date: str
    procedure_type: str
    equipment_type: str
    equipment_code: str
    result: str
    detail: str
    aam_correlative: int | str
    aam_date: date | str
    additional_data: str


def extract_pdf_text(path: Path) -> str:
    if not path.is_file():
        raise ExtractionError(f"No existe el archivo: {path}")
    if path.suffix.lower() != ".pdf":
        raise ExtractionError(f"El archivo no es PDF: {path}")

    process = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode != 0:
        error = process.stderr.decode("utf-8", errors="replace").strip()
        raise ExtractionError(f"No se pudo leer {path.name}: {error}")
    text = process.stdout.decode("utf-8", errors="replace")
    if not text.strip():
        raise ExtractionError(f"El PDF no contiene texto seleccionable: {path.name}")
    return text


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n,;")


def normalized_for_matching(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return normalize_space(value).casefold()


def normalize_code(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def parse_spanish_date(text: str) -> date:
    match = re.search(
        r"Lima,\s*(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+(\d{4})",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise ExtractionError("No se encontro la fecha principal de la carta")
    month_name = normalized_for_matching(match.group(2))
    month = MONTHS.get(month_name)
    if month is None:
        raise ExtractionError(f"Mes no reconocido: {match.group(2)}")
    return date(int(match.group(3)), month, int(match.group(1)))


def parse_letter_identity(text: str, path: Path, source_order: int) -> Letter:
    match = LETTER_RE.search(text)
    if not match:
        raise ExtractionError(f"No se encontro el numero de carta en {path.name}")
    full_number = match.group(1).upper()
    direction = "CPC_AAM" if "-CPC-AAM-" in full_number else "AAM_CPC"
    return Letter(
        full_number=full_number,
        correlative=int(match.group(2)),
        letter_date=parse_spanish_date(text),
        direction=direction,
        source_path=path,
        source_order=source_order,
    )


def parse_cpc(text: str, path: Path, source_order: int) -> Letter:
    letter = parse_letter_identity(text, path, source_order)
    if letter.direction != "CPC_AAM":
        raise ExtractionError(f"{path.name} no es una carta CPC hacia AAM")

    reference_section = re.search(
        r"Referencia:\s*(.*?)\s*Antecedentes:",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if reference_section:
        aam_reference = re.search(
            r"PSR2-F2-AAM-CPC-GEN-GLB-CAR-\d+",
            reference_section.group(1),
            re.IGNORECASE,
        )
        if aam_reference:
            # La primera AAM de la seccion Referencia define la cadena de
            # subsanacion. Las menciones narrativas del cuerpo no se usan.
            letter.referenced_aam = aam_reference.group(0).upper()

    section = re.search(
        r"El detalle de los equipos considerados es el siguiente:\s*(.*?)\s*Asimismo,",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if section:
        equipment_pattern = re.compile(
            rf"^\s*\d+\.\s+(.+?)\s+({CODE_RE})[,.;]?\s*$",
            re.MULTILINE,
        )
        for match in equipment_pattern.finditer(section.group(1)):
            letter.equipment.append(
                Equipment(
                    code=normalize_code(match.group(2)),
                    equipment_type=normalize_space(match.group(1)),
                )
            )
    else:
        # Las subsanaciones pueden mencionar los equipos dentro del cuerpo sin
        # repetir la seccion de lista usada en las primeras presentaciones.
        letter.equipment.extend(extract_typed_equipment(text))

    if not letter.equipment:
        raise ExtractionError(f"No se extrajo ningun equipo de {path.name}")
    return letter


def extract_typed_equipment(text: str) -> list[Equipment]:
    found: list[Equipment] = []
    seen_codes: set[str] = set()
    pattern = re.compile(
        rf"\b({EQUIPMENT_TYPE_RE})\s+({CODE_RE})\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        code = normalize_code(match.group(2))
        if code in seen_codes:
            continue
        seen_codes.add(code)
        found.append(
            Equipment(
                code=code,
                equipment_type=canonical_equipment_type(match.group(1)),
            )
        )
    return found


def canonical_equipment_type(value: str) -> str:
    key = normalized_for_matching(value)
    names = {
        "excavadora": "Excavadora",
        "retroexcavadora": "Retroexcavadora",
        "volquete": "Volquete",
        "camion volquete": "Camión Volquete",
        "cisterna de combustible": "Cisterna de Combustible",
        "cisterna de agua": "Cisterna de Agua",
    }
    return names.get(key, normalize_space(value))


def parse_response(text: str, path: Path, source_order: int) -> ParsedResponse:
    letter = parse_letter_identity(text, path, source_order)
    if letter.direction != "AAM_CPC":
        raise ExtractionError(f"{path.name} no es una respuesta AAM hacia CPC")

    reference = REFERENCE_RE.search(text)
    if not reference:
        raise ExtractionError(f"No se encontro la carta CPC referenciada en {path.name}")
    letter.referenced_cpc = reference.group(1).upper()

    if re.search(r"^\s*\d+\.\s+Equipos?:", text, re.MULTILINE | re.IGNORECASE):
        evaluations = parse_grouped_response(text)
    else:
        evaluations = parse_prose_response(text, letter.letter_date.year)
        if not evaluations:
            evaluations = parse_lifted_observations_response(text)

    if not evaluations:
        raise ExtractionError(f"No se extrajeron evaluaciones de {path.name}")
    return ParsedResponse(letter=letter, evaluations=evaluations)


def parse_grouped_response(text: str) -> dict[str, Evaluation]:
    starts = list(
        re.finditer(r"^\s*\d+\.\s+Equipos?:[^\n]*", text, re.MULTILINE | re.IGNORECASE)
    )
    evaluations: dict[str, Evaluation] = {}

    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        segment = text[start.start() : end]
        equipment = [
            Equipment(normalize_code(match.group(1)), normalize_space(match.group(2)))
            for match in re.finditer(
                rf"^\s*[•]\s*({CODE_RE}),\s*([^\n]+?)\s*$",
                segment,
                re.MULTILINE,
            )
        ]
        if not equipment:
            continue

        state_match = re.search(r"Estado:\s*([^\n]+)", segment, re.IGNORECASE)
        if not state_match:
            continue
        state = normalized_for_matching(state_match.group(1))
        observed = "no apt" in state
        result = "Observado-No conforme" if observed else "Aprobado"

        if not observed:
            for item in equipment:
                evaluations[item.code] = Evaluation(item.code, result, "Aprobado")
            continue

        observations = extract_observation_bullets(segment)
        for item in equipment:
            applicable = [
                observation
                for observation in observations
                if observation_applies(observation, item.equipment_type)
            ]
            detail = "\n- ".join(applicable)
            if detail:
                detail = "- " + detail
            else:
                detail = "No apto para ingreso al Lugar de las Obras."
            evaluations[item.code] = Evaluation(item.code, result, detail)

    return evaluations


def extract_observation_bullets(segment: str) -> list[str]:
    match = re.search(
        r"Observaciones?:\s*(.*?)^\s*o\s+Estado:",
        segment,
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    if not match:
        return []
    block = match.group(1)
    parts = re.split(r"\s*▪\s*", block)
    return [normalize_space(part) for part in parts if normalize_space(part)]


def observation_applies(observation: str, equipment_type: str) -> bool:
    observation_key = normalized_for_matching(observation)
    type_key = normalized_for_matching(equipment_type)
    if observation_key.startswith("cisternas no"):
        return "cisterna" in type_key
    if observation_key.startswith("volquetes y cisternas"):
        return "volquete" in type_key or "cisterna" in type_key
    if observation_key.startswith("volquetes"):
        return "volquete" in type_key
    return True


def parse_prose_response(text: str, year: int) -> dict[str, Evaluation]:
    section = re.search(
        r"a los equipos:\s*(.*?)\s*Se encuentran vencidas desde",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not section:
        return {}

    codes = [
        normalize_code(match.group(1))
        for match in re.finditer(rf"^\s*\d+\..*?({CODE_RE})[,;]?\s*$", section.group(1), re.MULTILINE)
    ]
    date_match = re.search(
        r"vencidas desde el\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)",
        text,
        re.IGNORECASE,
    )
    detail = "Las pólizas de seguros se encuentran vencidas."
    if date_match:
        month = MONTHS.get(normalized_for_matching(date_match.group(2)))
        if month:
            expired = date(year, month, int(date_match.group(1)))
            detail = f"Pólizas de seguros vencidas desde el {format_date(expired)}"

    return {
        code: Evaluation(code, "Observado-No conforme", detail) for code in codes
    }


def parse_lifted_observations_response(text: str) -> dict[str, Evaluation]:
    normalized = normalized_for_matching(text)
    approved = (
        "observaciones formuladas" in normalized
        and "quedan formalmente levantadas" in normalized
        and re.search(r"\baptos?\s+para\s+(?:su\s+)?ingreso", normalized)
    )
    if not approved:
        return {}
    return {
        item.code: Evaluation(item.code, "Aprobado", "Aprobado")
        for item in extract_typed_equipment(text)
    }


def ordinal_word(value: int) -> str:
    words = {
        1: "Primera",
        2: "Segunda",
        3: "Tercera",
        4: "Cuarta",
        5: "Quinta",
        6: "Sexta",
        7: "Séptima",
        8: "Octava",
        9: "Novena",
        10: "Décima",
    }
    return f"{words.get(value, str(value) + '.a')} presentación"


def build_rows(
    cpc_letters: Iterable[Letter], responses: Iterable[ParsedResponse]
) -> tuple[list[OutputRow], list[str]]:
    cpc_letters = list(cpc_letters)
    responses = list(responses)
    response_by_cpc = {item.letter.referenced_cpc: item for item in responses}
    response_by_number = {item.letter.full_number: item for item in responses}
    cpc_by_number = {item.full_number: item for item in cpc_letters}
    ordinal_cache: dict[tuple[str, str], int | None] = {}

    def presentation_ordinal(
        cpc: Letter, equipment_code: str, trail: frozenset[str] = frozenset()
    ) -> int | None:
        cache_key = (cpc.full_number, equipment_code)
        if cache_key in ordinal_cache:
            return ordinal_cache[cache_key]
        if cpc.full_number in trail:
            ordinal_cache[cache_key] = None
            return None
        if not cpc.referenced_aam:
            ordinal_cache[cache_key] = 1
            return 1

        previous_response = response_by_number.get(cpc.referenced_aam)
        if not previous_response or not previous_response.letter.referenced_cpc:
            ordinal_cache[cache_key] = None
            return None
        previous_cpc = cpc_by_number.get(previous_response.letter.referenced_cpc)
        if not previous_cpc:
            ordinal_cache[cache_key] = None
            return None

        previous_codes = {item.code for item in previous_cpc.equipment}
        if equipment_code not in previous_codes:
            ordinal_cache[cache_key] = 1
            return 1
        previous_ordinal = presentation_ordinal(
            previous_cpc, equipment_code, trail | {cpc.full_number}
        )
        ordinal_cache[cache_key] = (
            previous_ordinal + 1 if previous_ordinal is not None else None
        )
        return ordinal_cache[cache_key]

    rows: list[OutputRow] = []
    warnings: list[str] = []
    warning_keys: set[str] = set()

    def warn_once(key: str, message: str) -> None:
        if key not in warning_keys:
            warning_keys.add(key)
            warnings.append(message)

    for cpc in sorted(cpc_letters, key=lambda item: (item.letter_date, item.source_order)):
        response = response_by_cpc.get(cpc.full_number)
        cpc_codes = {item.code for item in cpc.equipment}
        if response:
            extra = sorted(set(response.evaluations) - cpc_codes)
            for code in extra:
                warn_once(
                    f"extra:{response.letter.full_number}:{code}",
                    f"{response.letter.full_number}: se omitio {code} porque no aparece "
                    f"en {cpc.full_number}.",
                )

        for item in cpc.equipment:
            order = presentation_ordinal(cpc, item.code)
            if order is None:
                warn_once(
                    f"ordinal:{cpc.full_number}",
                    f"{cpc.full_number}: no se pudo calcular el tipo de tramite porque "
                    f"no se proporciono la cadena documental iniciada por "
                    f"{cpc.referenced_aam}.",
                )
            evaluation = response.evaluations.get(item.code) if response else None
            if response and evaluation is None:
                warn_once(
                    f"missing:{response.letter.full_number}:{item.code}",
                    f"{response.letter.full_number}: no se encontro evaluacion para {item.code}.",
                )
            rows.append(
                OutputRow(
                    owner="CPC",
                    cpc_correlative=cpc.correlative,
                    cpc_date=cpc.letter_date,
                    reception_date="",
                    procedure_type=ordinal_word(order) if order is not None else "No calculado",
                    equipment_type=item.equipment_type,
                    equipment_code=item.code,
                    result=evaluation.result if evaluation else "",
                    detail=evaluation.detail if evaluation else "",
                    aam_correlative=response.letter.correlative if response else "",
                    aam_date=response.letter.letter_date if response else "",
                    additional_data="",
                )
            )
    return rows, warnings


def format_date(value: date | str) -> str:
    return value.strftime("%d/%m/%Y") if isinstance(value, date) else value


def markdown_table(rows: Iterable[OutputRow]) -> str:
    headers = [
        "Propietario",
        "Carta CPC",
        "Fecha CPC",
        "Recepcion",
        "Tramite",
        "Tipo de equipo",
        "Placa / Codigo",
        "Resultado SST",
        "Detalle",
        "Carta AAM",
        "Fecha AAM",
        "Dato adicional",
    ]
    body = []
    for row in rows:
        values = [
            row.owner,
            row.cpc_correlative,
            format_date(row.cpc_date),
            row.reception_date,
            row.procedure_type,
            row.equipment_type,
            row.equipment_code,
            row.result,
            row.detail.replace("\n", "<br>"),
            row.aam_correlative,
            format_date(row.aam_date),
            row.additional_data,
        ]
        body.append("| " + " | ".join(str(value).replace("|", "\\|") for value in values) + " |")
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    return "\n".join(["| " + " | ".join(headers) + " |", separator, *body])


def extract_documents(paths: list[Path]) -> tuple[list[OutputRow], list[str]]:
    cpc_letters: list[Letter] = []
    responses: list[ParsedResponse] = []
    seen_numbers: set[str] = set()

    for source_order, path in enumerate(paths):
        text = extract_pdf_text(path)
        identity = parse_letter_identity(text, path, source_order)
        if identity.full_number in seen_numbers:
            raise ExtractionError(f"Numero de carta duplicado: {identity.full_number}")
        seen_numbers.add(identity.full_number)
        if identity.direction == "CPC_AAM":
            cpc_letters.append(parse_cpc(text, path, source_order))
        else:
            responses.append(parse_response(text, path, source_order))

    known_cpc = {letter.full_number for letter in cpc_letters}
    for response in responses:
        if response.letter.referenced_cpc not in known_cpc:
            raise ExtractionError(
                f"{response.letter.full_number} referencia una carta CPC no proporcionada: "
                f"{response.letter.referenced_cpc}"
            )
    return build_rows(cpc_letters, responses)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extrae cartas CPC/AAM y muestra una tabla de evaluaciones."
    )
    parser.add_argument("pdf", nargs="+", type=Path, help="PDF de cartas CPC y AAM")
    args = parser.parse_args(argv)

    try:
        rows, warnings = extract_documents(args.pdf)
    except ExtractionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(markdown_table(rows))
    if warnings:
        print("\nAdvertencias:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

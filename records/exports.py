"""Transformacion de registros a formatos de exportacion."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Evaluation


EXPORT_HEADERS = [
    "Tipo de registro",
    "Propietario del Equipo",
    "N° Correlativo Carta de Entrada",
    "Fecha de carta CPC",
    "Fecha de recepción de carta",
    "Tipo de trámite",
    "Tipo de Equipo",
    "Placa / Código del Equipo",
    "Resultado de la Evaluación SST",
    "Detalle de la Observación o Conformidad",
    "N° Correlativo Carta Respuesta AAM",
    "Fecha de carta AAM",
    "Dato adicional",
    "Estado operativo",
    "Fecha de salida / retiro",
]


def presentation_values(presentation):
    """Convierte una presentacion en una fila neutral para CSV o Excel."""
    try:
        evaluation = presentation.evaluation
        result = evaluation.get_result_display()
        detail = evaluation.detail
    except Evaluation.DoesNotExist:
        result = detail = ""
    response = getattr(presentation.cpc_letter, "response_letter", None)
    return [
        "Presentación",
        presentation.owner,
        presentation.cpc_letter.correlative,
        presentation.cpc_letter.letter_date.strftime("%d/%m/%Y"),
        presentation.cpc_letter.reception_date.strftime("%d/%m/%Y")
        if presentation.cpc_letter.reception_date
        else "",
        presentation.procedure_type,
        presentation.equipment_type,
        presentation.equipment.code,
        result,
        detail,
        response.correlative if response else "",
        response.letter_date.strftime("%d/%m/%Y") if response else "",
        presentation.additional_data,
        presentation.equipment.get_operational_status_display(),
        presentation.equipment.retired_at.strftime("%d/%m/%Y")
        if presentation.equipment.retired_at
        else "",
    ]


def movement_values(movement):
    """Convierte una solicitud o retiro en la misma estructura exportable."""
    technical_detail = " · ".join(
        value
        for value in [
            movement.brand,
            movement.model,
            movement.serial,
            str(movement.year) if movement.year else "",
        ]
        if value
    )
    return [
        "Desmovilización",
        "CPC",
        movement.request_letter.correlative,
        movement.request_letter.letter_date.strftime("%d/%m/%Y"),
        movement.request_letter.reception_date.strftime("%d/%m/%Y")
        if movement.request_letter.reception_date
        else "",
        "Desmovilización",
        movement.equipment_type,
        movement.equipment.code,
        "",
        technical_detail,
        movement.response_letter.correlative if movement.response_letter else "",
        movement.response_letter.letter_date.strftime("%d/%m/%Y")
        if movement.response_letter
        else "",
        "",
        movement.get_status_display(),
        movement.movement_date.strftime("%d/%m/%Y"),
    ]


def record_values(record):
    if record["kind"] == "movement":
        return movement_values(record["source"])
    return presentation_values(record["source"])


def safe_spreadsheet_value(value):
    """Evita que hojas de cálculo interpreten datos externos como fórmulas."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def safe_record_values(record):
    return [safe_spreadsheet_value(value) for value in record_values(record)]


def workbook_bytes(records):
    """Genera el contenido binario de un libro Excel con los registros."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Registros"
    sheet.append(EXPORT_HEADERS)
    for record in records:
        sheet.append(safe_record_values(record))

    fill = PatternFill("solid", fgColor="163A5F")
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for index, header in enumerate(EXPORT_HEADERS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = min(
            max(len(header) + 2, 14), 42
        )
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()

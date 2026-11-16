from django import forms

import re

from django.core.exceptions import ValidationError

from .models import Evaluation, Letter, Presentation


LETTER_NUMBER_RE = re.compile(
    r"^PSR2-F2-(CPC-AAM|AAM-CPC)-GEN-GLB-CAR-(\d{4})$", re.IGNORECASE
)


def validate_letter_number(value, expected_direction):
    value = value.strip().upper()
    match = LETTER_NUMBER_RE.fullmatch(value)
    if not match:
        raise ValidationError("Usa el número completo de carta con el formato PSR2-F2-…-CAR-0000.")
    direction = match.group(1)
    if direction != expected_direction:
        raise ValidationError(f"Esta carta debe tener la dirección {expected_direction}.")
    return value


def validate_pdf_upload(upload):
    if not upload:
        return upload
    if upload.size > 10 * 1024 * 1024:
        raise ValidationError("El PDF supera el límite de 10 MB.")
    if upload.content_type not in {"application/pdf", "application/x-pdf"}:
        raise ValidationError("El respaldo debe ser un PDF.")
    position = upload.tell()
    try:
        upload.seek(0)
        if upload.read(5) != b"%PDF-":
            raise ValidationError("El archivo no contiene una cabecera PDF válida.")
    finally:
        upload.seek(position)
    return upload


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": ".pdf"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        clean_one = super().clean
        if not data:
            raise ValidationError("Selecciona al menos un archivo PDF.")
        if len(data) > 20:
            raise ValidationError("Puedes cargar hasta 20 archivos por lote.")
        return [validate_pdf_upload(clean_one(item, initial)) for item in data]


class UploadLettersForm(forms.Form):
    files = MultipleFileField(
        label="Cartas PDF",
        help_text="Selecciona una o varias cartas CPC y AAM relacionadas.",
    )


class PresentationEditForm(forms.Form):
    cpc_full_number = forms.CharField(label="Número completo de carta CPC", max_length=80)
    cpc_date = forms.DateField(
        label="Fecha de carta CPC", widget=forms.DateInput(attrs={"type": "date"})
    )
    reception_date = forms.DateField(
        label="Fecha de recepción", widget=forms.DateInput(attrs={"type": "date"})
    )
    equipment_type = forms.CharField(label="Tipo de equipo", max_length=100)
    equipment_code = forms.CharField(label="Placa / código", max_length=40)
    result = forms.ChoiceField(
        label="Resultado SST",
        choices=[("", "Pendiente"), *Evaluation.Result.choices],
        required=False,
    )
    detail = forms.CharField(
        label="Detalle", required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    aam_full_number = forms.CharField(
        label="Número completo de respuesta AAM", max_length=80, required=False
    )
    aam_date = forms.DateField(
        label="Fecha de carta AAM",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    additional_data = forms.CharField(
        label="Dato adicional", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    cpc_pdf = forms.FileField(
        label="Reemplazar / adjuntar PDF CPC",
        required=False,
        widget=forms.FileInput(attrs={"accept": ".pdf"}),
    )
    aam_pdf = forms.FileField(
        label="Reemplazar / adjuntar PDF AAM",
        required=False,
        widget=forms.FileInput(attrs={"accept": ".pdf"}),
    )

    def clean_cpc_pdf(self):
        return validate_pdf_upload(self.cleaned_data.get("cpc_pdf"))

    def clean_aam_pdf(self):
        return validate_pdf_upload(self.cleaned_data.get("aam_pdf"))

    def clean_cpc_full_number(self):
        return validate_letter_number(self.cleaned_data["cpc_full_number"], "CPC-AAM")

    def clean_aam_full_number(self):
        value = self.cleaned_data["aam_full_number"]
        return validate_letter_number(value, "AAM-CPC") if value else ""

    def clean(self):
        cleaned = super().clean()
        aam_number, aam_date = cleaned.get("aam_full_number"), cleaned.get("aam_date")
        if bool(aam_number) != bool(aam_date):
            self.add_error(
                "aam_full_number" if not aam_number else "aam_date",
                "Completa número y fecha AAM.",
            )
        if cleaned.get("result") and not aam_number:
            self.add_error("result", "Un resultado requiere una respuesta AAM.")
        if cleaned.get("result") == Evaluation.Result.OBSERVED and not cleaned.get("detail"):
            self.add_error("detail", "Describe la observación.")
        if cleaned.get("result") == Evaluation.Result.APPROVED and not cleaned.get("detail"):
            cleaned["detail"] = "Aprobado"
        return cleaned

    @classmethod
    def from_presentation(cls, presentation: Presentation, *args, **kwargs):
        try:
            evaluation = presentation.evaluation
        except Evaluation.DoesNotExist:
            evaluation = None
        response = getattr(presentation.cpc_letter, "response_letter", None)
        kwargs.setdefault(
            "initial",
            {
                "cpc_full_number": presentation.cpc_letter.full_number,
                "cpc_date": presentation.cpc_letter.letter_date,
                "reception_date": presentation.cpc_letter.reception_date,
                "equipment_type": presentation.equipment_type,
                "equipment_code": presentation.equipment.code,
                "result": evaluation.result if evaluation else "",
                "detail": evaluation.detail if evaluation else "",
                "aam_full_number": response.full_number if response else "",
                "aam_date": response.letter_date if response else None,
                "additional_data": presentation.additional_data,
            },
        )
        return cls(*args, **kwargs)


class ManualRecordForm(forms.Form):
    cpc_full_number = forms.CharField(label="Número completo de carta CPC", max_length=80)
    cpc_date = forms.DateField(
        label="Fecha de carta CPC", widget=forms.DateInput(attrs={"type": "date"})
    )
    reception_date = forms.DateField(
        label="Fecha de recepción", widget=forms.DateInput(attrs={"type": "date"})
    )
    predecessor_aam = forms.CharField(
        label="Respuesta AAM anterior (si es subsanación)", max_length=80, required=False
    )
    equipment_type = forms.CharField(label="Tipo de equipo", max_length=100)
    equipment_code = forms.CharField(label="Placa / código", max_length=40)
    result = forms.ChoiceField(
        label="Resultado SST",
        choices=[("", "Pendiente"), *Evaluation.Result.choices],
        required=False,
    )
    detail = forms.CharField(
        label="Detalle", required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    aam_full_number = forms.CharField(
        label="Número completo de respuesta AAM", max_length=80, required=False
    )
    aam_date = forms.DateField(
        label="Fecha de carta AAM",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    additional_data = forms.CharField(
        label="Dato adicional", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    cpc_pdf = forms.FileField(
        label="PDF CPC de respaldo", required=False, widget=forms.FileInput(attrs={"accept": ".pdf"})
    )
    aam_pdf = forms.FileField(
        label="PDF AAM de respaldo", required=False, widget=forms.FileInput(attrs={"accept": ".pdf"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        guidance = {
            "cpc_full_number": ("Ejemplo: PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001", "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001"),
            "predecessor_aam": ("Solo para subsanaciones: indica la respuesta AAM de la presentación anterior.", "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0001"),
            "equipment_type": ("Ejemplo: camioneta o camión volquete.", "Camioneta"),
            "equipment_code": ("Indica la placa o el código que identifica el equipo.", "BVL-812"),
            "result": ("Si hay resultado, completa el número y la fecha de la respuesta AAM.", None),
            "detail": ("Obligatorio si el resultado es observado; describe la observación.", None),
            "aam_full_number": ("Completa número y fecha cuando exista una respuesta AAM.", "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0001"),
            "aam_date": ("Necesaria cuando indicas el número de respuesta o un resultado SST.", None),
            "cpc_pdf": ("Opcional. PDF de hasta 10 MB.", None),
            "aam_pdf": ("Opcional. PDF de hasta 10 MB.", None),
        }
        for name, (help_text, placeholder) in guidance.items():
            self.fields[name].help_text = help_text
            if placeholder:
                self.fields[name].widget.attrs["placeholder"] = placeholder

    def clean_cpc_pdf(self):
        return validate_pdf_upload(self.cleaned_data.get("cpc_pdf"))

    def clean_aam_pdf(self):
        return validate_pdf_upload(self.cleaned_data.get("aam_pdf"))

    def clean_cpc_full_number(self):
        return validate_letter_number(self.cleaned_data["cpc_full_number"], "CPC-AAM")

    def clean_predecessor_aam(self):
        value = self.cleaned_data["predecessor_aam"]
        return validate_letter_number(value, "AAM-CPC") if value else ""

    def clean_aam_full_number(self):
        value = self.cleaned_data["aam_full_number"]
        return validate_letter_number(value, "AAM-CPC") if value else ""

    def clean(self):
        cleaned = super().clean()
        result = cleaned.get("result")
        aam_number = cleaned.get("aam_full_number")
        aam_date = cleaned.get("aam_date")
        if result and (not aam_number or not aam_date):
            self.add_error("aam_full_number", "El resultado requiere una carta AAM y su fecha.")
        if aam_number and not aam_date:
            self.add_error("aam_date", "Indica la fecha de la carta AAM.")
        if aam_date and not aam_number:
            self.add_error("aam_full_number", "Indica el número de la carta AAM.")
        if result == Evaluation.Result.APPROVED:
            cleaned["detail"] = cleaned.get("detail") or "Aprobado"
        elif result and not cleaned.get("detail"):
            self.add_error("detail", "Describe la observación.")
        for field in ("cpc_pdf", "aam_pdf"):
            upload = cleaned.get(field)
            if upload and (upload.content_type not in {"application/pdf", "application/x-pdf"}):
                self.add_error(field, "El respaldo debe ser un PDF.")
        return cleaned


class LetterEditForm(PresentationEditForm):
    """Datos compartidos de una carta y su respuesta."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ("equipment_type", "equipment_code", "result", "detail", "additional_data"):
            self.fields.pop(field, None)
        self.fields["reception_date"].required = False

    @classmethod
    def from_letter(cls, letter, *args, **kwargs):
        response = getattr(letter, "response_letter", None)
        kwargs.setdefault("initial", {
            "cpc_full_number": letter.full_number, "cpc_date": letter.letter_date,
            "reception_date": letter.reception_date,
            "aam_full_number": response.full_number if response else "",
            "aam_date": response.letter_date if response else None,
        })
        return cls(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        for field in ("cpc_pdf", "aam_pdf"):
            upload = cleaned.get(field)
            if upload and upload.content_type not in {"application/pdf", "application/x-pdf"}:
                self.add_error(field, "El respaldo debe ser un PDF.")
        return cleaned


class MovementEditForm(LetterEditForm):
    equipment_code = forms.CharField(label="Placa / código", max_length=40)
    equipment_type = forms.CharField(label="Tipo de equipo", max_length=100)
    movement_date = forms.DateField(label="Fecha de salida", widget=forms.DateInput(attrs={"type": "date"}))
    brand = forms.CharField(label="Marca", max_length=80, required=False)
    model = forms.CharField(label="Modelo", max_length=120, required=False)
    serial = forms.CharField(label="Serie", max_length=120, required=False)
    year = forms.IntegerField(label="Año", min_value=1, max_value=2147483647, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # LetterEditForm removes fields shared with presentation forms.
        self.fields["equipment_code"] = forms.CharField(label="Placa / código", max_length=40)
        self.fields["equipment_type"] = forms.CharField(label="Tipo de equipo", max_length=100)

    @classmethod
    def from_movement(cls, movement, *args, **kwargs):
        response = getattr(movement.request_letter, "response_letter", None)
        kwargs.setdefault("initial", {
            "cpc_full_number": movement.request_letter.full_number,
            "cpc_date": movement.request_letter.letter_date,
            "reception_date": movement.request_letter.reception_date,
            "aam_full_number": response.full_number if response else "",
            "aam_date": response.letter_date if response else None,
            "equipment_code": movement.equipment.code, "equipment_type": movement.equipment_type,
            "movement_date": movement.movement_date, "brand": movement.brand,
            "model": movement.model, "serial": movement.serial, "year": movement.year,
        })
        return cls(*args, **kwargs)

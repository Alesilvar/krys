from django import forms

import re

from django.core.exceptions import ValidationError

from .models import Evaluation, Letter, Presentation


LETTER_NUMBER_RE = re.compile(
    r"^PSR2-F2-(CPC-AAM|AAM-CPC)-GEN-GLB-CAR-(\d+)$", re.IGNORECASE
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


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": ".pdf"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        clean_one = super().clean
        return [clean_one(item, initial) for item in (data or [])]


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
        label="Resultado SST", choices=[("", "Pendiente"), *Evaluation.Result.choices]
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
                "aam_full_number": evaluation.response_letter.full_number if evaluation else "",
                "aam_date": evaluation.response_letter.letter_date if evaluation else None,
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
        label="Resultado SST", choices=[("", "Pendiente"), *Evaluation.Result.choices]
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

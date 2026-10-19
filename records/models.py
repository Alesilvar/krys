from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Letter(models.Model):
    class Direction(models.TextChoices):
        CPC_AAM = "CPC_AAM", "CPC hacia AAM"
        AAM_CPC = "AAM_CPC", "AAM hacia CPC"

    class Source(models.TextChoices):
        PDF = "PDF", "Extraída de PDF"
        MANUAL = "MANUAL", "Ingreso manual"

    full_number = models.CharField("número completo", max_length=80, unique=True)
    correlative = models.PositiveIntegerField("correlativo")
    direction = models.CharField("dirección", max_length=12, choices=Direction.choices)
    letter_date = models.DateField("fecha de carta")
    reception_date = models.DateField("fecha de recepción", null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.PDF)
    pdf = models.FileField(upload_to="letters/%Y/%m/", null=True, blank=True)
    response_to = models.OneToOneField(
        "self",
        verbose_name="carta CPC respondida",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="response_letter",
    )
    predecessor_response = models.ForeignKey(
        "self",
        verbose_name="respuesta AAM que origina la subsanación",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="followup_letters",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_letters",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["letter_date", "created_at"]

    def __str__(self):
        return self.full_number

    def clean(self):
        if self.direction == self.Direction.AAM_CPC and not self.response_to:
            raise ValidationError("Una carta AAM debe responder a una carta CPC.")


class Equipment(models.Model):
    code = models.CharField("placa o código", max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Presentation(models.Model):
    cpc_letter = models.ForeignKey(
        Letter,
        on_delete=models.CASCADE,
        related_name="presentations",
        limit_choices_to={"direction": Letter.Direction.CPC_AAM},
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="presentations"
    )
    owner = models.CharField(max_length=10, default="CPC")
    equipment_type = models.CharField("tipo de equipo", max_length=100)
    additional_data = models.TextField("dato adicional", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cpc_letter", "equipment"],
                name="unique_equipment_per_cpc_letter",
            )
        ]
        ordering = ["cpc_letter__letter_date", "created_at"]

    def __str__(self):
        return f"{self.equipment.code} - {self.cpc_letter.correlative}"

    def presentation_number(self, trail=None):
        trail = set(trail or [])
        if self.cpc_letter_id in trail:
            return None
        if not self.cpc_letter.predecessor_response_id:
            return 1
        previous_cpc = self.cpc_letter.predecessor_response.response_to
        if previous_cpc is None:
            return None
        previous = Presentation.objects.filter(
            cpc_letter=previous_cpc, equipment=self.equipment
        ).first()
        if previous is None:
            return 1
        previous_number = previous.presentation_number(trail | {self.cpc_letter_id})
        return previous_number + 1 if previous_number is not None else None

    @property
    def procedure_type(self):
        number = self.presentation_number()
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
        if number is None:
            return "No calculado"
        return f"{words.get(number, str(number) + '.ª')} presentación"


class Evaluation(models.Model):
    class Result(models.TextChoices):
        APPROVED = "APPROVED", "Aprobado"
        OBSERVED = "OBSERVED", "Observado-No conforme"

    presentation = models.OneToOneField(
        Presentation, on_delete=models.CASCADE, related_name="evaluation"
    )
    response_letter = models.ForeignKey(
        Letter,
        on_delete=models.CASCADE,
        related_name="evaluations",
        limit_choices_to={"direction": Letter.Direction.AAM_CPC},
    )
    result = models.CharField(max_length=20, choices=Result.choices)
    detail = models.TextField()
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)


class ProcessingWarning(models.Model):
    letter = models.ForeignKey(
        Letter, on_delete=models.CASCADE, related_name="processing_warnings"
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Creación"
        UPDATE = "UPDATE", "Edición"
        DELETE = "DELETE", "Eliminación"
        UPLOAD = "UPLOAD", "Carga"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=12, choices=Action.choices)
    object_type = models.CharField(max_length=50)
    object_id = models.CharField(max_length=80)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

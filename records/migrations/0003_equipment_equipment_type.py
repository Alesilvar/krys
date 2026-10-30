from django.db import migrations, models


ALIASES = {
    "Camión Volquete": "Volquete",
    "Camion Volquete": "Volquete",
}


def populate_equipment_types(apps, schema_editor):
    Equipment = apps.get_model("records", "Equipment")
    Presentation = apps.get_model("records", "Presentation")
    EquipmentMovement = apps.get_model("records", "EquipmentMovement")
    for presentation in Presentation.objects.all():
        canonical = ALIASES.get(presentation.equipment_type, presentation.equipment_type)
        if canonical != presentation.equipment_type:
            presentation.equipment_type = canonical
            presentation.save(update_fields=["equipment_type"])
    for movement in EquipmentMovement.objects.all():
        canonical = ALIASES.get(movement.equipment_type, movement.equipment_type)
        if canonical != movement.equipment_type:
            movement.equipment_type = canonical
            movement.save(update_fields=["equipment_type"])
    for equipment in Equipment.objects.all():
        presentation = (
            Presentation.objects.filter(equipment_id=equipment.pk)
            .order_by("created_at")
            .first()
        )
        movement = (
            EquipmentMovement.objects.filter(equipment_id=equipment.pk)
            .order_by("created_at")
            .first()
        )
        raw_type = (
            presentation.equipment_type
            if presentation
            else movement.equipment_type if movement else ""
        )
        equipment.equipment_type = ALIASES.get(raw_type, raw_type)
        equipment.save(update_fields=["equipment_type"])


class Migration(migrations.Migration):
    dependencies = [("records", "0002_equipment_operational_status_equipment_retired_at_and_more")]

    operations = [
        migrations.AddField(
            model_name="equipment",
            name="equipment_type",
            field=models.CharField(blank=True, max_length=100, verbose_name="tipo de equipo"),
        ),
        migrations.RunPython(populate_equipment_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="equipment",
            name="operational_status",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "Activo"),
                    ("REQUESTED", "Retiro solicitado"),
                    ("RETIRED", "Retirado"),
                ],
                default="ACTIVE",
                max_length=10,
                verbose_name="estado operativo",
            ),
        ),
    ]

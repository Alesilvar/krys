import os
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from extractor import ExtractionError

from .models import (
    AuditEvent,
    Equipment,
    EquipmentMovement,
    Evaluation,
    Letter,
    Presentation,
)
from .services import persist_preview, prepare_preview
from .equipment_rules import canonical_equipment_type, ensure_equipment_type, refresh_equipment_status
from .selectors import active_equipment_chart, current_inventory_by_type, filtered_records


SAMPLES = Path(os.environ.get("KRYS_TEST_SAMPLES_DIR", Path(__file__).resolve().parents[2]))


class TestRecordModels(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="safe-test-password")

    def test_active_chart_counts_only_active_equipment_and_groups_types(self):
        cpc = self.letter("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001", "CPC_AAM", 1)
        for code, kind, status in [
            ("AAA-111", "Volquete", Equipment.OperationalStatus.ACTIVE),
            ("BBB-222", "Camión volquete", Equipment.OperationalStatus.ACTIVE),
            ("CCC-333", "", Equipment.OperationalStatus.ACTIVE),
            ("DDD-444", "Volquete", Equipment.OperationalStatus.REQUESTED),
            ("EEE-555", "Volquete", Equipment.OperationalStatus.RETIRED),
            ("FFF-666", "Volquete", Equipment.OperationalStatus.REVIEW),
        ]:
            equipment = Equipment.objects.create(code=code, equipment_type=kind, operational_status=status)
            Presentation.objects.create(cpc_letter=cpc, equipment=equipment, equipment_type=kind, created_by=self.user)
        Equipment.objects.create(code="GGG-777", equipment_type="", operational_status=Equipment.OperationalStatus.ACTIVE)
        chart = active_equipment_chart()
        self.assertEqual(chart["total"], 3)
        self.assertEqual([(item["equipment_type"], item["total"]) for item in chart["items"]],
                         [("Camión volquete", 2), ("Sin tipo", 1)])
        self.assertEqual(chart["items"][0]["percentage"], 66.7)
        self.assertTrue(chart["gradient"])

    def test_active_chart_handles_empty_inventory(self):
        self.assertEqual(active_equipment_chart(), {"total": 0, "items": [], "gradient": ""})

    def test_equipment_type_aliases_and_ambiguous_values(self):
        for original, expected in [("VOLQUETE", "Camión volquete"),
                                   ("  Mini  cargador ", "Minicargador"),
                                   ("Grúa de celosía sobre orugas", "Grúa sobre orugas"),
                                   ("Cisterna de agua", "Cisterna de agua"),
                                   ("Grúa todoterreno", "Grúa todoterreno")]:
            with self.subTest(original=original):
                self.assertEqual(canonical_equipment_type(original), expected)

    def test_inventory_groups_existing_equivalent_types(self):
        cpc = self.letter("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001", "CPC_AAM", 1)
        aam = self.letter("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0002", "AAM_CPC", 2, response_to=cpc)
        for code, kind in [("AAA-111", "Volquete"), ("BBB-222", "Camión volquete")]:
            equipment = Equipment.objects.create(code=code, equipment_type=kind)
            presentation = Presentation.objects.create(cpc_letter=cpc, equipment=equipment, equipment_type=kind, created_by=self.user)
            Evaluation.objects.create(presentation=presentation, response_letter=aam, result=Evaluation.Result.APPROVED, detail="", updated_by=self.user)
        self.assertEqual(current_inventory_by_type(), [{"equipment_type": "Camión volquete", "total": 2}])

    def letter(self, number, direction, day, **kwargs):
        return Letter.objects.create(
            full_number=number,
            correlative=int(number.rsplit("-", 1)[-1]),
            direction=direction,
            letter_date=date(2026, 1, day),
            created_by=self.user,
            **kwargs,
        )

    def test_document_chain_calculates_second_presentation(self):
        cpc1 = self.letter("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001", "CPC_AAM", 1)
        aam1 = self.letter(
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0002", "AAM_CPC", 2, response_to=cpc1
        )
        cpc2 = self.letter(
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0003",
            "CPC_AAM",
            3,
            predecessor_response=aam1,
        )
        equipment = Equipment.objects.create(code="ABC-123")
        first = Presentation.objects.create(
            cpc_letter=cpc1,
            equipment=equipment,
            equipment_type="Excavadora",
            created_by=self.user,
        )
        second = Presentation.objects.create(
            cpc_letter=cpc2,
            equipment=equipment,
            equipment_type="Excavadora",
            created_by=self.user,
        )
        self.assertEqual(first.procedure_type, "Primera presentación")
        self.assertEqual(second.procedure_type, "Segunda presentación")

    def test_same_plate_cannot_have_two_equipment_types(self):
        equipment = Equipment.objects.create(
            code="ABC-123", equipment_type="Excavadora"
        )

        with self.assertRaisesRegex(
            ValidationError, "ya pertenece al tipo Excavadora"
        ):
            ensure_equipment_type(equipment, "Camioneta")

    def test_inventory_counts_each_approved_active_plate_once(self):
        equipment = Equipment.objects.create(
            code="ABC-123", equipment_type="Excavadora"
        )
        for index in (1, 3):
            cpc = self.letter(
                f"PSR2-F2-CPC-AAM-GEN-GLB-CAR-{index:04d}", "CPC_AAM", index
            )
            aam = self.letter(
                f"PSR2-F2-AAM-CPC-GEN-GLB-CAR-{index + 1:04d}",
                "AAM_CPC",
                index + 1,
                response_to=cpc,
            )
            presentation = Presentation.objects.create(
                cpc_letter=cpc,
                equipment=equipment,
                equipment_type="Excavadora",
                created_by=self.user,
            )
            Evaluation.objects.create(
                presentation=presentation,
                response_letter=aam,
                result=Evaluation.Result.APPROVED,
                detail="Aprobado",
                updated_by=self.user,
            )

        self.assertEqual(
            current_inventory_by_type(),
            [{"equipment_type": "Excavadora", "total": 1}],
        )

    def test_new_approval_after_retirement_reactivates_equipment(self):
        equipment = Equipment.objects.create(
            code="ABC-123", equipment_type="Excavadora"
        )
        request = self.letter(
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001", "CPC_AAM", 1,
            purpose=Letter.Purpose.DEMOBILIZATION,
        )
        response = self.letter(
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0002", "AAM_CPC", 2,
            response_to=request,
            purpose=Letter.Purpose.DEMOBILIZATION,
        )
        EquipmentMovement.objects.create(
            equipment=equipment,
            request_letter=request,
            response_letter=response,
            status=EquipmentMovement.Status.AUTHORIZED,
            movement_date=date(2026, 1, 2),
            equipment_type="Excavadora",
            created_by=self.user,
        )
        refresh_equipment_status(equipment)
        equipment.refresh_from_db()
        self.assertEqual(
            equipment.operational_status, Equipment.OperationalStatus.RETIRED
        )

        cpc = self.letter(
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0003", "CPC_AAM", 3
        )
        aam = self.letter(
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0004", "AAM_CPC", 4,
            response_to=cpc,
        )
        presentation = Presentation.objects.create(
            cpc_letter=cpc,
            equipment=equipment,
            equipment_type="Excavadora",
            created_by=self.user,
        )
        Evaluation.objects.create(
            presentation=presentation,
            response_letter=aam,
            result=Evaluation.Result.APPROVED,
            detail="Aprobado",
            updated_by=self.user,
        )
        refresh_equipment_status(equipment)
        equipment.refresh_from_db()

        self.assertEqual(
            equipment.operational_status, Equipment.OperationalStatus.ACTIVE
        )
        self.assertIsNone(equipment.retired_at)
        self.assertEqual(current_inventory_by_type()[0]["total"], 1)

    def test_presentations_and_retirements_share_one_record_list(self):
        equipment = Equipment.objects.create(
            code="ABC-123", equipment_type="Excavadora"
        )
        cpc = self.letter("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001", "CPC_AAM", 1)
        Presentation.objects.create(
            cpc_letter=cpc,
            equipment=equipment,
            equipment_type="Excavadora",
            created_by=self.user,
        )
        request = self.letter(
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0002", "CPC_AAM", 2,
            purpose=Letter.Purpose.DEMOBILIZATION,
        )
        EquipmentMovement.objects.create(
            equipment=equipment,
            request_letter=request,
            status=EquipmentMovement.Status.REQUESTED,
            movement_date=date(2026, 1, 2),
            equipment_type="Excavadora",
            created_by=self.user,
        )

        records, _, _, _ = filtered_records({})

        self.assertEqual(
            {record["kind"] for record in records},
            {"presentation", "movement"},
        )


class TestWebFlow(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("aleu", password="safe-test-password")
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_manual_entry_export_and_permanent_delete(self):
        response = self.client.post(
            reverse("manual_record"),
            {
                "cpc_full_number": "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0200",
                "cpc_date": "2026-05-01",
                "reception_date": "2026-05-02",
                "predecessor_aam": "",
                "equipment_type": "Excavadora",
                "equipment_code": "EXC-200",
                "result": "APPROVED",
                "detail": "Aprobado",
                "aam_full_number": "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0140",
                "aam_date": "2026-05-03",
                "additional_data": "Prueba manual",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        presentation = Presentation.objects.select_related("cpc_letter").get()
        self.assertEqual(presentation.procedure_type, "Primera presentación")
        self.assertEqual(presentation.evaluation.result, Evaluation.Result.APPROVED)
        self.assertEqual(AuditEvent.objects.get().user, self.user)

        body = self.client.get(reverse("export_csv")).content.decode("utf-8-sig")
        self.assertIn("EXC-200", body)
        self.assertIn("Primera presentación", body)

        self.client.post(reverse("delete_letter", args=[presentation.cpc_letter_id]))
        self.assertFalse(Letter.objects.exists())
        self.assertFalse(Presentation.objects.exists())

    def test_edit_can_attach_a_cpc_pdf(self):
        cpc = Letter.objects.create(
            full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0201",
            correlative=201,
            direction=Letter.Direction.CPC_AAM,
            letter_date=date(2026, 5, 4),
            reception_date=date(2026, 5, 5),
            source=Letter.Source.MANUAL,
            created_by=self.user,
        )
        equipment = Equipment.objects.create(code="EXC-201")
        presentation = Presentation.objects.create(
            cpc_letter=cpc,
            equipment=equipment,
            equipment_type="Excavadora",
            created_by=self.user,
        )

        with tempfile.TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=Path(media_root)
        ):
            response = self.client.post(
                reverse("edit_presentation", args=[presentation.pk]),
                {
                    "cpc_full_number": cpc.full_number,
                    "cpc_date": "2026-05-04",
                    "reception_date": "2026-05-05",
                    "equipment_type": "Excavadora",
                    "equipment_code": "EXC-201",
                    "result": "",
                    "detail": "",
                    "aam_full_number": "",
                    "aam_date": "",
                    "additional_data": "",
                    "cpc_pdf": SimpleUploadedFile(
                        "cpc-201.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf"
                    ),
                },
            )

            self.assertRedirects(response, reverse("dashboard"))
            cpc.refresh_from_db()
            self.assertTrue(cpc.pdf.name.endswith("cpc-201.pdf"))
            self.assertTrue(Path(cpc.pdf.path).is_file())

    def test_retirement_is_rendered_inside_the_main_records_table(self):
        request = Letter.objects.create(
            full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0202",
            correlative=202,
            direction=Letter.Direction.CPC_AAM,
            purpose=Letter.Purpose.DEMOBILIZATION,
            letter_date=date(2026, 5, 6),
            reception_date=date(2026, 5, 6),
            source=Letter.Source.MANUAL,
            created_by=self.user,
        )
        equipment = Equipment.objects.create(
            code="EXC-202",
            equipment_type="Excavadora",
            operational_status=Equipment.OperationalStatus.REQUESTED,
        )
        EquipmentMovement.objects.create(
            equipment=equipment,
            request_letter=request,
            status=EquipmentMovement.Status.REQUESTED,
            movement_date=date(2026, 5, 7),
            equipment_type="Excavadora",
            created_by=self.user,
        )

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "Desmovilización")
        self.assertContains(response, "Retiro solicitado")
        self.assertEqual(response.content.decode().count("<table"), 1)


class TestPdfImport(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pdf-user", password="safe-test-password")
        self.temp_media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=Path(self.temp_media.name))
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.temp_media.cleanup()

    def upload(self, name):
        path = SAMPLES / name
        return SimpleUploadedFile(name, path.read_bytes(), content_type="application/pdf")

    def upload_example(self, name):
        path = SAMPLES / "ejemplo-cuarta" / name
        return SimpleUploadedFile(name, path.read_bytes(), content_type="application/pdf")

    def test_failed_confirmation_can_be_retried(self):
        preview = prepare_preview([self.upload("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0150.pdf")])
        with self.assertRaises(ExtractionError):
            persist_preview(preview, {}, self.user)
        self.assertTrue(Path(preview["documents"][0]["path"]).exists())
        persist_preview(preview, {"reception_150": "2026-03-30"}, self.user)
        self.assertEqual(Letter.objects.count(), 1)

    def test_real_pdf_pair_previews_and_persists_two_rows(self):
        preview = prepare_preview(
            [
                self.upload("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0150.pdf"),
                self.upload("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0118.pdf"),
            ]
        )
        self.assertEqual(len(preview["rows"]), 2)
        self.assertEqual(
            {row["equipment_code"] for row in preview["rows"]},
            {"EXC35-14", "RE8100-23"},
        )
        persist_preview(preview, {"reception_150": "2026-03-30"}, self.user)
        self.assertEqual(Presentation.objects.count(), 2)
        self.assertEqual(Evaluation.objects.count(), 2)
        self.assertEqual(Letter.objects.count(), 2)

    def test_second_pair_uses_stored_chain(self):
        first = prepare_preview(
            [
                self.upload("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0150.pdf"),
                self.upload("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0118.pdf"),
            ]
        )
        persist_preview(first, {"reception_150": "2026-03-30"}, self.user)
        second = prepare_preview(
            [
                self.upload("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0190.pdf"),
                self.upload("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0136.pdf"),
            ]
        )
        self.assertEqual(
            {row["procedure_type"] for row in second["rows"]},
            {"Segunda presentación"},
        )
        persist_preview(second, {"reception_190": "2026-04-22"}, self.user)
        self.assertEqual(Presentation.objects.count(), 4)

    def test_flexible_document_chain_previews_and_persists(self):
        names = [
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0230.pdf",
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0171.pdf",
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0249.pdf",
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0191.pdf",
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0425.pdf",
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0585.pdf",
        ]
        preview = prepare_preview([self.upload_example(name) for name in names])

        self.assertEqual(len(preview["rows"]), 24)
        self.assertEqual(preview["warnings"], [])
        self.assertEqual(
            sum(row["result"] == "Observado-No conforme" for row in preview["rows"]),
            6,
        )

        persist_preview(
            preview,
            {
                "reception_230": "2026-05-13",
                "reception_249": "2026-05-19",
                "reception_425": "2026-07-30",
            },
            self.user,
        )
        self.assertEqual(Letter.objects.count(), 6)
        self.assertEqual(Presentation.objects.count(), 24)
        self.assertEqual(Evaluation.objects.count(), 24)

    def test_later_approval_reactivates_despite_import_order(self):
        presentation_names = [
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0230.pdf",
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0171.pdf",
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0249.pdf",
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0191.pdf",
            "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0425.pdf",
            "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0585.pdf",
        ]
        presentation_preview = prepare_preview(
            [self.upload_example(name) for name in presentation_names]
        )
        persist_preview(
            presentation_preview,
            {
                "reception_230": "2026-05-13",
                "reception_249": "2026-05-19",
                "reception_425": "2026-07-30",
            },
            self.user,
        )

        movement_preview = prepare_preview(
            [
                self.upload_example(
                    "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0516-desmovilización 16 volquetes.pdf"
                ),
                self.upload_example("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0505.pdf"),
            ]
        )
        self.assertEqual(movement_preview["rows"], [])
        self.assertEqual(len(movement_preview["movement_rows"]), 16)
        persist_preview(movement_preview, {"reception_516": "2026-09-02"}, self.user)

        # AAM 0585 is dated 26 September, after retirement response 0505 on 8 September.
        equipment = Equipment.objects.get(code="CET-756")
        approved = Presentation.objects.filter(
            equipment=equipment,
            evaluation__result=Evaluation.Result.APPROVED,
        ).exists()
        self.assertTrue(approved)
        self.assertEqual(
            equipment.operational_status, Equipment.OperationalStatus.ACTIVE
        )
        self.assertIsNone(equipment.retired_at)
        movement = EquipmentMovement.objects.get(equipment=equipment)
        self.assertEqual(movement.status, EquipmentMovement.Status.AUTHORIZED)
        self.assertEqual(movement.response_letter.correlative, 505)
        self.assertEqual(EquipmentMovement.objects.count(), 16)
        records, _, _, _ = filtered_records({})
        self.assertEqual(len(records), 40)
        self.assertEqual(
            sum(item["total"] for item in current_inventory_by_type()), 14
        )

    def test_demobilization_request_without_response_stays_requested(self):
        preview = prepare_preview(
            [
                self.upload_example(
                    "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0516-desmovilización 16 volquetes.pdf"
                )
            ]
        )

        self.assertEqual(preview["rows"], [])
        self.assertEqual(len(preview["movement_rows"]), 16)
        self.assertEqual(
            {row["status"] for row in preview["movement_rows"]},
            {"Retiro solicitado"},
        )

        persist_preview(preview, {"reception_516": "2026-09-02"}, self.user)

        self.assertEqual(EquipmentMovement.objects.count(), 16)
        self.assertFalse(
            EquipmentMovement.objects.exclude(
                status=EquipmentMovement.Status.REQUESTED,
                response_letter=None,
            ).exists()
        )
        self.assertFalse(
            Equipment.objects.exclude(
                operational_status=Equipment.OperationalStatus.REQUESTED,
                retired_at=None,
            ).exists()
        )

    def test_later_response_completes_requested_retirement(self):
        request_preview = prepare_preview(
            [
                self.upload_example(
                    "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0516-desmovilización 16 volquetes.pdf"
                )
            ]
        )
        persist_preview(
            request_preview, {"reception_516": "2026-09-02"}, self.user
        )

        response_preview = prepare_preview(
            [self.upload_example("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0505.pdf")]
        )
        self.assertEqual(len(response_preview["movement_rows"]), 16)
        self.assertEqual(
            {row["status"] for row in response_preview["movement_rows"]},
            {"Retirado"},
        )
        persist_preview(response_preview, {}, self.user)

        self.assertEqual(Letter.objects.count(), 2)
        self.assertEqual(EquipmentMovement.objects.count(), 16)
        self.assertFalse(
            EquipmentMovement.objects.exclude(
                status=EquipmentMovement.Status.AUTHORIZED,
                response_letter__correlative=505,
            ).exists()
        )
        self.assertFalse(
            Equipment.objects.exclude(
                operational_status=Equipment.OperationalStatus.RETIRED,
                retired_at=date(2026, 9, 2),
            ).exists()
        )

    def test_demobilization_response_before_request_is_rejected(self):
        with self.assertRaisesRegex(
            ExtractionError, "solicitud de desmovilizacion no proporcionada"
        ):
            prepare_preview(
                [self.upload_example("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0505.pdf")]
            )

    def test_pdf_with_existing_plate_under_another_type_is_rejected(self):
        Equipment.objects.create(code="CET-756", equipment_type="Camioneta")

        with self.assertRaisesRegex(
            ExtractionError,
            "La placa CET-756 ya pertenece al tipo Camioneta",
        ):
            prepare_preview(
                [
                    self.upload_example(
                        "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0516-desmovilización 16 volquetes.pdf"
                    )
                ]
            )


class TestLetterExpedients(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("expedientes", password="test")
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        self.cpc = Letter.objects.create(full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001", correlative=1, direction=Letter.Direction.CPC_AAM, letter_date=date(2026, 1, 1), created_by=self.user)
        self.response = Letter.objects.create(full_number="PSR2-F2-AAM-CPC-GEN-GLB-CAR-0002", correlative=2, direction=Letter.Direction.AAM_CPC, letter_date=date(2026, 1, 2), response_to=self.cpc, created_by=self.user)
        self.followup = Letter.objects.create(full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0003", correlative=3, direction=Letter.Direction.CPC_AAM, letter_date=date(2026, 1, 3), predecessor_response=self.response, created_by=self.user)

    def test_grouping_search_and_pending(self):
        equipment = Equipment.objects.create(code="ABC-1", equipment_type="Volquete")
        Presentation.objects.create(cpc_letter=self.followup, equipment=equipment, equipment_type="Volquete", created_by=self.user)
        result = self.client.get(reverse("letters"), {"q": "ABC-1", "status": "pending"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.context["expedients"]), 1)
        self.assertEqual([letter.pk for letter in result.context["expedients"][0]], [self.cpc.pk, self.followup.pk])
        self.assertContains(result, "Respuesta pendiente")
        self.assertContains(result, "PDF CPC no disponible")
        self.assertEqual(len(self.client.get(reverse("letters"), {"q": "sin coincidencia"}).context["expedients"]), 0)

    def test_movement_edit_updates_shared_response_and_equipment(self):
        self.followup.purpose = Letter.Purpose.DEMOBILIZATION
        self.followup.save()
        equipment = Equipment.objects.create(code="V-1", equipment_type="Volquete")
        movement = EquipmentMovement.objects.create(equipment=equipment, request_letter=self.followup, status=EquipmentMovement.Status.REQUESTED, movement_date=date(2026, 1, 4), equipment_type="Volquete", created_by=self.user)
        data = {"cpc_full_number": self.followup.full_number, "cpc_date": "2026-01-03", "reception_date": "", "aam_full_number": "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0004", "aam_date": "2026-01-05", "equipment_code": "V-2", "equipment_type": "Volquete", "movement_date": "2026-01-06", "brand": "Marca", "model": "Modelo", "serial": "123", "year": "2020"}
        result = self.client.post(reverse("edit_movement", args=[movement.pk]), data)
        self.assertRedirects(result, reverse("letters"))
        movement.refresh_from_db()
        self.assertEqual(movement.equipment.code, "V-2")
        self.assertEqual(movement.status, EquipmentMovement.Status.AUTHORIZED)
        self.assertEqual(movement.equipment.operational_status, Equipment.OperationalStatus.RETIRED)
        self.assertEqual(movement.response_letter.full_number, data["aam_full_number"])
        self.assertTrue(AuditEvent.objects.filter(action=AuditEvent.Action.UPDATE, object_type="Letter").exists())

    def test_delete_preserves_followup_and_login_required(self):
        self.client.post(reverse("delete_letter", args=[self.cpc.pk]))
        self.followup.refresh_from_db()
        self.assertIsNone(self.followup.predecessor_response_id)
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("letters")), f"{reverse('login')}?next={reverse('letters')}")

class SecurityRegressionTests(TestCase):
    def test_spreadsheet_values_are_literal(self):
        from .exports import safe_spreadsheet_value
        for value in ('=1+1', '  +1', '-1', '@SUM(A1)'):
            self.assertTrue(safe_spreadsheet_value(value).startswith("'"))
        self.assertEqual(safe_spreadsheet_value('normal'), 'normal')
        self.assertEqual(safe_spreadsheet_value(3), 3)

    def test_letter_pdf_requires_login(self):
        user = get_user_model().objects.create_user('pdf-user', password='secure-password')
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            letter = Letter.objects.create(full_number='PDF-1', correlative=1,
                direction=Letter.Direction.CPC_AAM, letter_date=date(2026, 1, 1),
                created_by=user, pdf=SimpleUploadedFile('test.pdf', b'%PDF-test'))
            url = reverse('letter_pdf', args=[letter.pk])
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'%PDF-test')
            response.close()
            self.assertEqual(self.client.get(letter.pdf.url).status_code, 404)

class RecordPermissionsTests(TestCase):
    def test_new_user_can_read_but_cannot_modify(self):
        user = get_user_model().objects.create_user('reader', password='secure-password')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('manual_record')).status_code, 403)
        self.assertEqual(self.client.post(reverse('confirm_upload')).status_code, 403)

    def test_editor_can_edit_but_not_delete(self):
        from django.contrib.auth.models import Group
        user = get_user_model().objects.create_user('editor', password='secure-password')
        user.groups.add(Group.objects.get(name='Edición'))
        letter = Letter.objects.create(full_number='TEST-1', correlative=1,
            direction=Letter.Direction.CPC_AAM, letter_date=date(2026, 1, 1), created_by=user)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('manual_record')).status_code, 200)
        self.assertEqual(self.client.post(reverse('delete_letter', args=[letter.pk])).status_code, 403)
        self.assertTrue(Letter.objects.filter(pk=letter.pk).exists())

class UploadValidationTests(TestCase):
    def test_empty_batch_and_fake_pdf_are_rejected(self):
        from .forms import UploadLettersForm, validate_pdf_upload
        self.assertFalse(UploadLettersForm({}, {}).is_valid())
        fake = SimpleUploadedFile('fake.pdf', b'not a pdf', content_type='application/pdf')
        with self.assertRaises(ValidationError):
            validate_pdf_upload(fake)

class PendingEvaluationResponseTests(TestCase):
    def test_response_is_available_without_evaluation(self):
        from .exports import presentation_values
        user = get_user_model().objects.create_user('reader-response', password='secure-password')
        cpc = Letter.objects.create(full_number='CPC-response-test', correlative=12,
            direction=Letter.Direction.CPC_AAM, letter_date=date(2026, 1, 1), created_by=user)
        response = Letter.objects.create(full_number='AAM-response-test', correlative=34,
            direction=Letter.Direction.AAM_CPC, letter_date=date(2026, 1, 2), response_to=cpc, created_by=user)
        equipment = Equipment.objects.create(code='PENDING-1')
        presentation = Presentation.objects.create(cpc_letter=cpc, equipment=equipment,
            equipment_type='Volquete', created_by=user)
        rows, *_ = filtered_records({})
        self.assertEqual(rows[0]['response_letter'], response)
        self.assertIsNone(rows[0]['evaluation'])
        self.assertEqual(presentation_values(presentation)[10:12], [34, '02/01/2026'])
        self.client.force_login(user)
        api_row = self.client.get(reverse('dashboard_data')).json()['records'][0]
        self.assertEqual(api_row['response'], 34)
        self.assertEqual(api_row['resultLabel'], 'Pendiente')

class LetterNumberValidationTests(TestCase):
    def test_exactly_four_digit_correlative(self):
        from .forms import validate_letter_number
        for value in ('PSR2-F2-CPC-AAM-GEN-GLB-CAR-123', 'PSR2-F2-CPC-AAM-GEN-GLB-CAR-12345'):
            with self.assertRaises(ValidationError):
                validate_letter_number(value, 'CPC-AAM')
        self.assertEqual(validate_letter_number('PSR2-F2-CPC-AAM-GEN-GLB-CAR-0123', 'CPC-AAM'), 'PSR2-F2-CPC-AAM-GEN-GLB-CAR-0123')

    def test_direction_correlative_is_unique(self):
        from django.db import IntegrityError, transaction
        user = get_user_model().objects.create_user('numbers')
        Letter.objects.create(full_number='CPC-unique', correlative=123, direction='CPC_AAM', letter_date=date(2026,1,1), created_by=user)
        Letter.objects.create(full_number='AAM-unique', correlative=123, direction='AAM_CPC', letter_date=date(2026,1,1), created_by=user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Letter.objects.create(full_number='CPC-duplicate', correlative=123, direction='CPC_AAM', letter_date=date(2026,1,1), created_by=user)

    def test_movement_year_has_database_safe_limit(self):
        from .forms import MovementEditForm
        field = MovementEditForm().fields['year']
        self.assertEqual(field.clean('2147483647'), 2147483647)
        for value in ('0', '-1', '2147483648'):
            with self.assertRaises(ValidationError):
                field.clean(value)

class EvaluationImportConflictTests(TestCase):
    def setUp(self):
        from .services import evaluation_snapshot
        self.user = get_user_model().objects.create_user('import-conflict')
        self.cpc = Letter.objects.create(full_number='CPC-conflict', correlative=991, direction='CPC_AAM', letter_date=date(2026,1,1), created_by=self.user)
        self.aam = Letter.objects.create(full_number='AAM-conflict', correlative=991, direction='AAM_CPC', letter_date=date(2026,1,2), response_to=self.cpc, created_by=self.user)
        self.equipment = Equipment.objects.create(code='CONFLICT', equipment_type='Volquete')
        self.presentation = Presentation.objects.create(cpc_letter=self.cpc, equipment=self.equipment, equipment_type='Volquete', created_by=self.user)
        self.evaluation = Evaluation.objects.create(presentation=self.presentation, response_letter=self.aam, result='OBSERVED', detail='Manual', updated_by=self.user)
        self.preview = {'batch_id': 'unused-test', 'documents': [], 'warnings': [], 'movement_rows': [], 'rows': [{
            'cpc_full_number': self.cpc.full_number, 'equipment_code': 'CONFLICT', 'equipment_type': 'Volquete',
            'row_index': 1, 'aam_full_number': self.aam.full_number, 'result': 'Aprobado', 'detail': 'PDF',
            'evaluation_snapshot': evaluation_snapshot(self.cpc.full_number, 'CONFLICT'), 'evaluation_conflict': True}]}
        self.media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=Path(self.media.name))
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.media.cleanup()

    def test_existing_value_is_preserved_by_default(self):
        persist_preview(self.preview, {}, self.user)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.detail, 'Manual')

    def test_explicit_replacement_is_audited(self):
        persist_preview(self.preview, {'replace_evaluation_1': '1'}, self.user)
        self.evaluation.refresh_from_db()
        self.assertEqual((self.evaluation.result, self.evaluation.detail), ('APPROVED', 'PDF'))
        event = AuditEvent.objects.get(object_type='Evaluation')
        self.assertEqual(event.details['before']['detail'], 'Manual')
        self.assertEqual(event.details['after']['detail'], 'PDF')

    def test_changed_evaluation_rejects_stale_preview(self):
        self.evaluation.detail = 'Cambio posterior'
        self.evaluation.save()
        with self.assertRaises(ExtractionError):
            persist_preview(self.preview, {'replace_evaluation_1': '1'}, self.user)
        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.detail, 'Cambio posterior')

class DocumentaryStatusTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('status-admin', password='secure-password')
        self.equipment = Equipment.objects.create(code='STATUS-1', equipment_type='Volquete')
        self.cpc = Letter.objects.create(full_number='CPC-status', correlative=901, direction='CPC_AAM', letter_date=date(2026,1,1), created_by=self.user)
        self.response = Letter.objects.create(full_number='AAM-status', correlative=901, direction='AAM_CPC', letter_date=date(2026,1,2), response_to=self.cpc, created_by=self.user)
        self.presentation = Presentation.objects.create(cpc_letter=self.cpc, equipment=self.equipment, equipment_type='Volquete', created_by=self.user)
        self.evaluation = Evaluation.objects.create(presentation=self.presentation, response_letter=self.response, result='APPROVED', detail='OK', updated_by=self.user)
        self.request = Letter.objects.create(full_number='CPC-retire', correlative=902, direction='CPC_AAM', letter_date=date(2026,1,3), created_by=self.user, purpose='DEMOBILIZATION')
        self.retirement = Letter.objects.create(full_number='AAM-retire', correlative=902, direction='AAM_CPC', letter_date=date(2026,1,4), response_to=self.request, created_by=self.user, purpose='DEMOBILIZATION')
        self.movement = EquipmentMovement.objects.create(equipment=self.equipment, request_letter=self.request, response_letter=self.retirement, status='AUTHORIZED', movement_date=date(2026,1,5), equipment_type='Volquete', created_by=self.user)

    def test_editing_old_approval_does_not_reactivate(self):
        refresh_equipment_status(self.equipment)
        self.evaluation.detail = 'Updated detail'
        self.evaluation.save()
        refresh_equipment_status(self.equipment)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.operational_status, 'RETIRED')

    def test_later_approval_reactivates_even_if_loaded_first(self):
        self.response.letter_date = date(2026,1,6)
        self.response.save()
        refresh_equipment_status(self.equipment)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.operational_status, 'ACTIVE')

    def test_tie_resolution_is_audited_and_invalidated_by_date_change(self):
        from .equipment_rules import analyze_equipment_status
        self.response.letter_date = self.retirement.letter_date
        self.response.save()
        refresh_equipment_status(self.equipment)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.operational_status, 'REVIEW')
        self.assertEqual(current_inventory_by_type(), [])
        state = analyze_equipment_status(self.equipment)
        self.client.force_login(self.user)
        response = self.client.post(reverse('resolve_equipment_status', args=[self.equipment.pk]), {'fingerprint': state['fingerprint'], 'selected': f'approval:{self.evaluation.pk}'})
        self.assertEqual(response.status_code, 302)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.operational_status, 'ACTIVE')
        self.assertTrue(AuditEvent.objects.filter(object_type='EquipmentStatusResolution', user=self.user).exists())
        self.movement.movement_date = date(2026,1,7)
        self.movement.save()
        refresh_equipment_status(self.equipment)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.operational_status, 'REVIEW')

    def test_request_date_and_stale_resolution(self):
        from .equipment_rules import analyze_equipment_status
        self.movement.status = EquipmentMovement.Status.REQUESTED
        self.movement.response_letter = None
        self.movement.save()
        refresh_equipment_status(self.equipment)
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.operational_status, 'REQUESTED')
        self.response.letter_date = self.request.letter_date
        self.response.save()
        refresh_equipment_status(self.equipment)
        self.equipment.refresh_from_db()
        state = analyze_equipment_status(self.equipment)
        self.assertEqual(state['status'], 'REVIEW')
        self.request.letter_date = date(2026,1,8)
        self.request.save()
        self.client.force_login(self.user)
        self.client.post(reverse('resolve_equipment_status', args=[self.equipment.pk]), {'fingerprint': state['fingerprint'], 'selected': f'approval:{self.evaluation.pk}'})
        self.equipment.refresh_from_db()
        self.assertEqual(self.equipment.status_resolution, {})
        self.assertFalse(AuditEvent.objects.filter(object_type='EquipmentStatusResolution').exists())

    def test_reader_cannot_resolve_tie(self):
        reader = get_user_model().objects.create_user('read-only')
        self.client.force_login(reader)
        self.assertEqual(self.client.post(reverse('resolve_equipment_status', args=[self.equipment.pk])).status_code, 403)

class RoleAccessRegressionTests(TestCase):
    def test_reader_can_export_and_record_admin_can_delete(self):
        from django.contrib.auth.models import Group
        reader = get_user_model().objects.create_user('reader-role')
        admin = get_user_model().objects.create_user('records-admin')
        admin.groups.add(Group.objects.get(name='Administración de registros'))
        letter = Letter.objects.create(full_number='CPC-role', correlative=880,
            direction=Letter.Direction.CPC_AAM, letter_date=date(2026,1,1), created_by=admin)
        self.client.force_login(reader)
        self.assertEqual(self.client.get(reverse('export_csv')).status_code, 200)
        self.assertEqual(self.client.get(reverse('export_xlsx')).status_code, 200)
        self.assertEqual(self.client.post(reverse('delete_letter', args=[letter.pk])).status_code, 403)
        self.client.force_login(admin)
        self.assertEqual(self.client.post(reverse('delete_letter', args=[letter.pk])).status_code, 302)
        self.assertFalse(Letter.objects.filter(pk=letter.pk).exists())

import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AuditEvent, Equipment, Evaluation, Letter, Presentation
from .services import persist_preview, prepare_preview


SAMPLES = Path("/home/aleu/Documentos/proyecto-krys")


class TestRecordModels(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="safe-test-password")

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


class TestWebFlow(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("aleu", password="safe-test-password")
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

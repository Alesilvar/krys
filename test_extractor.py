import unittest
from datetime import date
from pathlib import Path

from extractor import (
    Equipment,
    Evaluation,
    Letter,
    ParsedResponse,
    build_rows,
    extract_documents,
)


ROOT = Path("/home/aleu/Documentos/proyecto-krys")
DOWNLOADS = Path("/home/aleu/Descargas")


def sample(name):
    """Use the project copy when samples have been collected into the workspace."""
    project_copy = ROOT / name
    return project_copy if project_copy.is_file() else DOWNLOADS / name
SAMPLE_PDFS = [
    ROOT / "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0150.pdf",
    ROOT / "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0118.pdf",
    sample("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0178.pdf"),
    sample("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0127.pdf"),
]
SUBSANATION_PDFS = [
    ROOT / "PSR2-F2-CPC-AAM-GEN-GLB-CAR-0150.pdf",
    ROOT / "PSR2-F2-AAM-CPC-GEN-GLB-CAR-0118.pdf",
    sample("PSR2-F2-CPC-AAM-GEN-GLB-CAR-0190.pdf"),
    sample("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0136.pdf"),
]


class RealDocumentExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [str(path) for path in SAMPLE_PDFS if not path.is_file()]
        if missing:
            raise unittest.SkipTest("Faltan PDF de ejemplo: " + ", ".join(missing))
        cls.rows, cls.warnings = extract_documents(SAMPLE_PDFS)
        cls.by_code = {row.equipment_code: row for row in cls.rows}

    def test_extracts_all_equipment(self):
        self.assertEqual(len(self.rows), 16)
        self.assertEqual(len(self.by_code), 16)

    def test_pairs_both_responses(self):
        self.assertEqual(self.by_code["EXC35-14"].aam_correlative, 118)
        self.assertEqual(self.by_code["BMU-764"].aam_correlative, 127)

    def test_approved_group(self):
        for code in ("BMU-764", "BMV-721", "BMV-779", "BTF-842", "CJK-850", "BVF-722"):
            with self.subTest(code=code):
                self.assertEqual(self.by_code[code].result, "Aprobado")
                self.assertEqual(self.by_code[code].detail, "Aprobado")

    def test_observed_volquetes_receive_age_observation(self):
        for code in ("F7L-750", "AAT-805", "ADF-818", "AFR-881", "AFR-880"):
            with self.subTest(code=code):
                row = self.by_code[code]
                self.assertEqual(row.result, "Observado-No conforme")
                self.assertIn("4 años", row.detail)
                self.assertNotIn("seguros y polizas", row.detail.lower())

    def test_water_tankers_receive_all_applicable_observations(self):
        for code in ("C4N-794", "BLO-739", "A7E-930"):
            with self.subTest(code=code):
                detail = self.by_code[code].detail.lower()
                self.assertIn("seguros y pólizas", detail)
                self.assertIn("mantenimiento preventivo", detail)
                self.assertIn("4 años", detail)

    def test_expired_policy_response(self):
        for code in ("EXC35-14", "RE8100-23"):
            with self.subTest(code=code):
                row = self.by_code[code]
                self.assertEqual(row.result, "Observado-No conforme")
                self.assertIn("02/04/2026", row.detail)

    def test_manual_fields_remain_empty(self):
        for row in self.rows:
            self.assertEqual(row.reception_date, "")
            self.assertEqual(row.additional_data, "")

    def test_all_are_first_presentations_in_this_sample(self):
        for row in self.rows:
            self.assertEqual(row.procedure_type, "Primera presentación")

    def test_no_warnings_for_valid_samples(self):
        self.assertEqual(self.warnings, [])


class MatchingRulesTests(unittest.TestCase):
    def test_response_only_equipment_is_omitted_and_reported(self):
        cpc = Letter(
            full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001",
            correlative=1,
            letter_date=date(2026, 1, 1),
            direction="CPC_AAM",
            source_path=Path("cpc.pdf"),
            source_order=0,
            equipment=[Equipment("AAA-111", "Volquete")],
        )
        aam_letter = Letter(
            full_number="PSR2-F2-AAM-CPC-GEN-GLB-CAR-0002",
            correlative=2,
            letter_date=date(2026, 1, 2),
            direction="AAM_CPC",
            source_path=Path("aam.pdf"),
            source_order=1,
            referenced_cpc=cpc.full_number,
        )
        response = ParsedResponse(
            letter=aam_letter,
            evaluations={
                "AAA-111": Evaluation("AAA-111", "Aprobado", "Aprobado"),
                "ZZZ-999": Evaluation("ZZZ-999", "Aprobado", "Aprobado"),
            },
        )

        rows, warnings = build_rows([cpc], [response])

        self.assertEqual([row.equipment_code for row in rows], ["AAA-111"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("ZZZ-999", warnings[0])

    def test_repeated_equipment_in_unrelated_new_cpc_is_first_presentation(self):
        first = Letter(
            full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0001",
            correlative=1,
            letter_date=date(2026, 1, 1),
            direction="CPC_AAM",
            source_path=Path("first.pdf"),
            source_order=0,
            equipment=[Equipment("AAA-111", "Volquete")],
        )
        unrelated = Letter(
            full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0002",
            correlative=2,
            letter_date=date(2026, 2, 1),
            direction="CPC_AAM",
            source_path=Path("unrelated.pdf"),
            source_order=1,
            equipment=[Equipment("AAA-111", "Volquete")],
        )

        rows, warnings = build_rows([first, unrelated], [])

        self.assertEqual([row.procedure_type for row in rows], [
            "Primera presentación",
            "Primera presentación",
        ])
        self.assertEqual(warnings, [])

    def test_missing_referenced_aam_makes_ordinal_unresolved(self):
        cpc = Letter(
            full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0003",
            correlative=3,
            letter_date=date(2026, 3, 1),
            direction="CPC_AAM",
            source_path=Path("followup.pdf"),
            source_order=0,
            equipment=[Equipment("AAA-111", "Volquete")],
            referenced_aam="PSR2-F2-AAM-CPC-GEN-GLB-CAR-0099",
        )

        rows, warnings = build_rows([cpc], [])

        self.assertEqual(rows[0].procedure_type, "No calculado")
        self.assertEqual(len(warnings), 1)
        self.assertIn("PSR2-F2-AAM-CPC-GEN-GLB-CAR-0099", warnings[0])


class SubsanationDocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [str(path) for path in SUBSANATION_PDFS if not path.is_file()]
        if missing:
            raise unittest.SkipTest("Faltan PDF de subsanacion: " + ", ".join(missing))
        cls.rows, cls.warnings = extract_documents(SUBSANATION_PDFS)
        cls.by_key = {
            (row.cpc_correlative, row.equipment_code): row for row in cls.rows
        }

    def test_second_presentation_is_detected(self):
        for code in ("EXC35-14", "RE8100-23"):
            with self.subTest(code=code):
                row = self.by_key[(190, code)]
                self.assertEqual(row.procedure_type, "Segunda presentación")

    def test_lifted_observations_are_approved(self):
        for code in ("EXC35-14", "RE8100-23"):
            with self.subTest(code=code):
                row = self.by_key[(190, code)]
                self.assertEqual(row.result, "Aprobado")
                self.assertEqual(row.detail, "Aprobado")
                self.assertEqual(row.aam_correlative, 136)

    def test_subsanation_metadata(self):
        row = self.by_key[(190, "EXC35-14")]
        self.assertEqual(row.cpc_date, date(2026, 4, 22))
        self.assertEqual(row.aam_date, date(2026, 4, 24))
        self.assertEqual(row.reception_date, "")

    def test_subsanation_has_no_warnings(self):
        self.assertEqual(self.warnings, [])

    def test_new_equipment_in_followup_starts_at_first_presentation(self):
        prior_cpc = Letter(
            full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0100",
            correlative=100,
            letter_date=date(2026, 1, 1),
            direction="CPC_AAM",
            source_path=Path("prior-cpc.pdf"),
            source_order=0,
            equipment=[Equipment("OLD-100", "Excavadora")],
        )
        prior_aam_letter = Letter(
            full_number="PSR2-F2-AAM-CPC-GEN-GLB-CAR-0101",
            correlative=101,
            letter_date=date(2026, 1, 2),
            direction="AAM_CPC",
            source_path=Path("prior-aam.pdf"),
            source_order=1,
            referenced_cpc=prior_cpc.full_number,
        )
        prior_aam = ParsedResponse(
            letter=prior_aam_letter,
            evaluations={
                "OLD-100": Evaluation(
                    "OLD-100", "Observado-No conforme", "Observado"
                )
            },
        )
        followup = Letter(
            full_number="PSR2-F2-CPC-AAM-GEN-GLB-CAR-0102",
            correlative=102,
            letter_date=date(2026, 1, 3),
            direction="CPC_AAM",
            source_path=Path("followup.pdf"),
            source_order=2,
            equipment=[
                Equipment("OLD-100", "Excavadora"),
                Equipment("NEW-200", "Volquete"),
            ],
            referenced_aam=prior_aam_letter.full_number,
        )

        rows, warnings = build_rows([prior_cpc, followup], [prior_aam])
        by_code = {
            (row.cpc_correlative, row.equipment_code): row for row in rows
        }

        self.assertEqual(
            by_code[(102, "OLD-100")].procedure_type, "Segunda presentación"
        )
        self.assertEqual(
            by_code[(102, "NEW-200")].procedure_type, "Primera presentación"
        )
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()

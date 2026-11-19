import os
import unittest
from datetime import date
from pathlib import Path

from extractor import (
    Equipment,
    Evaluation,
    ExtractionError,
    Letter,
    ParsedDemobilizationResponse,
    ParsedResponse,
    build_rows,
    extract_documents,
    extract_pdf_text,
    parse_response,
    parse_cpc,
    parse_demobilization_request,
    parse_demobilization_response,
    validate_demobilization_pair,
)


ROOT = Path(os.environ.get("KRYS_TEST_SAMPLES_DIR", Path(__file__).resolve().parent.parent))


def sample(name):
    """Use the project copy when samples have been collected into the workspace."""
    project_copy = ROOT / name
    return project_copy
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
FLEXIBLE_FORMAT_PDFS = [
    ROOT / "ejemplo-cuarta/PSR2-F2-CPC-AAM-GEN-GLB-CAR-0230.pdf",
    ROOT / "ejemplo-cuarta/PSR2-F2-AAM-CPC-GEN-GLB-CAR-0171.pdf",
    ROOT / "ejemplo-cuarta/PSR2-F2-CPC-AAM-GEN-GLB-CAR-0249.pdf",
    ROOT / "ejemplo-cuarta/PSR2-F2-AAM-CPC-GEN-GLB-CAR-0191.pdf",
    ROOT / "ejemplo-cuarta/PSR2-F2-CPC-AAM-GEN-GLB-CAR-0425.pdf",
    ROOT / "ejemplo-cuarta/PSR2-F2-AAM-CPC-GEN-GLB-CAR-0585.pdf",
]
DEMOBILIZATION_REQUEST = (
    ROOT
    / "ejemplo-cuarta/PSR2-F2-CPC-AAM-GEN-GLB-CAR-0516-desmovilización 16 volquetes.pdf"
)
DEMOBILIZATION_RESPONSE = (
    ROOT / "ejemplo-cuarta/PSR2-F2-AAM-CPC-GEN-GLB-CAR-0505.pdf"
)


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


class NumberedVehicleListTests(unittest.TestCase):
    def test_extracts_plates_and_numeric_serial_from_682(self):
        path = ROOT / "PDF-PSR2/PSR2-F2-CPC-AAM-GEN-GLB-CAR-0682 XXXVII envío.pdf"
        if not path.is_file():
            self.skipTest("Falta la carta 682 de ejemplo")
        letter = parse_cpc(extract_pdf_text(path), path, 0)
        self.assertEqual([(item.code, item.equipment_type) for item in letter.equipment], [
            ("BDG-925", "Camión grúa"), ("BEC-729", "Camión grúa"),
            ("CMO-442", "Camioneta SUV"), ("BCT-894", "Cisterna de combustible"),
            ("2146365", "Plataforma de elevación tipo tijera"),
        ])

    def test_rejects_unrecognized_item_instead_of_returning_partial_list(self):
        text = """Lima, 2 de noviembre de 2026
CARTA No. PSR2-F2-CPC-AAM-GEN-GLB-CAR-0682
los siguientes equipos y vehículos:
1. Camión grúa, placa BDG-925.
2. Equipo sin identificador.
"""
        with self.assertRaises(ExtractionError):
            parse_cpc(text, Path("682.pdf"), 0)


class ListedApprovalTests(unittest.TestCase):
    def test_724_approves_only_five_listed_items_from_682(self):
        cpc = ROOT / "PDF-PSR2/PSR2-F2-CPC-AAM-GEN-GLB-CAR-0682 XXXVII envío.pdf"
        aam = ROOT / "PDF-PSR2/PSR2-F2-AAM-CPC-GEN-GLB-CAR-0724.pdf"
        if not cpc.is_file() or not aam.is_file():
            self.skipTest("Faltan las cartas 682 y 724 de ejemplo")
        response = parse_response(extract_pdf_text(aam), aam, 1)
        self.assertEqual(set(response.evaluations), {"BDG-925", "BEC-729", "CMO-442", "BCT-894", "2146365"})
        self.assertEqual(response.default_result, "")
        rows, warnings = extract_documents([cpc, aam])
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row.result == "Aprobado" and row.aam_correlative == 724 for row in rows))
        self.assertEqual(warnings, [])

    def test_does_not_approve_list_with_unrecognized_item(self):
        text = """Lima, 3 de noviembre de 2026
CARTA No. PSR2-F2-AAM-CPC-GEN-GLB-CAR-0724
Referencia: Carta No. PSR2-F2-CPC-AAM-GEN-GLB-CAR-0682
La documentación presentada para dichas unidades no presenta observaciones.
• Camión, Placa: BDG-925.
• Equipo sin identificador.
En virtud de lo expuesto, se da la conformidad el ingreso y operación de los referidos vehículos y equipo.
"""
        with self.assertRaises(ExtractionError):
            parse_response(text, Path("724.pdf"), 0)


class MatchingRulesTests(unittest.TestCase):
    def test_multiple_responses_are_not_silently_overwritten(self):
        cpc = Letter('CPC-1', 1, date(2026, 1, 1), 'CPC_AAM', Path('cpc.pdf'), 0,
                     equipment=[Equipment('AAA-111', 'Volquete')])
        responses = []
        for number, result in ((2, 'Aprobado'), (3, 'Observado-No conforme')):
            letter = Letter(f'AAM-{number}', number, date(2026, 1, number),
                            'AAM_CPC', Path('aam.pdf'), number, referenced_cpc='CPC-1')
            responses.append(ParsedResponse(letter, {'AAA-111': Evaluation('AAA-111', result, result)}))
        rows, warnings = build_rows([cpc], responses)
        self.assertEqual(rows[0].result, '')
        self.assertEqual(rows[0].aam_correlative, '')
        self.assertIn('varias respuestas', warnings[0])

    def test_observations_with_parenthesized_plate(self):
        text = '''Lima, 19 de mayo de 2026
CARTA No. PSR2-F2-AAM-CPC-GEN-GLB-CAR-0187
Referencia: Carta No. PSR2-F2-CPC-AAM-GEN-GLB-CAR-0241
• Volquete FAW (Placa BWK-844): Falta el Certificado de Opacidad.
• Excavadora KOMATSU (Placa/Serie EXC35-12): Certificado sin vigencia.
'''
        parsed = parse_response(text, Path('0187.pdf'), 0)
        self.assertEqual(set(parsed.evaluations), {'BWK-844', 'EXC35-12'})
        self.assertIn('Opacidad', parsed.evaluations['BWK-844'].detail)
        self.assertEqual(parsed.evaluations['EXC35-12'].result, 'Observado-No conforme')

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


class FlexibleDocumentFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [str(path) for path in FLEXIBLE_FORMAT_PDFS if not path.is_file()]
        if missing:
            raise unittest.SkipTest("Faltan PDF de formatos flexibles: " + ", ".join(missing))
        cls.rows, cls.warnings = extract_documents(FLEXIBLE_FORMAT_PDFS)
        cls.by_key = {
            (row.cpc_correlative, row.equipment_code): row for row in cls.rows
        }

    def test_extracts_complete_first_and_followup_presentations(self):
        counts = {
            correlative: sum(row.cpc_correlative == correlative for row in self.rows)
            for correlative in (230, 249, 425)
        }
        self.assertEqual(counts, {230: 14, 249: 6, 425: 4})
        self.assertIn((230, "BHK713"), self.by_key)
        self.assertEqual(self.by_key[(230, "BVL-812")].equipment_type, "Camioneta")
        self.assertEqual(self.by_key[(230, "CAY-928")].equipment_type, "Camión grúa")

    def test_individual_observations_and_implicit_approvals(self):
        observed = {"BVL-812", "D4J-868", "CET-756", "CEK-912", "CDR-725", "CET-757"}
        for row in (item for item in self.rows if item.cpc_correlative == 230):
            expected = "Observado-No conforme" if row.equipment_code in observed else "Aprobado"
            with self.subTest(code=row.equipment_code):
                self.assertEqual(row.result, expected)
        self.assertIn("programa de mantenimiento", self.by_key[(230, "CDR-725")].detail.lower())
        self.assertNotIn("CONSORCIO", self.by_key[(230, "CET-757")].detail)

    def test_blanket_and_explicit_followup_approvals(self):
        for correlative in (249, 425):
            for row in (item for item in self.rows if item.cpc_correlative == correlative):
                with self.subTest(correlative=correlative, code=row.equipment_code):
                    self.assertEqual(row.result, "Aprobado")
                    self.assertEqual(row.detail, "Aprobado")
                    self.assertEqual(row.procedure_type, "Segunda presentación")

    def test_generic_followup_types_are_inherited(self):
        self.assertEqual(self.by_key[(425, "BVL-812")].equipment_type, "Camioneta")
        for code in ("CET-756", "CDR-725", "CET-757"):
            self.assertEqual(self.by_key[(425, code)].equipment_type, "Volquete")

    def test_flexible_documents_have_no_warnings(self):
        self.assertEqual(self.warnings, [])


class DemobilizationExtractionTests(unittest.TestCase):
    def test_extracts_sixteen_movement_rows_with_technical_data(self):
        parsed = parse_demobilization_request(
            extract_pdf_text(DEMOBILIZATION_REQUEST), DEMOBILIZATION_REQUEST, 0
        )
        self.assertEqual(len(parsed.items), 16)
        by_code = {item.code: item for item in parsed.items}
        self.assertEqual(by_code["CET-756"].brand, "SHACMAN")
        self.assertEqual(by_code["CET-756"].model, "SX331862306C")
        self.assertEqual(by_code["CET-756"].serial, "LZGJR4Z67SX033296")
        self.assertEqual(by_code["CET-756"].departure_date, date(2026, 9, 2))
        self.assertEqual(by_code["BWK-844"].brand, "FAW")

    def test_response_authorizes_the_same_sixteen_plates(self):
        request = parse_demobilization_request(
            extract_pdf_text(DEMOBILIZATION_REQUEST), DEMOBILIZATION_REQUEST, 0
        )
        response = parse_demobilization_response(
            extract_pdf_text(DEMOBILIZATION_RESPONSE), DEMOBILIZATION_RESPONSE, 1
        )
        self.assertEqual(
            set(response.equipment_codes), {item.code for item in request.items}
        )
        self.assertEqual(response.letter.referenced_cpc, request.letter.full_number)

    def test_rejects_response_with_missing_and_additional_plates(self):
        request = parse_demobilization_request(
            extract_pdf_text(DEMOBILIZATION_REQUEST), DEMOBILIZATION_REQUEST, 0
        )
        parsed_response = parse_demobilization_response(
            extract_pdf_text(DEMOBILIZATION_RESPONSE), DEMOBILIZATION_RESPONSE, 1
        )
        missing_code = parsed_response.equipment_codes[-1]
        response = ParsedDemobilizationResponse(
            letter=parsed_response.letter,
            equipment_codes=[
                *parsed_response.equipment_codes[:-1],
                "ZZZ-999",
            ],
        )

        with self.assertRaises(ExtractionError) as raised:
            validate_demobilization_pair(request, response)
        self.assertIn(f"Faltantes: ['{missing_code}']", str(raised.exception))
        self.assertIn("adicionales: ['ZZZ-999']", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

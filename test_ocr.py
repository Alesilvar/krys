from pathlib import Path
from unittest.mock import patch
import subprocess

import pytest

from extractor import ExtractionError, extract_pdf_text


def result(stdout=b'', stderr=b'', returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_texto_seleccionable_no_ejecuta_ocr(tmp_path):
    pdf = tmp_path / 'carta.pdf'
    pdf.touch()
    with patch('extractor.subprocess.run', return_value=result(b'Texto existente')) as run:
        assert extract_pdf_text(pdf) == 'Texto existente'
    assert run.call_count == 1


def test_ocr_ordena_paginas_y_limpia_temporales(tmp_path):
    pdf = tmp_path / 'carta.pdf'
    pdf.touch()
    temporary = []

    def run(command, **kwargs):
        if command[0] == 'pdftotext':
            return result(b' \f ')
        if command[0] == 'pdftoppm':
            prefix = Path(command[-1])
            temporary.append(prefix.parent)
            for number in (10, 2, 1):
                prefix.with_name(f'pagina-{number}.png').touch()
            return result()
        return result(Path(command[1]).stem.encode())

    with patch('extractor.subprocess.run', side_effect=run):
        assert extract_pdf_text(pdf).split() == ['pagina-1', 'pagina-2', 'pagina-10']
    assert not temporary[0].exists()


def test_error_de_pdf_no_activa_ocr(tmp_path):
    pdf = tmp_path / 'carta.pdf'
    pdf.touch()
    with patch('extractor.subprocess.run', return_value=result(stderr=b'PDF invalido', returncode=1)) as run:
        with pytest.raises(ExtractionError, match='PDF invalido'):
            extract_pdf_text(pdf)
    assert run.call_count == 1


def test_ocr_sin_dependencia_informa_error(tmp_path):
    pdf = tmp_path / 'carta.pdf'
    pdf.touch()
    with patch('extractor.subprocess.run', side_effect=[result(), FileNotFoundError()]):
        with pytest.raises(ExtractionError, match='tesseract'):
            extract_pdf_text(pdf)


def test_ocr_sin_texto_informa_error(tmp_path):
    pdf = tmp_path / 'carta.pdf'
    pdf.touch()
    with patch('extractor.subprocess.run', side_effect=[result(), result()]):
        with pytest.raises(ExtractionError, match='No se pudo reconocer texto'):
            extract_pdf_text(pdf)


def test_ocr_con_pagina_escaneada_de_carta_real(tmp_path):
    """Rasteriza una muestra real sin modificarla y prueba el flujo completo."""
    import os
    import shutil

    from extractor import parse_cpc

    samples = Path(os.environ.get('KRYS_TEST_SAMPLES_DIR', Path(__file__).resolve().parent.parent))
    original = samples / 'PSR2-F2-CPC-AAM-GEN-GLB-CAR-0150.pdf'
    if not original.is_file():
        pytest.skip(f'Falta el PDF de muestra: {original}')
    if any(shutil.which(tool) is None for tool in ('pdftotext', 'pdftoppm', 'tesseract')):
        pytest.skip('Se necesitan Poppler y Tesseract para la prueba de OCR')
    languages = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True, check=True)
    if 'spa' not in languages.stdout.splitlines():
        pytest.skip('Faltan los datos de idioma español de Tesseract')

    image_prefix = tmp_path / 'pagina'
    subprocess.run(
        ['pdftoppm', '-f', '1', '-l', '1', '-singlefile', '-scale-to-x', '1275',
         '-scale-to-y', '1650', '-jpeg', str(original), str(image_prefix)],
        check=True, capture_output=True, timeout=30,
    )
    jpeg = image_prefix.with_suffix('.jpg').read_bytes()
    content = b'q 612 0 0 792 0 0 cm /Im0 Do Q'
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /XObject /Subtype /Image /Width 1275 /Height 1650 '
        b'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length '
        + str(len(jpeg)).encode() + b' >>\nstream\n' + jpeg + b'\nendstream',
        b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'\nendstream',
    ]
    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f'{number} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode())
    pdf.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    scanned = tmp_path / 'carta-escaneada.pdf'
    scanned.write_bytes(pdf)

    selectable = subprocess.run(['pdftotext', str(scanned), '-'], capture_output=True, check=True)
    assert not selectable.stdout.strip()
    text = extract_pdf_text(scanned)
    letter = parse_cpc(text, scanned, 0)
    assert letter.correlative == 150
    assert {equipment.code for equipment in letter.equipment} == {'EXC35-14', 'RE8100-23'}


def test_carta_real_con_texto_no_ejecuta_ocr():
    import os

    from extractor import parse_cpc

    samples = Path(os.environ.get('KRYS_TEST_SAMPLES_DIR', Path(__file__).resolve().parent.parent))
    original = samples / 'PSR2-F2-CPC-AAM-GEN-GLB-CAR-0150.pdf'
    if not original.is_file():
        pytest.skip(f'Falta el PDF de muestra: {original}')
    with patch('extractor.extract_pdf_ocr', side_effect=AssertionError('OCR no debe ejecutarse')):
        letter = parse_cpc(extract_pdf_text(original), original, 0)
    assert letter.correlative == 150
    assert {equipment.code for equipment in letter.equipment} == {'EXC35-14', 'RE8100-23'}

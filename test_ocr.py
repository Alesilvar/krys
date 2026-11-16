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

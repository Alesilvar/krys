#!/usr/bin/env python3
"""Diagnostica cartas locales y compara filas con un CSV de referencia.

No escribe en la base de datos. Los resultados pueden contener datos privados.
"""
import argparse
import csv
from dataclasses import asdict
from datetime import date, datetime
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extractor import (ExtractionError, build_rows, extract_pdf_text, is_demobilization,
                       parse_cpc, parse_demobilization_request, parse_demobilization_response,
                       parse_letter_identity, parse_response)


def key_code(value):
    return re.sub(r'[^A-Z0-9]', '', str(value or '').upper())


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).split())


def compare_value(field, value):
    if field in ('cpc_date', 'aam_date'):
        for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
            try:
                return datetime.strptime(str(value), fmt).date().isoformat()
            except ValueError:
                pass
    value = normalized(value)
    if field == 'equipment_type':
        value = value.replace('camion volquete', 'volquete')
    return value


def read_csv(path):
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1252')
    dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
    result = []
    reader = csv.reader(io.StringIO(text, newline=''), dialect)
    for cells in reader:
        line = reader.line_num
        if len(cells) >= 11 and cells[1].strip().isdigit() and cells[6].strip():
            result.append((line, cells))
    return result


def audit(directory, csv_path=None, excluded=()):
    excluded = tuple(path.resolve() for path in excluded)
    paths = sorted(p for p in directory.rglob('*') if p.is_file() and p.suffix.lower() == '.pdf'
                   and not any(p.resolve().is_relative_to(root) for root in excluded))
    seen_hashes, seen_numbers = {}, {}
    documents, cpcs, responses = [], [], []
    for path in paths:
        record = {'path': str(path), 'status': '', 'letter': '', 'message': ''}
        documents.append(record)
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen_hashes:
                record.update(status='duplicate', message=seen_hashes[digest])
                continue
            seen_hashes[digest] = str(path)
            text = extract_pdf_text(path)
            identity = parse_letter_identity(text, path, 0)
            record['letter'] = identity.full_number
            if identity.full_number in seen_numbers:
                record.update(status='number_conflict', message=seen_numbers[identity.full_number])
                continue
            seen_numbers[identity.full_number] = str(path)
            if is_demobilization(text):
                parser = parse_demobilization_request if identity.direction == 'CPC_AAM' else parse_demobilization_response
                parsed = parser(text, path, 0)
                record['status'] = 'demobilization'
                record['items'] = len(parsed.items if identity.direction == 'CPC_AAM' else parsed.equipment_codes)
            elif identity.direction == 'CPC_AAM':
                cpcs.append(parse_cpc(text, path, len(cpcs)))
                record['status'] = 'presentation'
            else:
                responses.append(parse_response(text, path, len(responses)))
                record['status'] = 'response'
        except (ExtractionError, OSError, UnicodeError) as error:
            record.update(status='error', message=str(error))
    rows, warnings = build_rows(cpcs, responses)
    result = {'documents': documents, 'warnings': warnings, 'rows': [asdict(row) for row in rows]}
    if csv_path:
        refs = {}
        duplicates = []
        for line, cells in read_csv(csv_path):
            key = (int(cells[1]), key_code(cells[6]))
            if key in refs:
                duplicates.append({'line': line, 'key': key})
            else:
                refs[key] = (line, cells)
        actual = {}
        for row in rows:
            key = (row.cpc_correlative, key_code(row.equipment_code))
            if key in actual:
                duplicates.append({'source': 'extraction', 'key': key})
            else:
                actual[key] = row
        fields = {'owner': 0, 'cpc_date': 2, 'procedure_type': 4, 'equipment_type': 5,
                  'result': 7, 'aam_correlative': 9, 'aam_date': 10}
        differences = []
        matched = []
        for key in sorted(refs.keys() & actual.keys()):
            line, cells = refs[key]
            row = actual[key]
            changes = {}
            for field, index in fields.items():
                expected, got = cells[index], getattr(row, field)
                if compare_value(field, expected) != compare_value(field, got):
                    changes[field] = {'reference': expected, 'extracted': str(got)}
            entry = {'line': line, 'key': key, 'fields': changes}
            (differences if changes else matched).append(entry)
        result['comparison'] = {'reference_rows': sum(1 for _ in read_csv(csv_path)),
            'matched': matched, 'differences': differences, 'duplicate_keys': duplicates,
            'missing': [{'line': refs[k][0], 'key': k} for k in sorted(refs.keys() - actual.keys())],
            'extra': [list(k) for k in sorted(actual.keys() - refs.keys())],
            'not_compared': ['reception_date', 'detail', 'additional_data']}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--reference', type=Path, help='CSV de la hoja Equipos')
    parser.add_argument('--exclude', type=Path, action='append', default=[], help='Directorio que se excluye del inventario')
    parser.add_argument('--output', type=Path, required=True, help='Ruta del informe JSON privado')
    args = parser.parse_args()
    report = audit(args.directory, args.reference, args.exclude)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(f"Documentos: {len(report['documents'])}; filas extraídas: {len(report['rows'])}; informe: {args.output}")


if __name__ == '__main__':
    main()

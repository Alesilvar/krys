#!/usr/bin/env python3
"""Comprueba destinos de enlaces Markdown locales en la documentación del proyecto."""
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+['\"][^\n]*['\"])?\)")


def main():
    documents = [ROOT / name for name in ("README.md", "CONTRIBUTING.md", "AGENTS.md")]
    documents += sorted((ROOT / "docs").rglob("*.md"))
    failures = []
    for document in documents:
        if not document.is_file():
            failures.append(f"Falta el documento {document.relative_to(ROOT)}")
            continue
        in_fence = False
        for number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^\s*(`{3,}|~{3,})", line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in LINK.finditer(line):
                target = match.group(1).strip("<>")
                parts = urlsplit(target)
                if parts.scheme or parts.netloc or not parts.path:
                    continue
                path = document.parent / unquote(parts.path)
                if not path.exists():
                    failures.append(f"{document.relative_to(ROOT)}:{number}: enlace inexistente: {target}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Enlaces locales verificados en {len(documents)} documentos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

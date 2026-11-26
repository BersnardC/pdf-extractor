r"""
parse_fields.py — Descubre campos potenciales en un rango de páginas de un PDF.

Genera parsed_fields.json con la estructura exacta de fields_rules.json
(key_field = parsed por defecto), listo para crear o actualizar fields_rules.json.

Uso:
    python parse_fields.py --file BRTM_2.pdf --pages 2360,2370
    python parse_fields.py --folder D:\otra --file x.pdf --pages 1,50
"""

import argparse
import json
import os
import re
import sys

import pymupdf

from index import (
    MAX_LABEL_WORDS,
    REGEX_LABEL,
    detectar_columnas,
    normalizar_cache,
    obtener_lineas,
)

OUTPUT_REPORT = "parsed_fields.json"

# Familia NCL: NCL(11), NCL(12), NCL(13)... el número de clase varía
# indefinidamente (1..45+), por eso se colapsa a UNA entrada con regex
# en lugar de agregar ncl_11, ncl_12, ... individualmente.
# index.py la resuelve por fallback de regex en resolver_campo.
REGEX_NCL_PARSED = re.compile(r"^ncl_\d+$")


def parse_pages(valor):
    """--pages inicio,fin → (inicio, fin) 1-indexed inclusivo."""
    partes = valor.split(",")
    if len(partes) != 2:
        raise argparse.ArgumentTypeError(
            f"Formato inválido: '{valor}'. Usa --pages inicio,fin (ej. 10,20)"
        )
    try:
        inicio, fin = int(partes[0].strip()), int(partes[1].strip())
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Formato inválido: '{valor}'. Usa enteros: --pages 10,20"
        )
    if inicio < 1 or fin < inicio:
        raise argparse.ArgumentTypeError(
            f"Rango inválido: {inicio},{fin}. Se espera inicio ≥ 1 y inicio ≤ fin"
        )
    return inicio, fin


def main():
    parser = argparse.ArgumentParser(
        description="Descubrir fields potenciales en un rango de páginas de un PDF"
    )
    parser.add_argument(
        "--file",
        required=True,
        help="PDF a evaluar (nombre en --folder o path absoluto)",
    )
    parser.add_argument(
        "--folder",
        default="docs",
        help="Carpeta con el PDF (default: docs/)",
    )
    parser.add_argument(
        "--pages",
        required=True,
        type=parse_pages,
        metavar="INICIO,FIN",
        help="Rango de páginas 1-indexed inclusivo (ej. --pages 10,20)",
    )
    args = parser.parse_args()

    inicio, fin = args.pages
    ruta = args.file
    if not os.path.isfile(ruta):
        ruta = os.path.join(args.folder, os.path.basename(args.file))
    if not os.path.isfile(ruta):
        print(f"No existe el archivo: {args.file}")
        raise SystemExit(1)

    doc = pymupdf.open(ruta)
    total_pag = len(doc)
    if inicio > total_pag:
        print(f"Rango inválido: inicio={inicio} > páginas del PDF ({total_pag})")
        raise SystemExit(1)
    fin = min(fin, total_pag)

    print(f"Archivo: {os.path.basename(ruta)}")
    print(f"Páginas: {inicio}–{fin} (de {total_pag})")

    candidatos = {}  # parsed → {"raw_field", "page"}
    umbral_prev = None

    for num_pag in range(inicio - 1, fin):
        pagina = doc[num_pag]
        lineas = obtener_lineas(pagina)
        if not lineas:
            continue

        umbral, x0_logo = detectar_columnas(lineas, umbral_prev)
        umbral_prev = umbral
        alto = pagina.rect.height

        for x0, y0, texto in lineas:
            if y0 < 50 or y0 > alto - 40:
                continue
            # Solo columna de contenido (excluye marca y zona logo)
            if not (umbral <= x0 < x0_logo):
                continue
            m = REGEX_LABEL.match(texto)
            if not m or len(m.group(1).split()) > MAX_LABEL_WORDS:
                continue
            label = m.group(1).strip()
            parsed = normalizar_cache(label)
            if parsed not in candidatos:
                candidatos[parsed] = {
                    "raw_field": label,
                    "page": num_pag + 1,
                }

    doc.close()

    if not candidatos:
        print("No se detectaron labels candidatos en el rango indicado.")
        raise SystemExit(0)

    # Construir reporte con estructura exacta de fields_rules.json
    # key_field = parsed por defecto (el usuario lo edita después)
    reporte = {}
    ncl_collapsed = False
    for parsed in sorted(candidatos):
        raw = candidatos[parsed]["raw_field"]
        if REGEX_NCL_PARSED.match(parsed):
            # NCL es especial: familia abierta NCL(n) → UNA entrada con regex
            if not ncl_collapsed:
                reporte["ncl"] = {
                    "key_field": "ncl",
                    "raw_field": "NCL",
                    "regex": "^ncl_\\d+$",
                }
                ncl_collapsed = True
            continue
        reporte[parsed] = {
            "key_field": parsed,
            "raw_field": raw,
        }

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    print(f"Candidatos detectados: {len(candidatos)}")
    print(f"Reporte escrito: {OUTPUT_REPORT} ({len(reporte)} entradas)")
    if ncl_collapsed:
        print(
            "  NCL colapsado a 1 entrada con regex "
            "(familia NCL(n) abierta: 11, 12, 13...)"
        )
    print("\nParsed detectados:")
    for parsed, info in sorted(candidatos.items()):
        print(f"  {parsed}  (raw: \"{info['raw_field']}\", pág {info['page']})")
    print(
        f"\nSiguiente paso: revisar key_field en {OUTPUT_REPORT} "
        "y pegarlo/actualizar fields_rules.json"
    )


if __name__ == "__main__":
    main()

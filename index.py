import argparse
import json
import os
import re
import time
import unicodedata
from datetime import datetime

import pymupdf

# --- CONFIGURACIÓN ---
DOCS_DIR = "docs"
OUTPUT_DIR = "output/data"
RULES_PATH = "fields_rules.json"
UNKNOWN_PATH = os.path.join("output", "fields_unknown.json")
SUGGEST_PATH = os.path.join("output", "suggest.txt")

REGEX_MARCA = re.compile(r"^\d{9}$")
REGEX_LABEL = re.compile(r"^([A-ZÀ-Ý][A-Za-zÀ-ÿ0-9\s\(\)/]*?):\s*(.*)$")
REGEX_FECHA_PUB = re.compile(r"RPI\s+\d+\s+de\s+(\d{2}/\d{2}/\d{4})")
MAX_LABEL_WORDS = 5

# Claves estructurales que no vienen de fields_rules.json
CLAVES_ESTRUCTURALES = {
    "marca",
    "fecha_publicacion",
    "pagina_pdf",
    "pagina_fin",
    "pdf_origen",
    "event_text",
    "logo_text",
    "has_logo",
}


def normalizar_clave(texto):
    """Elimina tildes/cedillas y convierte a snake_case limpio."""
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-zA-Z0-9]+", "_", sin_tildes.lower()).strip("_")


# Cache de normalizar_clave por label repetido
_NORM_CACHE = {}


def normalizar_cache(texto):
    v = _NORM_CACHE.get(texto)
    if v is None:
        v = normalizar_clave(texto)
        _NORM_CACHE[texto] = v
    return v


def cargar_rules():
    """Carga fields_rules.json → dict por parsed_field (lookup O(1)).
    Compila los campos 'regex' una sola vez para fallback."""
    if not os.path.isfile(RULES_PATH):
        return {}, []
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        rules = json.load(f)
    regex_rules = []
    for key, entry in rules.items():
        pat = entry.get("regex")
        if pat:
            regex_rules.append((re.compile(pat), entry))
    return rules, regex_rules


def cargar_unknown():
    """Carga fields_unknown.json si existe → dict por parsed_field."""
    if not os.path.isfile(UNKNOWN_PATH):
        return {}
    with open(UNKNOWN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def registrar_unknown(unknowns, parsed, raw_field, page, valor, archivo):
    """Agrega 1 entrada por campo desconocido (dedup por parsed)."""
    if parsed in unknowns:
        return
    unknowns[parsed] = {
        "raw_field": raw_field,
        "page": page,
        "value_example": valor[:200],
        "file": archivo,
    }


def resolver_campo(label, rules, regex_rules=(), strict=True):
    """
    Devuelve (key_field, parsed, estado):
      "known"   → en rules / regex / estructural → key_field de rules
      "auto"    → fuera de rules pero aceptado (bootstrap o strict=false) → key=parsed
      "unknown" → fuera de rules y strict=true → no entra al JSON
    """
    parsed = normalizar_cache(label)
    entry = rules.get(parsed)
    if entry:
        return entry.get("key_field", parsed), parsed, "known"
    for rx, entry in regex_rules:
        if rx.match(parsed):
            return entry.get("key_field", parsed), parsed, "known"
    if parsed in CLAVES_ESTRUCTURALES:
        return parsed, parsed, "known"
    if not rules or not strict:
        # Bootstrap sin rules, o --strict false: aceptar el candidato
        return parsed, parsed, "auto"
    return parsed, parsed, "unknown"


def extraer_fecha_pub(doc):
    for pno in range(min(5, len(doc))):
        m = REGEX_FECHA_PUB.search(doc[pno].get_text("text"))
        if m:
            return m.group(1)
    return "Desconocida"


def detectar_columnas(lineas, umbral_prev=None):
    """
    Detecta X dinámicas:
      - ^\\d{9}$  → columna marca
      - Etiqueta: → columna contenido (a la derecha de la marca)
      - zona derecha → logo_text
    """
    x0_marcas = []
    x0_labels = []
    for x0, _y0, texto in lineas:
        t = texto.strip()
        if not t:
            continue
        if REGEX_MARCA.match(t):
            x0_marcas.append(x0)
        elif REGEX_LABEL.match(t):
            x0_labels.append(x0)

    if x0_marcas:
        x0_marca = min(x0_marcas)
        cont = [x for x in x0_labels if x > x0_marca + 40]
        x0_cont = min(cont) if cont else x0_marca + 64.2
    elif umbral_prev is not None:
        x0_marca = umbral_prev - 30
        x0_cont = umbral_prev + 30
    else:
        if x0_labels:
            xs = sorted(x0_labels)
            x0_cont = xs[len(xs) // 2]
        else:
            x0_cont = 133.7
        x0_marca = x0_cont - 64.2

    umbral = x0_cont - 25.0
    if umbral <= x0_marca:
        umbral = (x0_marca + x0_cont) / 2.0
    x0_logo = x0_cont + 280.0
    return umbral, x0_logo


def obtener_lineas(pagina):
    """Extrae líneas (x0, y0, texto) usando get_text('dict')."""
    d = pagina.get_text("dict")
    lineas = []
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            x0, y0, x1, y1 = l["bbox"]
            texto = "".join(s["text"] for s in l["spans"]).strip()
            if texto:
                lineas.append((x0, y0, texto))
    lineas.sort(key=lambda t: (round(t[1], 1), round(t[0], 1)))
    return lineas


class Registro:
    def __init__(self, marca, fecha_pub, pagina_ini, pdf_origen):
        self.datos = {
            "marca": marca,
            "fecha_publicacion": fecha_pub,
            "pagina_pdf": pagina_ini,
            "pdf_origen": pdf_origen,
            "has_logo": False,
        }
        self.ultimo_campo = None  # key_field del campo multilínea abierto
        self.swallowing = False   # tragando continuaciones de campo unknown
        self.event_text_set = False
        self.text_counter = 0
        self.pagina_fin = pagina_ini
        self.ya_guardado = False  # ya se escribió a disco (re-guardar tras logos)

    def set_event_text(self, texto):
        self.datos["event_text"] = texto
        self.event_text_set = True
        self.ultimo_campo = None

    def set_campo(self, key_field, valor):
        if key_field in self.datos and key_field not in CLAVES_ESTRUCTURALES:
            # Merge en lista si la key ya existe (ej. ncl_11 + ncl_13 → ncl)
            actual = self.datos[key_field]
            if isinstance(actual, list):
                actual.append(valor)
            else:
                self.datos[key_field] = [actual, valor]
        else:
            self.datos[key_field] = valor
        self.ultimo_campo = key_field
        self.swallowing = False

    def start_swallow(self):
        """Campo unknown: traga sus continuaciones hasta el próximo label."""
        self.ultimo_campo = None
        self.swallowing = True

    def anexar_continuacion(self, texto):
        """Anexa línea sin label al último campo abierto. Nunca genera text_x."""
        if self.ultimo_campo is None:
            return False
        actual = self.datos.get(self.ultimo_campo)
        if actual is None:
            return False
        if isinstance(actual, list):
            actual[-1] = (actual[-1] + " " + texto).strip()
        else:
            self.datos[self.ultimo_campo] = (actual + " " + texto).strip()
        return True

    def add_text_orphan(self, texto):
        """Texto huérfano sin label y sin campo abierto → text_N."""
        self.text_counter += 1
        self.datos[f"text_{self.text_counter}"] = texto


def guardar_registro(reg, output_dir):
    marca = reg.datos["marca"]
    reg.datos["pagina_fin"] = reg.pagina_fin
    ruta = os.path.join(output_dir, f"{marca}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(reg.datos, f, ensure_ascii=False, indent=2)


def procesar_pdf(
    ruta_pdf, output_dir, rules, regex_rules, unknowns, max_pag=None, strict=True
):
    nombre_pdf = os.path.basename(ruta_pdf)
    print(f"\n=== Procesando {nombre_pdf} ===")
    doc = pymupdf.open(ruta_pdf)
    fecha_pub = extraer_fecha_pub(doc)
    print(f"  Fecha publicación: {fecha_pub}")

    registro_actual = None
    total_registros = 0
    total_pngs = 0
    total_has_logo = 0
    umbral_prev = None
    fin = min(max_pag, len(doc)) if max_pag else len(doc)

    marcas_con_logo = set()

    def _contar_logo(reg):
        nonlocal total_has_logo
        m = reg.datos["marca"]
        if reg.datos.get("has_logo") and m not in marcas_con_logo:
            marcas_con_logo.add(m)
            total_has_logo += 1

    def _guardar(reg):
        nonlocal total_registros
        guardar_registro(reg, output_dir)
        reg.ya_guardado = True
        total_registros += 1
        _contar_logo(reg)

    for num_pag in range(fin):
        pagina = doc[num_pag]
        lineas = obtener_lineas(pagina)
        if not lineas:
            continue

        umbral, x0_logo = detectar_columnas(lineas, umbral_prev)
        umbral_prev = umbral
        alto = pagina.rect.height

        # Imágenes raster en zona del logo (X)
        imgs_pagina = []
        for img_info in pagina.get_images(full=True):
            xref = img_info[0]
            for rect in pagina.get_image_rects(xref):
                if rect.width > 15 and rect.height > 15 and rect.x0 >= x0_logo - 20:
                    imgs_pagina.append(
                        {
                            "xref": xref,
                            "y0": rect.y0,
                            "y1": rect.y1,
                            "yc": (rect.y0 + rect.y1) / 2,
                        }
                    )
        # Vectores grandes en zona del logo (logo vectorial, sin PNG)
        vectores_pagina = []
        for d in pagina.get_drawings():
            r = d["rect"]
            if (
                r.x0 >= x0_logo - 20
                and 15 < r.width < 200
                and 15 < r.height < 200
            ):
                vectores_pagina.append({"y0": r.y0, "y1": r.y1, "yc": (r.y0 + r.y1) / 2})

        marcas_en_pagina = []

        for x0, y0, texto in lineas:
            if y0 < 50 or y0 > alto - 40:
                continue

            # Zona logo (texto lateral)
            if x0 >= x0_logo:
                if registro_actual:
                    registro_actual.datos["logo_text"] = texto
                    registro_actual.datos["has_logo"] = True
                continue

            # Columna izquierda: número de marca
            if x0 < umbral:
                if REGEX_MARCA.match(texto.strip()):
                    if registro_actual:
                        _guardar(registro_actual)
                    registro_actual = Registro(
                        texto.strip(), fecha_pub, num_pag + 1, nombre_pdf
                    )
                    marcas_en_pagina.append((y0, registro_actual))
                continue

            # Columna de contenido
            if registro_actual is None:
                continue

            registro_actual.pagina_fin = num_pag + 1

            m = REGEX_LABEL.match(texto)
            if m and len(m.group(1).split()) <= MAX_LABEL_WORDS:
                # 1. Línea con label (≤5 palabras) → resolución por fields_rules
                label = m.group(1).strip()
                valor = m.group(2).strip()
                key_field, parsed, estado = resolver_campo(
                    label, rules, regex_rules, strict
                )
                if estado == "unknown":
                    registrar_unknown(
                        unknowns, parsed, label, num_pag + 1, valor, nombre_pdf
                    )
                    # Tragar campo unknown + sus continuaciones
                    registro_actual.start_swallow()
                else:
                    if estado == "auto":
                        # Fuera de rules pero aceptado → trazabilidad en suggest
                        registrar_unknown(
                            unknowns, parsed, label, num_pag + 1, valor, nombre_pdf
                        )
                    registro_actual.set_campo(key_field, valor)
            elif registro_actual.swallowing:
                # Continuación de campo unknown → tragar, no va a marca.json
                pass
            elif (
                not registro_actual.event_text_set
                and registro_actual.ultimo_campo is None
            ):
                # 2. Primera línea sin label de bloque nuevo → event_text
                registro_actual.set_event_text(texto)
            elif registro_actual.anexar_continuacion(texto):
                # 3. Continuación de campo multilínea/página → NUNCA text_x
                pass
            else:
                # 4. Huérfana → text_N
                registro_actual.add_text_orphan(texto)

        # Asociar logos de esta página a las marcas
        def _dueno(yc):
            if marcas_en_pagina:
                for i, (y_marca, reg) in enumerate(marcas_en_pagina):
                    y_fin = (
                        marcas_en_pagina[i + 1][0]
                        if i + 1 < len(marcas_en_pagina)
                        else alto
                    )
                    if y_marca - 40 <= yc < y_fin:
                        return reg
                return None
            # Página de continuación sin nº de marca
            return registro_actual

        for v in vectores_pagina:
            reg = _dueno(v["yc"])
            if reg:
                reg.datos["has_logo"] = True

        for img in imgs_pagina:
            propietario = _dueno(img["yc"])
            if propietario:
                try:
                    pix = pymupdf.Pixmap(doc, img["xref"])
                    if pix.n - pix.alpha > 3:
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    ruta_png = os.path.join(
                        output_dir, f"{propietario.datos['marca']}.png"
                    )
                    pix.save(ruta_png)
                    propietario.datos["has_logo"] = True
                    total_pngs += 1
                except Exception as e:
                    print(f"  Error imagen {propietario.datos['marca']}: {e}")

        # Refrescar en disco los registros ya guardados ANTES de asignar logos
        # (2 marcas en la misma página: la 1ª se guarda al ver la 2ª, sin logos aún)
        for _y, reg in marcas_en_pagina:
            if reg.ya_guardado:
                guardar_registro(reg, output_dir)
                _contar_logo(reg)

    if registro_actual:
        _guardar(registro_actual)

    doc.close()
    print(f"  Registros guardados: {total_registros}")
    print(f"  Logos: {total_has_logo} (PNG: {total_pngs})")
    return total_registros, total_pngs, total_has_logo


def escribir_unknown_y_suggest(unknowns):
    """Escribe fields_unknown.json y suggest.txt (solo si hay unknowns)."""
    if not unknowns:
        if os.path.isfile(UNKNOWN_PATH):
            os.remove(UNKNOWN_PATH)
        if os.path.isfile(SUGGEST_PATH):
            os.remove(SUGGEST_PATH)
        print("\nSin campos desconocidos nuevos.")
        return

    with open(UNKNOWN_PATH, "w", encoding="utf-8") as f:
        json.dump(unknowns, f, ensure_ascii=False, indent=2)

    lineas = [
        "Nuevos fields detectados - agregar a fields_rules.json y re-ejecutar:",
        "",
    ]
    for parsed, info in unknowns.items():
        lineas.append(
            f"  - {parsed} | raw: \"{info['raw_field']}\" "
            f"| pag {info['page']} | {info['file']}"
        )
    with open(SUGGEST_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")

    print(f"\nUnknowns escritos: {UNKNOWN_PATH} ({len(unknowns)})")
    print(f"Sugerencia escrita: {SUGGEST_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="Extraer registros RPI de los PDFs de una carpeta"
    )
    parser.add_argument(
        "--folder",
        default=DOCS_DIR,
        help="Carpeta con los PDFs de entrada (default: docs/)",
    )
    parser.add_argument(
        "--file",
        help="Procesar solo este PDF de la carpeta (ej. BRTM_1.pdf)",
    )
    parser.add_argument(
        "--files",
        help="Procesar varios PDFs de la carpeta, separados por coma (ej. a.pdf,b.pdf)",
    )

    def _parse_bool(v):
        return v.lower() in ("true", "1", "yes", "y")

    parser.add_argument(
        "--strict",
        type=_parse_bool,
        default=True,
        metavar="BOOL",
        help=(
            "true: solo fields de fields_rules.json (default); "
            "false: rules + labels que cumplan el patrón (key=parsed, "
            "también aparecen en suggest.txt)"
        ),
    )
    args = parser.parse_args()

    if args.file and args.files:
        print("Usa --file o --files, no ambos.")
        raise SystemExit(1)

    carpeta = args.folder
    if not os.path.isdir(carpeta):
        print(f"No existe el directorio {carpeta}/")
        raise SystemExit(1)

    os.makedirs("output", exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.file:
        nombres = [os.path.basename(args.file)]
    elif args.files:
        nombres = [
            n.strip() for n in args.files.split(",") if n.strip()
        ]
    else:
        nombres = sorted(
            f for f in os.listdir(carpeta) if f.lower().endswith(".pdf")
        )
        if not nombres:
            print(f"No hay PDFs en {carpeta}/")
            return

    faltantes = [
        n
        for n in nombres
        if not os.path.isfile(os.path.join(carpeta, n))
    ]
    if faltantes:
        print(f"No existen: {', '.join(faltantes)}")
        raise SystemExit(1)

    rules, regex_rules = cargar_rules()
    unknowns = cargar_unknown()
    print(f"Rules cargadas: {len(rules)} campos ({len(regex_rules)} con regex)")
    if not rules:
        print(
            "AVISO: fields_rules.json ausente o vacío — "
            "bootstrap: los labels (≤5 palabras) se aceptan como field; "
            "edita fields_rules.json para renombrar key_field."
        )
    if not args.strict and rules:
        print(
            "AVISO: --strict false — labels fuera de fields_rules.json "
            "se aceptan como field (key=parsed) y aparecen en suggest.txt"
        )
    print(f"Strict: {args.strict}")
    print(f"Carpeta: {carpeta}")
    print(f"PDFs a procesar: {len(nombres)}")

    total_regs = 0
    total_pngs = 0
    total_has_logo = 0
    t_total = time.perf_counter()

    for nombre in nombres:
        ruta = os.path.join(carpeta, nombre)
        t0 = time.perf_counter()
        try:
            r, p, h = procesar_pdf(
                ruta, OUTPUT_DIR, rules, regex_rules, unknowns, strict=args.strict
            )
            total_regs += r
            total_pngs += p
            total_has_logo += h
        except Exception as e:
            print(f"  ERROR procesando {nombre}: {e}")
        dt = time.perf_counter() - t0
        print(f"  [tiempo] {nombre}: {dt:.2f}s")

    dt_total = time.perf_counter() - t_total
    escribir_unknown_y_suggest(unknowns)
    print(f"\n=== TOTAL ===")
    print(f"Registros: {total_regs}")
    print(f"Logos: {total_has_logo} (PNG: {total_pngs})")
    print(f"[tiempo] Total: {dt_total:.2f}s ({len(nombres)} PDFs)")
    print(f"Salida: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()

import argparse
import json
import os
import re
import unicodedata
from datetime import datetime

import pymupdf

# --- CONFIGURACIÓN ---
DOCS_DIR = "docs"
OUTPUT_DIR = "output/data"
REPORTES_DIR = "output/reportes"
REGLAS_PATH = "reglas_campos.json"

REGEX_MARCA = re.compile(r"^\d{9}$")
REGEX_LABEL = re.compile(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\s\(\)/]*?):\s*(.*)$")
REGEX_NCL = re.compile(r"^NCL\(\d+\)$", re.IGNORECASE)
REGEX_FECHA_PUB = re.compile(r"RPI\s+\d+\s+de\s+(\d{2}/\d{2}/\d{4})")
REGEX_ESTADO = re.compile(
    r"^(Publica[çc][ãa]o\s+de|Exig[êe]ncia\s+formal)", re.IGNORECASE
)

# Claves que el script reconoce sin estar en reglas_campos.json
CLAVES_CONOCIDAS = {
    "marca",
    "fecha_publicacion",
    "pagina_pdf",
    "pagina_fin",
    "estado",
    "ncl",
    "text_logo",
    "tiene_logo",
    "campos_desconocidos",
    "pdf_origen",
}


def normalizar_clave(texto):
    """Elimina tildes/cedillas y convierte a snake_case limpio."""
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-zA-Z0-9]+", "_", sin_tildes.lower()).strip("_")


def cargar_reglas():
    with open(REGLAS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("campos_conocidos", {})


def es_label_conocido(clave_norm, reglas):
    if clave_norm in CLAVES_CONOCIDAS:
        return True
    if clave_norm in reglas:
        return True
    if REGEX_NCL.match(clave_norm.replace(" ", "_").upper()) or clave_norm.startswith("ncl"):
        return True
    return False


def resolver_clave(label, reglas):
    """Devuelve (clave_json, es_desconocido)."""
    clave_norm = normalizar_clave(label)
    if REGEX_NCL.match(label.strip()) or clave_norm.startswith("ncl"):
        return "ncl", False
    if clave_norm in reglas:
        return reglas[clave_norm], False
    if clave_norm in CLAVES_CONOCIDAS:
        return clave_norm, False
    return clave_norm, True


def extraer_fecha_pub(doc):
    for pno in range(min(5, len(doc))):
        m = REGEX_FECHA_PUB.search(doc[pno].get_text("text"))
        if m:
            return m.group(1)
    return "Desconocida"


def detectar_columnas(lineas, umbral_prev=None):
    """
    Detecta X dinámicas a partir de líneas con:
      - ^\\d{9}$  → columna marca
      - Etiqueta: → columna contenido (solo a la derecha de la marca)
      - zona derecha → text_logo
    Devuelve (umbral, x0_logo).
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
        # Labels que están a la derecha de la columna marca (descarta intro izq.)
        cont = [x for x in x0_labels if x > x0_marca + 40]
        x0_cont = min(cont) if cont else x0_marca + 64.2
    elif umbral_prev is not None:
        # Página de continuación sin marca: reutilizar umbral anterior
        x0_marca = umbral_prev - 30
        x0_cont = umbral_prev + 30
    else:
        # Sin marcas ni umbral previo: usar mediana de labels como contenido
        if x0_labels:
            xs = sorted(x0_labels)
            x0_cont = xs[len(xs) // 2]
        else:
            x0_cont = 133.7
        x0_marca = x0_cont - 64.2

    # Umbral cerca de la columna de contenido: deja fuera líneas intro intermedias
    umbral = x0_cont - 25.0
    if umbral <= x0_marca:
        umbral = (x0_marca + x0_cont) / 2.0
    # Zona logo: contenido + margen amplio (típ. 441 vs 133)
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
        }
        self.ultimo_campo = None  # clave JSON del campo multilínea abierto
        self.ultimo_es_desconocido = False
        self.campos_desconocidos = {}  # clave_norm -> valor
        self.labels_desconocidos = {}  # clave_norm -> {label_original, ejemplos}
        self.pagina_fin = pagina_ini

    def set_campo(self, clave, valor, es_desconocido, label_original=None):
        if clave == "ncl":
            if "ncl" in self.datos:
                actual = self.datos["ncl"]
                if isinstance(actual, list):
                    actual.append(valor)
                else:
                    self.datos["ncl"] = [actual, valor]
            else:
                self.datos["ncl"] = valor
            self.ultimo_campo = "ncl"
            self.ultimo_es_desconocido = False
            return

        if es_desconocido:
            if clave in self.campos_desconocidos:
                self.campos_desconocidos[clave] += " " + valor
            else:
                self.campos_desconocidos[clave] = valor
            if clave not in self.labels_desconocidos:
                self.labels_desconocidos[clave] = {
                    "label_original": label_original or clave,
                    "ejemplo_valor": valor,
                }
            self.ultimo_campo = clave
            self.ultimo_es_desconocido = True
            return

        self.datos[clave] = valor
        self.ultimo_campo = clave
        self.ultimo_es_desconocido = False

    def anexar_continuacion(self, texto):
        """Anexa línea sin label al último campo abierto (conocido o desconocido)."""
        if self.ultimo_campo is None:
            return False
        if self.ultimo_es_desconocido:
            if self.ultimo_campo not in self.campos_desconocidos:
                return False
            self.campos_desconocidos[self.ultimo_campo] += " " + texto
            return True
        actual = self.datos.get(self.ultimo_campo)
        if actual is None:
            return False
        if isinstance(actual, list):
            actual[-1] = (actual[-1] + " " + texto).strip()
        else:
            self.datos[self.ultimo_campo] = (actual + " " + texto).strip()
        return True

    def finalizar(self):
        if self.campos_desconocidos:
            self.datos["campos_desconocidos"] = self.campos_desconocidos
        return self.datos


def guardar_registro(reg, output_dir):
    marca = reg.datos["marca"]
    ruta = os.path.join(output_dir, f"{marca}.json")
    datos = reg.finalizar()
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def extraer_imagenes(pagina, doc, marca, output_dir):
    """Extrae imágenes de la página y las asocia por posición vertical a la marca."""
    imagenes = []
    for img_info in pagina.get_images(full=True):
        xref = img_info[0]
        for rect in pagina.get_image_rects(xref):
            if rect.width > 15 and rect.height > 15:
                imagenes.append({"xref": xref, "y0": rect.y0})

    if not imagenes:
        return False

    # Asociar por y0: la imagen debe estar en el rango de la marca
    # (desde y0 de la marca hasta el fin de página o siguiente marca)
    # Simplificado: tomar la imagen más cercana por debajo de la y de la marca
    # En la práctica cada marca tiene su logo en su bloque
    try:
        # Usar la primera imagen como logo de la marca actual
        # (en RPI cada registro tiene un logo)
        img = imagenes[0]
        pix = pymupdf.Pixmap(doc, img["xref"])
        if pix.n - pix.alpha > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        ruta_png = os.path.join(output_dir, f"{marca}.png")
        pix.save(ruta_png)
        return True
    except Exception as e:
        print(f"  Error guardando imagen de {marca}: {e}")
        return False


def procesar_pdf(ruta_pdf, output_dir, reporte_acumulado, max_pag=None):
    nombre_pdf = os.path.basename(ruta_pdf)
    print(f"\n=== Procesando {nombre_pdf} ===")
    doc = pymupdf.open(ruta_pdf)
    fecha_pub = extraer_fecha_pub(doc)
    print(f"  Fecha publicación: {fecha_pub}")

    registro_actual = None
    total_registros = 0
    total_logos = 0
    umbral_prev = None
    fin = min(max_pag, len(doc)) if max_pag else len(doc)

    for num_pag in range(fin):
        pagina = doc[num_pag]
        lineas = obtener_lineas(pagina)
        if not lineas:
            continue

        umbral, x0_logo = detectar_columnas(lineas, umbral_prev)
        umbral_prev = umbral
        alto = pagina.rect.height

        # Recopilar imágenes de la página con su y0
        imgs_pagina = []
        for img_info in pagina.get_images(full=True):
            xref = img_info[0]
            for rect in pagina.get_image_rects(xref):
                if rect.width > 15 and rect.height > 15:
                    imgs_pagina.append({"xref": xref, "y0": rect.y0})

        marcas_en_pagina = []  # (y0, registro) para asociar logos

        for x0, y0, texto in lineas:
            # Ignorar encabezado y pie
            if y0 < 50 or y0 > alto - 40:
                continue

            # Zona logo (texto lateral)
            if x0 >= x0_logo:
                if registro_actual:
                    registro_actual.datos["text_logo"] = texto
                continue

            # Columna izquierda: número de marca
            if x0 < umbral:
                if REGEX_MARCA.match(texto.strip()):
                    # Guardar registro anterior
                    if registro_actual:
                        guardar_registro(registro_actual, output_dir)
                        total_registros += 1
                    registro_actual = Registro(texto.strip(), fecha_pub, num_pag + 1, nombre_pdf)
                    marcas_en_pagina.append((y0, registro_actual))
                # Otros textos izquierdos (intro legal) se ignoran
                continue

            # Columna de contenido
            if registro_actual is None:
                # Contenido antes de cualquier marca (intro) → ignorar
                continue

            registro_actual.pagina_fin = num_pag + 1

            m = REGEX_LABEL.match(texto)
            if m:
                label = m.group(1).strip()
                valor = m.group(2).strip()
                clave, es_desc = resolver_clave(label, cargar_reglas_cache())
                registro_actual.set_campo(clave, valor, es_desc, label_original=label)
                if es_desc:
                    reporte_acumulado.setdefault(
                        clave,
                        {
                            "label_original": label,
                            "clave_normalizada": clave,
                            "apariciones": 0,
                            "ejemplo_valor": valor,
                            "ejemplo_marca": registro_actual.datos["marca"],
                            "ejemplo_pagina": num_pag + 1,
                            "pdf": nombre_pdf,
                        },
                    )
                    reporte_acumulado[clave]["apariciones"] += 1
            elif REGEX_ESTADO.match(texto):
                # Línea de estado (Publicação de..., etc.)
                if "estado" not in registro_actual.datos:
                    registro_actual.datos["estado"] = texto
                    registro_actual.ultimo_campo = None
                    registro_actual.ultimo_es_desconocido = False
            else:
                # Línea sin label → continuación de campo multilínea
                if not registro_actual.anexar_continuacion(texto):
                    # Campo huérfano → reportar
                    clave_huerfana = f"linea_sin_label_p{num_pag + 1}"
                    reporte_acumulado.setdefault(
                        f"sin_label_{registro_actual.datos['marca']}_{num_pag + 1}",
                        {
                            "label_original": None,
                            "clave_normalizada": "linea_sin_label",
                            "apariciones": 0,
                            "ejemplo_valor": texto[:120],
                            "ejemplo_marca": registro_actual.datos["marca"],
                            "ejemplo_pagina": num_pag + 1,
                            "pdf": nombre_pdf,
                            "tipo": "bloque_sin_label",
                        },
                    )
                    reporte_acumulado[
                        f"sin_label_{registro_actual.datos['marca']}_{num_pag + 1}"
                    ]["apariciones"] += 1

        # Asociar logos de esta página a las marcas
        if imgs_pagina and marcas_en_pagina:
            marcas_en_pagina.sort(key=lambda t: t[0])
            for img in imgs_pagina:
                propietario = None
                for i, (y_marca, reg) in enumerate(marcas_en_pagina):
                    y_fin = (
                        marcas_en_pagina[i + 1][0]
                        if i + 1 < len(marcas_en_pagina)
                        else alto
                    )
                    if y_marca - 10 <= img["y0"] < y_fin:
                        propietario = reg
                        break
                if propietario:
                    try:
                        pix = pymupdf.Pixmap(doc, img["xref"])
                        if pix.n - pix.alpha > 3:
                            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                        ruta_png = os.path.join(
                            output_dir, f"{propietario.datos['marca']}.png"
                        )
                        pix.save(ruta_png)
                        propietario.datos["tiene_logo"] = True
                        total_logos += 1
                    except Exception as e:
                        print(f"  Error imagen {propietario.datos['marca']}: {e}")

    # Guardar último registro
    if registro_actual:
        guardar_registro(registro_actual, output_dir)
        total_registros += 1

    doc.close()
    print(f"  Registros guardados: {total_registros}")
    print(f"  Logos extraídos: {total_logos}")
    return total_registros, total_logos


# Cache de reglas para no releer el JSON en cada línea
_REGLAS_CACHE = None


def cargar_reglas_cache():
    global _REGLAS_CACHE
    if _REGLAS_CACHE is None:
        _REGLAS_CACHE = cargar_reglas()
    return _REGLAS_CACHE


def escribir_reporte(reporte, reportes_dir):
    os.makedirs(reportes_dir, exist_ok=True)
    ruta = os.path.join(reportes_dir, "desconocidos.json")
    salida = {
        "fecha_ejecucion": datetime.now().isoformat(timespec="seconds"),
        "total_tipos_desconocidos": len(reporte),
        "campos": [v for v in reporte.values() if v.get("tipo") != "bloque_sin_label"],
        "bloques_sin_label": [
            v for v in reporte.values() if v.get("tipo") == "bloque_sin_label"
        ],
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print(f"\nReporte escrito: {ruta}")
    print(f"  Campos desconocidos: {len(salida['campos'])}")
    print(f"  Bloques sin label: {len(salida['bloques_sin_label'])}")


def main():
    parser = argparse.ArgumentParser(
        description="Extraer registros RPI de los PDFs en docs/"
    )
    parser.add_argument(
        "--file",
        help="Procesar solo este PDF de docs/ (ej. BRTM_1.pdf)",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(REPORTES_DIR, exist_ok=True)

    # Descubrir PDFs en docs/
    if not os.path.isdir(DOCS_DIR):
        print(f"No existe el directorio {DOCS_DIR}/")
        return

    if args.file:
        nombre = os.path.basename(args.file)
        ruta = os.path.join(DOCS_DIR, nombre)
        if not os.path.isfile(ruta):
            print(f"No existe {ruta}")
            raise SystemExit(1)
        pdfs = [nombre]
    else:
        pdfs = sorted(
            f for f in os.listdir(DOCS_DIR) if f.lower().endswith(".pdf")
        )
        if not pdfs:
            print(f"No hay PDFs en {DOCS_DIR}/")
            return

    print(f"PDFs a procesar: {len(pdfs)}")
    reporte_acumulado = {}
    total_regs = 0
    total_imgs = 0

    for nombre in pdfs:
        ruta = os.path.join(DOCS_DIR, nombre)
        try:
            r, i = procesar_pdf(ruta, OUTPUT_DIR, reporte_acumulado)
            total_regs += r
            total_imgs += i
        except Exception as e:
            print(f"  ERROR procesando {nombre}: {e}")

    escribir_reporte(reporte_acumulado, REPORTES_DIR)
    print(f"\n=== TOTAL ===")
    print(f"Registros: {total_regs}")
    print(f"Logos: {total_imgs}")
    print(f"Salida: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()

import json
import os
import re
import pymupdf

# --- CONFIGURACIÓN ---
PDF_PATH = "./docs/BRTM_1.pdf"  # Cambia esto por la ruta de tu PDF
OUTPUT_DIR = "output/data"
PAGINAS_A_PROBAR = (
    10,
    15,
)  # Rango de páginas para evaluar rápido (ej. pág 10 a 25)

# Umbral X que separa la columna izquierda (N° proceso) de la derecha (datos y logo)
UMBRAL_COLUMNA_X = 135.0
REGEX_PROCESO = re.compile(r"^\d{9}$")


def extraer_rpi(pdf_path, output_dir, rango_paginas=None):
    os.makedirs(output_dir, exist_ok=True)
    doc = pymupdf.open(pdf_path)

    inicio = rango_paginas[0] - 1 if rango_paginas else 0
    fin = min(rango_paginas[1], len(doc)) if rango_paginas else len(doc)

    # Extraer fecha de publicación de la primera página o encabezado
    fecha_pub = "Desconocida"
    match_fecha = re.search(
        r"de\s+(\d{2}/\d{2}/\d{4})", doc[inicio].get_text("text")
    )
    if match_fecha:
        fecha_pub = match_fecha.group(1)

    registro_actual = None
    total_extraidos = 0
    total_imagenes = 0

    def guardar_registro(reg):
        if not reg:
            return
        ruta_json = os.path.join(output_dir, f"{reg['marca']}.json")
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)

    for num_pag in range(inicio, fin):
        pagina = doc[num_pag]

        # 1. Obtener bloques de texto con coordenadas
        bloques = pagina.get_text("blocks")
        # Ordenar de arriba hacia abajo (y0) y luego de izquierda a derecha (x0)
        bloques.sort(key=lambda b: (round(b[1], 1), round(b[0], 1)))

        # 2. Obtener todas las imágenes de la página con sus coordenadas
        imagenes_pagina = []
        for img_info in pagina.get_images(full=True):
            xref = img_info[0]
            rects = pagina.get_image_rects(xref)
            for rect in rects:
                # Filtrar logos muy pequeños (ej. íconos de interfaz si los hubiera)
                if rect.width > 15 and rect.height > 15:
                    imagenes_pagina.append(
                        {"xref": xref, "y0": rect.y0, "y1": rect.y1}
                    )

        # Lista para vincular imágenes a los procesos detectados en esta página
        procesos_en_pagina = []

        for b in bloques:
            x0, y0, x1, y1, texto, _, tipo_bloque = b
            if tipo_bloque != 0:  # Ignorar bloques que no sean texto
                continue

            texto_limpio = texto.strip()
            if not texto_limpio:
                continue

            # Ignorar encabezados y pies de página
            if y0 < 50 or y0 > pagina.rect.height - 40:
                continue

            # ¿Es un número de proceso nuevo en la columna izquierda?
            lineas = [l.strip() for l in texto_limpio.split("\n") if l.strip()]
            primer_renglon = lineas[0]

            if x0 < UMBRAL_COLUMNA_X and REGEX_PROCESO.match(primer_renglon):
                # Guardar el registro anterior antes de empezar el nuevo
                if registro_actual:
                    guardar_registro(registro_actual)
                    total_extraidos += 1

                # Iniciar nuevo registro
                registro_actual = {
                    "marca": primer_renglon,
                    "fecha_publicacion": fecha_pub,
                    "pagina_pdf": num_pag + 1,
                    "tiene_logo": False,
                    "datos_columna_izq": lineas[1:],
                    "bloques_derecha": [],
                }
                procesos_en_pagina.append(
                    {"y0": y0, "registro": registro_actual}
                )
            else:
                # Es contenido que pertenece al registro activo
                if registro_actual:
                    if x0 < UMBRAL_COLUMNA_X:
                        registro_actual["datos_columna_izq"].extend(lineas)
                    else:
                        registro_actual["bloques_derecha"].append(texto_limpio)

        # 3. Vincular imágenes de esta página al proceso que le corresponde verticalmente
        procesos_en_pagina.sort(key=lambda p: p["y0"])
        for img in imagenes_pagina:
            propietario = None
            for i, proc in enumerate(procesos_en_pagina):
                y_inicio = proc["y0"] - 10  # Pequeño margen superior
                y_fin = (
                    procesos_en_pagina[i + 1]["y0"]
                    if i + 1 < len(procesos_en_pagina)
                    else pagina.rect.height
                )

                if y_inicio <= img["y0"] < y_fin:
                    propietario = proc["registro"]
                    break

            if propietario:
                try:
                    pix = pymupdf.Pixmap(doc, img["xref"])
                    # Convertir a RGB si viene en CMYK o con canal alfa problemático
                    if pix.n - pix.alpha > 3:
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)

                    ruta_png = os.path.join(
                        output_dir, f"{propietario['marca']}.png"
                    )
                    pix.save(ruta_png)
                    propietario["tiene_logo"] = True
                    total_imagenes += 1

                    # Actualizar el JSON si ya se había guardado
                    guardar_registro(propietario)
                except Exception as e:
                    print(
                        f"Error guardando imagen de {propietario['marca']}: {e}"
                    )

    # Guardar el último registro pendiente al terminar el bucle
    if registro_actual:
        guardar_registro(registro_actual)
        total_extraidos += 1

    print(f"Proceso finalizado.")
    print(f"Total registros guardados: {total_extraidos}")
    print(f"Total logos extraídos (.png): {total_imagenes}")


if __name__ == "__main__":
    extraer_rpi(PDF_PATH, OUTPUT_DIR, rango_paginas=PAGINAS_A_PROBAR) # rango_paginas es opcional, si no se pasa se procesan todas las páginas del PDF

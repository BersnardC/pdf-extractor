import pymupdf

# Abrir el archivo PDF
documento = pymupdf.open("./docs/BRTM_1.pdf")

texto_completo = ""

# Limitar el bucle a las primeras 20 páginas (índices 0 al 19)
for num_pagina, pagina in enumerate(documento[10:20]):
    texto_completo += f"--- Página {num_pagina + 1} ---\n"
    texto_completo += pagina.get_text() + "\n"

# Cerrar el documento para liberar memoria
documento.close()

print(texto_completo)

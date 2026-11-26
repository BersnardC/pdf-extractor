import pymupdf

doc = pymupdf.open("./docs/BRTM_1.pdf")
pagina = doc[10]  # Página 11 (índice 10)

print(f"Ancho de página: {pagina.rect.width} | Alto: {pagina.rect.height}\n")

for b in pagina.get_text("blocks"):
    x0, y0, x1, y1, texto, _, tipo = b
    if tipo == 0:  # Solo texto
        primer_renglon = texto.strip().split("\n")
        print(f"x0={x0:6.1f} | y0={y0:6.1f} | {primer_renglon[:55]}")

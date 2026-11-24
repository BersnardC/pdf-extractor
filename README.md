# PDF Parser — Extractor de registros RPI

Extrae registros de marcas (RPI / INPI) desde archivos PDF. Genera un JSON por marca con sus campos estructurados, más el logo en PNG cuando está presente.

## Requisitos

- Python 3.10+

## Instalación

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Uso

```bash
# Procesar todos los PDFs de docs/ (default)
python index.py

# Un solo PDF de docs/
python index.py --file BRTM_1.pdf

# Varios PDFs de docs/
python index.py --files BRTM_1.pdf,BRTM_2.pdf

# Todos los PDFs de otra carpeta (path absoluto o relativo)
python index.py --folder D:\otra\carpeta

# Varios PDFs de otra carpeta
python index.py --folder D:\otra\carpeta --files a.pdf,b.pdf
```

- `--folder` y `--file` / `--files` se pueden combinar.
- `--file` y `--files` son mutuamente excluyentes.
- La salida siempre se escribe en `output/data/` del proyecto.

## Estructura del proyecto

```
docs/                    PDFs de entrada (default)
fields_rules.json        Fields conocidos (fuente de verdad)
fields_unknown.json      Generado: campos desconocidos detectados
suggest.txt              Generado: qué agregar a fields_rules.json
output/data/             <marca>.json + <marca>.png
index.py                 Script principal
requirements.txt
```

## Configuración de fields (`fields_rules.json`)

Cada entrada usa la forma parseada del label como clave (tras normalizar: minúsculas, sin tildes, snake_case):

```json
{
  "titular": {
    "key_field": "titular",
    "raw_field": "Titular"
  },
  "ncl": {
    "key_field": "ncl",
    "raw_field": "NCL",
    "regex": "^ncl_\\d+$"
  }
}
```

| Propósito | Descripción |
|---|---|
| `key_field` | Nombre final de la clave en `<marca>.json` |
| `raw_field` | Texto original en el PDF (solo referencia / trazabilidad) |
| `regex` | Opcional. Matchea familias de labels sin agregar cada variante (ej. `NCL(11)`, `NCL(12)`, ...) |

### Flujo con campos desconocidos

1. Correr `python index.py`
2. Revisar `suggest.txt` (y `fields_unknown.json` para detalles)
3. Agregar los nuevos fields a `fields_rules.json`
4. Re-correr el script

Los campos unknown **no** se incluyen en `<marca>.json`; sus líneas de continuación se descartan hasta el siguiente label conocido.

## Campos de salida

Cada `<marca>.json` incluye:

| Campo | Descripción |
|---|---|
| `marca` | Número de marca (9 dígitos) |
| `fecha_publicacion` | Fecha del RPI |
| `pagina_pdf` / `pagina_fin` | Página inicial y final del registro |
| `pdf_origen` | Archivo PDF de origen |
| `event_text` | Primera línea del bloque (título/evento: Publicação..., Exigência..., Concessão..., etc.) |
| `titular`, `fecha_deposito`, ... | Campos definidos en `fields_rules.json` |
| `ncl` | Clasificación NCL (lista si hay varias) |
| `especificacion` | Texto multilínea, puede cruzar páginas |
| `text_N` | Líneas huérfanas sin label (`text_1`, `text_2`, ...) |
| `text_logo` | Texto detectado en la zona del logo (si existe) |
| `has_logo` | `true` / `false` — si se extrajo el logo PNG |

## Notas

- El script imprime el tiempo de procesamiento por PDF y el total.
- `output/data/` puede contener resultados de corridas anteriores; se sobrescriben por número de marca.
- Los PDFs de `docs/` están ignorados en git (ver `.gitignore`).

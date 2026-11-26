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

# Modo no estricto: aceptar labels fuera de rules (aparecen en suggest.txt)
python index.py --strict false
```

- `--folder` y `--file` / `--files` se pueden combinar.
- `--file` y `--files` son mutuamente excluyentes.
- `--strict` (default `true`): `true` = solo fields de `fields_rules.json`; `false` = rules + labels que cumplan el patrón (`key_field` = parsed, también se reportan en `suggest.txt`).
- La salida siempre se escribe en `output/data/` del proyecto.

### Descubrir fields (`parse_fields.py`)

Evalúa un rango de páginas de un PDF y genera `parsed_fields.json` con la
estructura exacta de `fields_rules.json` (listo para crear o actualizar):

```bash
# Requerido: --file y --pages inicio,fin (1-indexed, inclusivo)
python parse_fields.py --file BRTM_2.pdf --pages 2360,2370
python parse_fields.py --folder D:\otra --file x.pdf --pages 1,50
```

Sin `--pages` el script avisa y sale con error. El reporte usa
`key_field` = forma parseada por defecto — edítalo antes de pegarlo en
`fields_rules.json` si quieres renombrar (`fecha_deposito`, etc.).

**NCL es especial**: la familia `NCL(11)`, `NCL(12)`, `NCL(13)`... tiene un
número abierto de clases, así que el reporte la colapsa en **una sola
entrada** con `"regex": "^ncl_\\d+$"` en lugar de listar cada variante.

## Estructura del proyecto

```
docs/                    PDFs de entrada (default)
fields_rules.json        Fields conocidos (fuente de verdad)
output/fields_unknown.json  Generado: campos desconocidos detectados
output/suggest.txt       Generado: qué agregar a fields_rules.json
output/data/             <marca>.json + <marca>.png
parsed_fields.json       Generado: reporte de parse_fields (potenciales fields)
index.py                 Script principal
parse_fields.py          Descubridor de fields por rango de páginas
requirements.txt
bk/                      Scripts archivados (extractor_rpi, get_coords, get_text, index - old)
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

### Estados de un label al procesar

| Estado | Condición | En `<marca>.json` | En `suggest.txt` |
|---|---|---|---|
| `known` | en `fields_rules.json` (o regex/estructural) | ✅ `key_field` de rules | ❌ |
| `auto` | fuera de rules pero aceptado (`--strict false` o bootstrap sin rules) | ✅ `key_field` = parsed | ✅ |
| `unknown` | fuera de rules con `--strict true` (default) | ❌ (tragado) | ✅ |

**Flujo del analista con `--strict false`:**

1. Correr → campos nuevos entran al JSON **y** a `suggest.txt`
2. Decidir cuáles promover a `fields_rules.json` (con su `key_field`)
3. Re-correr → los promovidos usan `key_field` de rules y desaparecen de `suggest.txt`; el resto sigue reportado

### Flujo con campos desconocidos

1. Correr `python index.py`
2. Revisar `output/suggest.txt` (y `output/fields_unknown.json` para detalles)
3. Agregar los nuevos fields a `fields_rules.json`
4. Re-correr el script

**Alternativa (descubrimiento dirigido):** usar `parse_fields.py --pages inicio,fin`
sobre la zona de interés → editar `key_field` en `parsed_fields.json` →
pegar/actualizar en `fields_rules.json` → correr `index.py`.

Los campos unknown **no** se incluyen en `<marca>.json`; sus líneas de continuación se descartan hasta el siguiente label conocido.

### Reglas de detección de label

Una línea se considera label si:

1. Está en la columna de contenido
2. Inicia con **mayúscula**
3. Contiene `:`
4. El label (parto antes de `:`) tiene **máximo 5 palabras**

Si `fields_rules.json` no existe o está vacío, el script entra en **bootstrap**: todos los labels que cumplan estas reglas se aceptan como field con `key_field` = forma parseada (ej. `data_de_deposito`) y **también se reportan** en `suggest.txt` (borrador para crear rules). Edita `fields_rules.json` después para renombrar (`fecha_deposito`, etc.).

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
| `logo_text` | Texto detectado en la zona del logo (wordmark, si existe) |
| `has_logo` | `true` / `false` — imagen raster (PNG), wordmark (`logo_text`) o vector en zona logo |

## Notas

- El script imprime el tiempo de procesamiento por PDF y el total.
- `output/data/` puede contener resultados de corridas anteriores; se sobrescriben por número de marca.
- Los PDFs de `docs/` están ignorados en git (ver `.gitignore`).

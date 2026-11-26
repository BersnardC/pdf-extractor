# AGENTS.md — Contexto rápido para asistentes

## Qué es

Extractor de registros de marcas **RPI/INPI** (PDFs en `docs/`) → 1 JSON por marca en `output/data/<marca>.json` + logo `<marca>.png`.

- Python 3.10+ · única dependencia: `pymupdf` (`requirements.txt`)
- Código, comentarios, docs y respuestas en **español**
- Consola Windows cp1252 → sin emojis en prints

## Comandos

```bash
pip install -r requirements.txt

# Principal (default: todo docs/, strict=true)
python index.py
python index.py --folder docs
python index.py --file BRTM_1.pdf
python index.py --files a.pdf,b.pdf
python index.py --strict false          # acepta labels fuera de rules

# Descubridor de fields (NO lee fields_rules.json)
python parse_fields.py --file X.pdf --pages INICIO,FIN   # 1-indexed, inclusivo
```

## Arquitectura

| Archivo | Rol |
|---|---|
| `index.py` | Motor + CLI principal |
| `parse_fields.py` | Descubridor de fields por rango de páginas (importa utilidades de `index`) |
| `fields_rules.json` | Config de fields conocidos (estructura 2) — fuente de verdad |
| `output/` | **Todo** lo generado |
| `output/data/` | `<marca>.json` + `<marca>.png` |
| `output/fields_unknown.json` | Campos desconocidos detectados |
| `output/suggest.txt` | Qué agregar a `fields_rules.json` |
| `parsed_fields.json` | Reporte de `parse_fields` (raíz, se queda ahí) |
| `samples/` | PDFs mini para pruebas rápidas (gitignored) |
| `bk/` | Scripts archivados — **no tocar** |
| `session-ses_e048.md` | Historial de sesión — **no borrar** |

## Conceptos clave (costoso rediscover)

### Estructura 2 de `fields_rules.json`
- Clave del dict = `parsed_field` = `normalizar_clave(label)` (lookup O(1))
- `key_field` = nombre final en `<marca>.json`; `raw_field` = texto original (solo referencia)
- `regex` opcional para familias — **solo NCL lo usa**: `"^ncl_\\d+$"` (número de clase abierto 1..45+ → colapsado a UNA entrada; resuelto por fallback de regex en `resolver_campo`)

### 3 estados de label en `resolver_campo(label, rules, regex_rules, strict)`
| Estado | Condición | En `<marca>.json` | En `output/suggest.txt` |
|---|---|---|---|
| `known` | en rules o regex | ✅ usa `key_field` de rules | ❌ |
| `auto` | fuera de rules, aceptado (`strict=false` o bootstrap `not rules`) | ✅ `key=parsed` | ✅ siempre |
| `unknown` | fuera de rules con `strict=true` | ❌ tragado (`start_swallow`) | ✅ |

- `--strict` default **`true`** (bool parseado: `true/1/yes/y`)
- **Bootstrap**: si `fields_rules.json` no existe/vacío, todos los labels válidos → `auto` (borrador de rules)
- Flujo del analista: correr `--strict false` → promover campos a rules → re-correr → promovidos salen de suggest

### Detección de labels
- `REGEX_LABEL = ^([A-ZÀ-Ý][A-Za-zÀ-ÿ0-9\s\(\)/]*?):\s*(.*)$` — mayúscula obligatoria
- `MAX_LABEL_WORDS = 5` palabras antes de `:`
- Solo líneas en columna contenido (`umbral ≤ x0 < x0_logo`)
- Continuaciones de unknowns se tragan hasta el próximo label

### Jerarquía por línea (en `procesar_pdf`)
1. Label → `resolver_campo`
2. Primera línea sin label de bloque nuevo → `event_text` (reemplaza a `REGEX_ESTADO`; funciona para Publicação/Exigência/Concessão)
3. Campo abierto → `anexar_continuacion` (NUNCA `text_N`)
4. Huérfana sin campo abierto → `text_N`

### Logos
- `has_logo=true` si: PNG raster ✅ **o** `logo_text` wordmark ✅ **o** vector en zona logo ✅
- Zona logo: `x0 ≥ x0_logo-20`, centro-Y con margen 40; fallback a `registro_actual` en páginas de continuación
- Vectores via `get_drawings()` (15<w,h<200) → `has_logo` sin PNG aún
- **Re-guardado**: `Registro.ya_guardado` + re-guardar `marcas_en_pagina` tras asignar logos (2 marcas misma página); conteo deduplicado `marcas_con_logo`
- `pagina_fin` se sincroniza en `guardar_registro` (`reg.datos["pagina_fin"] = reg.pagina_fin`)

### Salida
- `ensure_ascii=False` (tildes visibles en JSON)
- Timing por PDF + total (`[tiempo]`, sin emoji)

## Reglas específicas

1. **NO hardcodear labels/`key_field` en Python** — van en `fields_rules.json`
2. **NO re-correr PDFs completos para verificar** (BRTM_1 = 8067 págs) → usar `samples/` o `max_pag=25` en pruebas
3. Sin emojis en prints (rompe cp1252); `ensure_ascii=False` al guardar JSON
4. `docs/*`, `output/*`, `samples/*` están en `.gitignore` — no commitear generados
5. No borrar `bk/` ni `session-ses_e048.md`
6. Cambios en reglas de detección (label/columnas/continuaciones) → actualizar `README.md`
7. `parse_fields.py` **NO** lee `fields_rules.json` (descubrimiento puro, `key_field`=parsed); `index.py` **SÍ**
8. Verificación mínima esperada: `python -m py_compile index.py parse_fields.py` + smoke con `samples/` o `max_pag=25`
9. Campo nuevo en rules → seguir el flujo de `--strict` (README: tabla de estados + flujo del analista)

## Pendientes conocidos

- **`with_img` + vector→PNG**: plan acordado (render vector con `pagina.get_pixmap(clip=rect)`; semántica: `has_logo` = imagen|texto|vector, `with_img` = solo PNG) — nunca implementado, pospuesto por bugs de logos
- **Fase 2 (paquete `pdfx/`)**: extracción del motor genérico a paquete + `schemas/` para el 2º tipo de PDF — solo conversado, no implementado

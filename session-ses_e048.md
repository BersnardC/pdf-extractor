# Extracción RPI con coords dinámicas y JSON

**Session ID:** ses_e048d6c80ffeNTvZdfhdPyeY8z
**Created:** 20/11/2026, 8:12:32 p.m.
**Updated:** 26/11/2026, 12:33:22 a.m.

---

## User

Preciso

---

## Assistant

**Tool: todowrite**

**Tool: read**

---

## Assistant

**Tool: edit**

**Tool: read**

---

## Assistant

**Tool: edit**

**Tool: read**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

Fix verificado en la pág. 2363. Smoke test rápido en BRTM_1:

**Tool: bash**

---

## Assistant

**Tool: todowrite**

---

## Assistant

Fix aplicado y verificado:

| Test | Resultado |
|---|---|
| BRTM_2 pág. 2363 → `501850812` | `has_logo: true` + PNG ✅ |
| `501854866` (misma pág.) | `has_logo: true` ✅ |
| BRTM_1 25 págs | 26 regs, 17 logos (antes 15 — recuperó 2 por el mismo bug) ✅ |

**Mecanismo**: `Registro.ya_guardado` + re-guardado de `marcas_en_pagina` después de asignar logos, solo a quien ya estaba en disco. Conteo de logos deduplicado por `marcas_con_logo` (sin doble conteo al re-guardar).

Queda pendiente el plan de **`with_img` + vector→PNG** que habíamos acordado — ¿lo hago ahora?

---

## User

Perfecto, que pasaria en el caso que no existiera el archivo fields_rules? 

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: read**

**Tool: read**

---

## Assistant

## Qué pasa hoy si no existe `fields_rules.json`

**No crashea** — degrada así:

| Paso | Comportamiento |
|---|---|
| `cargar_rules()` (`index.py:60-61`) | `if not os.path.isfile(...)` → devuelve `{}, []` silenciosamente |
| Consola | imprime `Rules cargadas: 0 campos (0 con regex)` — sin error |
| `resolver_campo` | todo label → `es_desconocido=True` (solo pasan las claves estructurales) |
| Cada campo (`Titular:...`, `NCL(11):...`, etc.) | → `fields_unknown.json` + `start_swallow()` → **no entra a `<marca>.json`** |
| Final | se escriben `fields_unknown.json` + `suggest.txt` con **todos** los campos detectados |

### Resultado en cada `<marca>.json`

```json
{
  "marca": "...",
  "fecha_publicacion": "...",
  "pagina_pdf": ...,
  "pdf_origen": "...",
  "has_logo": false,
  "event_text": "...",
  "text_1": "..."   // solo huérfanas sin label
}
```

Sin `titular`, `ncl`, `especificacion`, etc. — todo tragado como unknown.

### En la práctica es un "bootstrap"

1. Corres sin `fields_rules.json`
2. `suggest.txt` te lista todos los labels con su forma parseada
3. Creas `fields_rules.json` a partir de eso (key_field/raw_field)
4. Re-correr → campos llenos

---

**Posibles mejoras** (si te interesa):

1. **Aviso claro**: si rules está vacío, imprimir warning fuerte al inicio: *"`fields_rules.json` no existe o está vacío — todos los campos irán a unknown"`*
2. **Abortar**: `exit 1` si no hay rules (más estricto)
3. **Auto-bootstrap**: generar un `fields_rules.json` borrador desde los unknowns (con `key_field = parsed`, `raw_field = raw_field`) y pedir que lo edites

¿Quieres que cambie algo del comportamiento actual o solo era consulta?

---

## User

No, creo que mejor seria evaluar el bloque de la marca e intentar sacar los fields que cumplan con las reglas actuales: Nueva linea, inicien con Mayuscula tengan : y adicional agregaria otra que no superen 5 palabras. D hecho ninguna actualmente supera las 5, esta ultima regla creo que no esta, confirma estas dos cosas y el plan mas viable 

---

## Assistant

**Tool: read**

**Tool: bash**

---

## Assistant

## Confirmaciones

### 1. Reglas actuales del label (`REGEX_LABEL`, `index.py:19`)

```python
REGEX_LABEL = re.compile(r"^([A-ZÀ-Ý][A-Za-zÀ-ÿ0-9\s\(\)/]*?):\s*(.*)$")
```

| Regla | ¿Existe? |
|---|---|
| Nueva línea (se procesa línea a línea) | ✅ por diseño |
| Inicia con Mayúscula | ✅ `[A-ZÀ-Ý]` |
| Tiene `:` | ✅ |
| **Máx. 5 palabras** | ❌ **NO está** |

### 2. ¿Ningún field actual supera las 5 palabras?

**Confirmado.** Conteo de `raw_field` en `fields_rules.json`:

```
1: Apostila, Apresentação, CFE, Especificação, Natureza, NCL,
   Procurador, Protocolo, Titular
2: Elemento nominativo, Especificação traduzida, Prioridade unionista
3: Data de depósito, Detalhes do despacho, Motivo do indeferimento
4: Número da Inscrição Internacional
5: Data de recebimento pelo INPI   ← máximo exacto
```

**Max = 5**, ninguno excede. El límite de 5 no rompería nada actual.

---

## Plan viable

### A. Agregar límite de 5 palabras a `REGEX_LABEL`

No cabe limpio en la regex (contar palabras). Post-check en `resolver_campo` o al matchear:

```python
def es_label_valido(m):
    label = m.group(1).strip()
    return len(label.split()) <= 5
```

**Efecto**: líneas como  
`Esse procedimento precisa ser realizado em duas etapas: 1) Gere...`  
(9 palabras antes del `:`) → **dejan de ser label** → caen en continuación/`text_N` — refuerza el caso `duas etapas`.

### B. Bootstrap automático cuando `fields_rules` está vacío/ausente

Hoy: todo → unknown + swallow → JSON vacío.  
Propuesto en `resolver_campo`:

```python
# si rules está vacío (bootstrap) y el label cumple el patrón:
if not rules and es_label_valido(m):
    return parsed, parsed, False   # aceptar como field conocido
    # key_field = parsed, raw_field = label
```

Resultado sin `fields_rules.json`:

```json
{
  "marca": "...",
  "titular": "DEBORA...",
  "data_de_deposito": "27/03/2026",
  "ncl_11": "1, 5 e 42",
  ...
}
```

Y al final, los unknowns que **no** cumplan (o los que quieras renombrar) siguen yendo a `suggest.txt`.

**Alternativa más simple**: si `rules` vacío → warning fuerte + seguir con unknowns como hoy (bootstrap manual desde `suggest.txt`).

### C. ¿Aplicar el límite de 5 siempre (A) o solo en bootstrap (B)?

| Opción | Efecto |
|---|---|
| **A siempre** | más preciso en todos los modos; protege contra falsos labels largos |
| **A solo si rules vacío** | comportamiento actual intacto cuando hay rules |

Recomiendo **A siempre** + **B como fallback de bootstrap**.

---

### Pasos de implementación

1. Post-check ≤5 palabras en el match de label (antes de `resolver_campo`)
2. Si `rules` vacío y label válido → aceptar field (`key_field = parsed`)
3. Warning al arrancar si rules ausente/vacío
4. Verificación: BRTM_1 25 págs con rules → mismos conteos; sin rules → JSON con fields auto-detectados

¿Vas por **A siempre + B bootstrap**, o prefieres otra combinación?

---

## User

aplica el limite de 5, y el bootstrap automatico

---

## Assistant

**Tool: todowrite**

**Tool: read**

---

## Assistant

**Tool: edit**

**Tool: edit**

**Tool: edit**

---

## Assistant

**Tool: edit**

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: grep**

---

## Assistant

**Tool: grep**

**Tool: bash**

---

## Assistant

**Tool: read**

---

## Assistant

`pagina_fin` vive en el atributo pero nunca entra a `datos` — lo sincronizo al guardar:

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: edit**

**Tool: todowrite**

---

## Assistant

Listo:

| Cambio | Verificación |
|---|---|
| **≤5 palabras** en label (`MAX_LABEL_WORDS`) | con rules: 26 regs, 17 logos, 0 unknowns — igual que antes ✅ |
| **Bootstrap** si rules vacío | sin rules: fields auto-detectados (`titular`, `data_de_deposito`, `ncl_11`, ...) ✅ |
| Warning al arrancar sin rules | ✅ |
| Bonus: `pagina_fin` no se escribía al JSON (bug) | corregido en `guardar_registro` ✅ |

Sin `fields_rules.json` ahora sale:
```json
{ "titular": "Aphea.Bio...", "data_de_deposito": "27/03/2026", "ncl_11": "1, 5 e 42", ... }
```
Para renombrar: creas `fields_rules.json` con `key_field` y re-corrés.

---

## User

Perfecto, he pasado algunos archivos a @bk\ por favor actualiza el readme si es necesairo, adicional quiero hacer un nuevo scrip parse_fields, basicamente recibe un archivo especifico, evalua un numero d epaginas y obtiene los fields especificos parseados potenciales usando las mismas reglas de @index.py y crea un archivo con el reporte parsed_fields, listo para copiar y pegar en @fields_rules.json sino este no esta o si se quiere actualizar, evalua un plan

---

## Assistant

**Tool: read**

**Tool: bash**

---

## Assistant

## Contexto verificado

- `bk/` contiene los scripts archivados: `extractor_rpi.py`, `get_coords.py`, `get_text.py`, `index - old.py`
- README no los menciona (la sección estructura ya está limpia) — solo falta añadir `parse_fields` y una nota de `bk/`
- Reglas a reutilizar de `index.py`: `REGEX_LABEL` + `MAX_LABEL_WORDS=5` + `normalizar_clave` + detección de columnas (`detectar_columnas`/`obtener_lineas`)

---

# Plan: `parse_fields.py` + README

## 1. `parse_fields.py` (nuevo, raíz)

### CLI

```bash
python parse_fields.py --file BRTM_1.pdf --pages 100
python parse_fields.py --folder D:\otra --file x.pdf --pages 50
```

| Arg | Default | Descripción |
|---|---|---|
| `--file` | **requerido** | PDF a evaluar (en `--folder` o path absoluto) |
| `--folder` | `docs` | Carpeta del PDF |
| `--pages` | `100` | Nº de páginas a evaluar desde el inicio |

### Lógica (solo lectura del PDF, no escribe `<marca>.json`)

1. Importar de `index.py`: `obtener_lineas`, `detectar_columnas`, `REGEX_LABEL`, `MAX_LABEL_WORDS`, `normalizar_cache`, `cargar_rules`, `CLAVES_ESTRUCTURALES`
2. Para cada página (hasta `--pages`):
   - `obtener_lineas` + encadenar `umbral_prev` (mismo flujo que `index.py`)
   - Líneas con `umbral ≤ x0 < x0_logo` (columna contenido, excluye marca y zona logo)
   - Match `REGEX_LABEL` y ≤5 palabras → candidate label
3. Dedup por `parsed = normalizar_cache(label)`; guardar `raw_field` = primer label visto (con tildes originales)
4. Marcar NCL: si `parsed` matchea `^ncl_\d+$` → colapsar a una sola entrada con `regex`

### Merge con `fields_rules.json` existente

```python
existing, _ = cargar_rules()   # preserva key_field renombrados (fecha_deposito, etc.)
```

- **Ya en rules** → se conserva la entrada tal cual (no pisa tus renombres)
- **Nuevo** → `{"key_field": parsed, "raw_field": raw}` (bootstrap-consistente)
- Si no hay rules → todo es nuevo

### Salida: `parsed_fields.json` (raíz)

```json
{
  "titular": { "key_field": "titular", "raw_field": "Titular" },
  "data_de_deposito": { "key_field": "fecha_deposito", "raw_field": "Data de depósito" },
  "detalhes_do_despacho": { "key_field": "detalhes_do_despacho", "raw_field": "Detalhes do despacho" }
}
```

- Formato **idéntico** a `fields_rules.json` → copiar-pegar o reemplazar directo
- Consola: `Detectados: N | ya en rules: X | nuevos: Y` + lista de nuevos

### No toca

- `fields_rules.json` (solo lectura)
- `output/data/` (no genera registros)

## 2. README

| Sección | Cambio |
|---|---|
| Estructura | agregar `parse_fields.py`, `parsed_fields.json`, nota `bk/` (scripts archivados) |
| Uso | bloque nuevo `parse_fields` con ejemplos |
| Config fields | flujo alternativo: *descubrir fields con `parse_fields` → pegar en `fields_rules.json`* |

## 3. Verificación

```bash
python parse_fields.py --file BRTM_1.pdf --pages 25
# → parsed_fields.json con ≥18 entries; ncl colapsado; sin tocar fields_rules.json
python index.py --file BRTM_1.pdf   # smoke: sin regresiones
```

---

**1 decisión**: el reporte ¿solo los **nuevos** (diff) o el **archivo completo mergeado** (reemplazo directo)? Propongo **completo mergeado** — cumple ambos casos (crear desde cero y actualizar) en un solo archivo. ¿Ok?

---

## User

De hecho, una acotaicon, no deberias saber el key_field, porque no lo sabes, en todo caos por defecto seria el mismo key parsed, recuerda que ese es para el reporte controlado.. se correria evaluando entre un numero d epaginas es decir: start-end, asi limitamos mas yendo directamente a donde se quieren sacar, el scrit solo generaria los potenciales fields con la estructura exacta para crear o actualizar el field rules.. lo pillas?

---

## Assistant

Sí, lo pillo. Corrijo el plan:

---

# Plan revisado: `parse_fields.py`

## Ajustes por tu acotación

| Antes (mal) | Ahora (bien) |
|---|---|
| Merge con `fields_rules.json` existente (presumía `key_field` ajeno) | **No lee** `fields_rules.json` — solo descubre |
| `key_field` = renombre existente | **`key_field` = `parsed`** por defecto (tú lo editas después) |
| `--pages N` desde el inicio | **`--start` / `--end`** — ir directo a la zona de interés |

El reporte es el artefacto **controlado**: tú lo revisas/editas `key_field` y lo pegas en `fields_rules.json`.

## CLI

```bash
python parse_fields.py --file BRTM_2.pdf --start 2300 --end 2400
python parse_fields.py --file BRTM_1.pdf                      # default start=1 end=100
```

| Arg | Default | Descripción |
|---|---|---|
| `--file` | requerido | PDF a evaluar |
| `--folder` | `docs` | Carpeta (o path absoluto en `--file`) |
| `--start` | `1` | Página inicial (1-indexed, como en el PDF) |
| `--end` | `start + 99` | Página final inclusiva |

## Lógica

1. Importar de `index.py`: `obtener_lineas`, `detectar_columnas`, `REGEX_LABEL`, `MAX_LABEL_WORDS`, `normalizar_cache`
2. Recorrer páginas `start..end` (encadenando `umbral_prev`)
3. Líneas en columna contenido (`umbral ≤ x0 < x0_logo`) que matcheen label + ≤5 palabras
4. Dedup por `parsed`; `raw_field` = primer label visto con tildes originales
5. Familia NCL (`ncl_11`, `ncl_12`...) → colapsar a **una** entrada con `"regex": "^ncl_\\d+$"` (consistente con cómo `index.py` la resuelve)

## Salida: `parsed_fields.json` (raíz)

```json
{
  "titular": { "key_field": "titular", "raw_field": "Titular" },
  "data_de_deposito": { "key_field": "data_de_deposito", "raw_field": "Data de depósito" },
  "ncl": { "key_field": "ncl", "raw_field": "NCL", "regex": "^ncl_\\d+$" }
}
```

- **`key_field` = `parsed`** en todos (salvo NCL que va con su regex)
- Estructura idéntica a `fields_rules.json` → crear desde cero o comparar/actualizar manualmente
- Consola: `Páginas X–Y | candidatos: N | nuevos potenciales: ...` (lista de parsed)
- **No escribe** `fields_rules.json` ni `output/data/`

## README

- Estructura: `parse_fields.py`, `parsed_fields.json`, nota `bk/` (scripts archivados)
- Uso: ejemplos con `--start/--end`
- Flujo fields: opción B — *descubrir con `parse_fields` → editar `key_field` → pegar en `fields_rules.json`*

## Verificación

```bash
python parse_fields.py --file BRTM_2.pdf --start 2360 --end 2370
# → parsed_fields.json con estructura exacta, key_field==parsed
python index.py --file BRTM_1.pdf   # smoke sin regresiones
```

---

¿Opción NCL con colapso a `regex` o prefieres entries individuales (`ncl_11`, `ncl_12`...)?

---

## User

en lugar de --start --end que sea: --pages:10,20 por ejemplo sino hay pages, que especifique pages un mensaje

---

## Assistant

# Plan final: `parse_fields.py`

## CLI

```bash
python parse_fields.py --file BRTM_2.pdf --pages 2360,2370
python parse_fields.py --folder D:\otra --file x.pdf --pages 1,50
```

| Arg | Requerido | Descripción |
|---|---|---|
| `--file` | ✅ | PDF a evaluar (en `--folder` o path absoluto) |
| `--folder` | ❌ (default `docs`) | Carpeta del PDF |
| `--pages` | ✅ | Rango `inicio,fin` (1-indexed, inclusivo) |

**Sin `--pages`** → mensaje y exit 1:

```
Debes especificar el rango de páginas: --pages inicio,fin
Ejemplo: --pages 10,20
```

Validaciones: `pages` con exactamente 2 enteros, `inicio ≤ fin`, dentro del rango del PDF.

## Lógica

1. Importar de `index.py`: `obtener_lineas`, `detectar_columnas`, `REGEX_LABEL`, `MAX_LABEL_WORDS`, `normalizar_cache`
2. Recorrer páginas `inicio..fin` (encadenando `umbral_prev`)
3. Líneas columna contenido (`umbral ≤ x0 < x0_logo`) → `REGEX_LABEL` + ≤5 palabras
4. Dedup por `parsed`; `raw_field` = primer label visto (con tildes)
5. Familia `ncl_*` → colapsar a entrada con `"regex": "^ncl_\\d+$"`
6. **No lee** `fields_rules.json` — `key_field` = `parsed` siempre (editas después)

## Salida: `parsed_fields.json` (raíz)

```json
{
  "titular": { "key_field": "titular", "raw_field": "Titular" },
  "data_de_deposito": { "key_field": "data_de_deposito", "raw_field": "Data de depósito" },
  "ncl": { "key_field": "ncl", "raw_field": "NCL", "regex": "^ncl_\\d+$" }
}
```

- Consola: `Páginas 2360–2370 | candidatos: N` + lista de parsed
- **No toca** `fields_rules.json` ni `output/data/`

## README

- Estructura: `parse_fields.py`, `parsed_fields.json`, nota `bk/` (scripts archivados: `extractor_rpi.py`, `get_coords.py`, `get_text.py`, `index - old.py`)
- Uso: ejemplo `--pages 10,20` + aviso de requerido
- Flujo fields: *descubrir con `parse_fields` → editar `key_field` → pegar/actualizar `fields_rules.json`*

## Verificación

```bash
python parse_fields.py --file BRTM_2.pdf --pages 2360,2370   # genera reporte
python parse_fields.py --file BRTM_1.pdf                      # → mensaje de error pages
python index.py --file BRTM_1.pdf                             # smoke sin regresiones
```

---

Pendiente 1 decisión: ¿NCL colapsado a `regex` (como propongo) o entries individuales `ncl_11`, `ncl_12`...?

---

## User

Si, a regex solo NCL, especifica el porque es especial

---

## Assistant

**Tool: todowrite**

---

## Assistant

**Tool: write**

---

## Assistant

**Tool: edit**

**Tool: edit**

**Tool: edit**

---

## Assistant

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: edit**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: todowrite**

---

## Assistant

Listo:

| Check | Resultado |
|---|---|
| `--pages` requerido (sin él → error argparse) | ✅ |
| `--pages abc` → mensaje de formato | ✅ |
| `--pages 99999,...` → rango > PDF | ✅ |
| Archivo inexistente | ✅ |
| NCL colapsado a 1 entrada `regex` | ✅ (`15 entradas` de 16 candidatos) |
| `key_field` = `parsed` | ✅ |
| Smoke `index.py` sin regresiones | ✅ (11 regs) |
| README: `parse_fields`, `bk/`, flujo | ✅ |

**Por qué NCL es especial**: la familia `NCL(11)`, `NCL(12)`, `NCL(13)`... tiene un **número abierto de clases** (1..45+) — listar `ncl_11`, `ncl_12`... sería infinito. El reporte la colapsa a:

```json
"ncl": { "key_field": "ncl", "raw_field": "NCL", "regex": "^ncl_\\d+$" }
```

que `index.py` resuelve por fallback de regex en `resolver_campo`.

```bash
python parse_fields.py --file BRTM_2.pdf --pages 2360,2370
```

---

## User

Es posible que puedas crearme dos archivos de las paginas 10 a la 15 y de la 15 a la 20 de alguno de los archivos de @data? en pdf? 

---

## Assistant

## Plan: extraer 2 PDFs por rango de páginas

**Método**: PyMuPDF `insert_pdf(from_page, to_page)` — rápido, sin re-render.

```python
src = pymupdf.open("docs/BRTM_1.pdf")
# páginas 10–15 (1-indexed → 9..14)
dst.insert_pdf(src, from_page=9, to_page=14)
# páginas 15–20 (1-indexed → 14..19)
dst.insert_pdf(src, from_page=14, to_page=19)
```

**Salida propuesta** (en `docs/` para poder usarlos al toque con `--file`):

| Archivo | Páginas |
|---|---|
| `docs/BRTM_1_p10-15.pdf` | 10–15 |
| `docs/BRTM_1_p15-20.pdf` | 15–20 |

Luego sirven para probar:
```bash
python parse_fields.py --file BRTM_1_p10-15.pdf --pages 1,6
python index.py --file BRTM_1_p15-20.pdf
```

**Notas**:
- `docs/*` está en `.gitignore` (no ensucia git)
- ¿Sobre BRTM_1 (default) o prefieres otro de `docs/` (BRTM_2/3/4)?
- ¿Los dejo en `docs/` o en una carpeta aparte (`samples/`)?

¿Procedo con BRTM_1 en `docs/`?

---

## User

de 1 y 2, simple en /samples

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

Creados en `samples/` (6 págs c/u):

| Archivo | Páginas origen |
|---|---|
| `BRTM_1_p10-15.pdf` | BRTM_1 10–15 |
| `BRTM_1_p15-20.pdf` | BRTM_1 15–20 |
| `BRTM_2_p10-15.pdf` | BRTM_2 10–15 |
| `BRTM_2_p15-20.pdf` | BRTM_2 15–20 |

- `samples/*` agregado a `.gitignore`
- Probado: `parse_fields.py --file samples/BRTM_1_p10-15.pdf --pages 1,6` → 11 candidatos, NCL colapsado ✅

---

## User

Actualmente si por alguna razon en hay un tgitulo field que cumple con la caracteristica en alun bloque de marca peor no esta en field_rules este no se genera en el reporte? Hicimos que sino hay fields rules definidos que detecte automaticamente, pero en este escenario planteado? 

---

## Assistant

**Tool: read**

**Tool: grep**

---

## Assistant

## Respuesta: **sí se genera en ambos reportes** — no hay hueco

Escenario: `fields_rules.json` **existe**, aparece un label que cumple patrón (mayúscula + `:` + ≤5 palabras) pero **no está** en rules.

### `parse_fields.py` → `parsed_fields.json`

**No lee `fields_rules.json` en ningún momento.** Detecta *todo* label que cumpla el patrón en el rango de páginas → siempre entra al reporte, existan rules o no.

```
parse_fields.py → candidatos → parsed_fields.json   (sin consultar rules)
```

### `index.py` → `<marca>.json` vs reporte de unknowns

`resolver_campo` (`index.py:109-112`):

```python
if not rules:          # bootstrap SOLO si rules vacío
    return parsed, parsed, False
return parsed, parsed, True   # ← rules existen + label no está → desconocido
```

| Destino | ¿Va? |
|---|---|
| `suggest.txt` + `fields_unknown.json` (**reporte de unknowns**) | ✅ **sí** |
| `<marca>.json` | ❌ no (tragado hasta re-correr con rules actualizadas) |

El `if not rules` solo decide si el field **entra al JSON de la marca**, no si se **reporta**.

### Resumen

```
rules vacías  → bootstrap → entra a marca.json
rules existen + label nuevo → suggest.txt/fields_unknown.json (reporte) + parsed_fields.json
                             NO entra a marca.json hasta agregarlo a rules
```

**No hay caso en que un label válido pase desapercibido en los reportes.**

¿Querías que en este escenario también entrara a `<marca>.json` (bootstrap parcial para labels nuevos aunque existan rules)? Sería cambiar `if not rules` por aceptar siempre — rompería la separación known/unknown actual.

---

## User

No, pero agreguemos un flag adicional, --strict por defecto, true signific que si esta @fields_rules.json tomara unicamente lo que esta en ahi, pero si es false, entonces tomara lo que esta en @fields_rules.json y adiconal cualquier field que este presente y cumpla.. Lo pillas? Obviamente sino existe el archivo este field no tiene peso alguno porque tomaria todos los fields potenciales.. lo ves?

---

## Assistant

## Plan: flag `--strict` en `index.py`

### Semántica

| Escenario | `--strict true` (default) | `--strict false` |
|---|---|---|
| `fields_rules.json` **existe** | Solo fields de rules → `<marca>.json`; resto → `suggest.txt`/`fields_unknown.json` (**como hoy**) | Fields de rules **+** cualquier label que cumpla patrón (mayúscula, `:`, ≤5 palabras) → `<marca>.json` con `key_field = parsed` si no está en rules |
| `fields_rules.json` **no existe / vacío** | Bootstrap: todos los candidatos (flag sin peso) | Igual — flag sin peso |
| Label **sí** en rules | `key_field` de rules (renombres respetados) | Igual — `key_field` de rules |

### Cambios en `index.py`

**1. argparse** (`main`):
```python
def parse_bool(v): return v.lower() in ("true", "1", "yes", "y")
parser.add_argument("--strict", type=parse_bool, default=True,
    metavar="BOOL",
    help="true: solo fields de fields_rules.json (default); false: rules + labels que cumplan el patrón")
```
→ `procesar_pdf(..., strict=args.strict)`

**2. `resolver_campo`** — única lógica a tocar:
```python
# antes:
if not rules:
    return parsed, parsed, False
return parsed, parsed, True

# después:
if not rules or not strict:
    # rules vacío (bootstrap) O strict=false → aceptar candidato
    return parsed, parsed, False
return parsed, parsed, True
```

- `es_desc=False` → no se registra unknown, va a `set_campo(key_field, valor)`
- En rules → `entry["key_field"]` (renombres intactos); fuera de rules → `key_field = parsed`

**3. AVISO en consola** al arrancar con `--strict false`:
```
AVISO: --strict false — labels fuera de fields_rules.json se aceptan como field (key=parsed)
```

### README

- Uso: ejemplo `python index.py --strict false`
- Sección reglas/bootstrap: tabla con los 2 modos + aclaración de que sin archivo el flag no aplica

### Verificación

```bash
# 1. default → comportamiento idéntico al actual
python index.py --file BRTM_1.pdf   # o smoke 25 págs

# 2. --strict false → algún label fuera de rules entra a marca.json
python index.py --file BRTM_1.pdf --strict false
# verificar que un campo auto-detectado (ej. exame_de_merito, no está en rules)
# aparece en <marca>.json con key_field=parsed

# 3. sin fields_rules.json + cualquier flag → bootstrap igual
```

---

**1 duda**: con `--strict false`, ¿los campos auto-aceptados (fuera de rules) deben seguir apareciendo también en `suggest.txt` como "para agregar a rules" (trazabilidad), o solo ir al JSON y no reportarlos? Propongo **no reportarlos** (ya entraron al JSON; suggest queda para modo strict).

---

## User

Si debe seguir apareciendo en suggest, por que? Para que quede a decision del analista a futuras ejecuciones, donde puede o no aplicar el strict, lo pillas? Porque en realidad no sabria cuales estarian presentes y cuales no como field rules, lo tienes? 

---

## Assistant

Exacto, lo pillo. El ciclo queda así:

### Flujo del analista

```
correr --strict false
  → campos nuevos entran al JSON (key=parsed) Y aparecen en suggest.txt
analista decide cuáles promover a fields_rules.json (con su key_field)
  → re-correr (--strict true o false)
      → los agregados → "known" (usan key_field de rules) y desaparecen de suggest
      → los que no agregó → siguen en suggest
```

`suggest.txt` = **inventario de lo que existe fuera de rules** para decidir a futuro; sin él, en modo `--strict false` el analista no sabría qué está entrando "solo por patrón".

---

# Plan final: `--strict` en `index.py`

## Semántica de `resolver_campo` (3 estados)

```python
def resolver_campo(label, rules, regex_rules=(), strict=True):
    """
    Returns (key_field, parsed, estado):
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
    if not rules or not strict:      # bootstrap O strict=false
        return parsed, parsed, "auto"
    return parsed, parsed, "unknown"
```

## Loop en `procesar_pdf`

```python
key_field, parsed, estado = resolver_campo(label, rules, regex_rules, strict)

if estado == "unknown":
    registrar_unknown(...)              # suggest/fields_unknown
    registro_actual.start_swallow()     # no entra al JSON
else:
    if estado == "auto":
        registrar_unknown(...)          # ← SIEMPRE en suggest (trazabilidad)
    registro_actual.set_campo(key_field, valor)
```

| Estado | Entra a `<marca>.json` | En `suggest.txt` |
|---|---|---|
| `known` | ✅ `key_field` de rules | ❌ |
| `auto` | ✅ `key_field = parsed` | ✅ |
| `unknown` | ❌ (tragado) | ✅ |

**Nota**: bootstrap (sin rules) ahora también llena `suggest.txt` — sirve como borrador inicial de `fields_rules.json` (antes no lo hacía). Coherente con el mismo flujo del analista.

## CLI

```python
parser.add_argument("--strict", type=parse_bool, default=True, metavar="BOOL",
    help="true: solo fields de fields_rules.json (default); "
         "false: rules + labels que cumplan el patrón (auto)")
```

- AVISO en consola si `--strict false`
- `procesar_pdf(..., strict=args.strict)`

## README

- Uso: `python index.py --strict false`
- Sección fields: tabla de 3 estados + flujo del analista (sugerencia → promover a rules → suggest se limpia)

## Verificación

```bash
# 1. default → idéntico al actual (mismos conteos, mismo suggest)
python index.py --file BRTM_1.pdf   # smoke 25 págs

# 2. --strict false → label fuera de rules (ej. exame_de_merito)
#    → aparece en <marca>.json con key=parsed
#    → Y aparece en suggest.txt

# 3. agregar ese campo a fields_rules.json, re-correr --strict false
#    → usa key_field de rules y YA NO aparece en suggest
```

---

¿Procedo a implementar?

---

## User

adelante..implementa

---

## Assistant

**Tool: todowrite**

**Tool: read**

---

## Assistant

**Tool: edit**

**Tool: edit**

**Tool: edit**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: edit**

**Tool: edit**

**Tool: edit**

---

## Assistant

**Tool: edit**

**Tool: edit**

---

## Assistant

**Tool: edit**

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

`samples/` ya no está — lo recreo para el test CLI:

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

`fields_unknown.json` tenía entradas viejas de BRTM_2. Limpio y pruebo limpio:

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: todowrite**

---

## Assistant

Implementado y verificado:

| Escenario | Resultado |
|---|---|
| **default** `--strict true` | Igual que antes: solo fields de rules al JSON, resto → unknown/suggest ✅ |
| **`--strict false`** | Auto-acepta fuera de rules (`key=parsed`) **y** los registra en `suggest.txt` ✅ |
| **Promoción a rules** | Tras agregar `data_de_deposito → fecha_deposito`: usa el rename y **desaparece** de suggest ✅ |
| CLI | `--strict BOOL` en `--help` + AVISO al arrancar con `false` ✅ |
| Bootstrap (sin rules) | Ahora también llena `suggest.txt` (borrador de rules) ✅ |

```bash
python index.py --strict false
```

**3 estados** en `resolver_campo`:

| Estado | JSON | suggest |
|---|---|---|
| `known` | ✅ key de rules | ❌ |
| `auto` | ✅ key=parsed | ✅ |
| `unknown` | ❌ tragado | ✅ |

---

## User

Bien, por ultimo creo que fields_unknown y suggest deberian ir mejor en output, ya que se generan unicamente luego de una ejecucion.. Que opinas? 

---

## Assistant

**Tool: grep**

**Tool: bash**

---

## Assistant

## Opinión: sí, tiene sentido

Son **artefactos de ejecución** (se regeneran en cada run), igual que `<marca>.json`. Argumentos a favor:

1. **Coherencia**: todo lo generado → `output/`
2. **Git**: `.gitignore` ya tiene `output/*` — hoy `fields_unknown.json`/`suggest.txt` en raíz **no** están ignorados (se pueden colar al commit); al moverlos quedan cubiertos automáticamente
3. **Raíz limpia**: solo config fuente (`fields_rules.json`, `index.py`, etc.)

**Detalle**: `cargar_unknown()` los lee al inicio — si no existen, ya devuelve `{}`; solo hay que asegurar que `output/` exista antes de escribir (hoy solo se crea `output/data/`).

---

# Plan: mover a `output/`

## Cambios en `index.py`

```python
# antes
UNKNOWN_PATH = "fields_unknown.json"
SUGGEST_PATH = "suggest.txt"

# después
UNKNOWN_PATH = os.path.join("output", "fields_unknown.json")
SUGGEST_PATH = os.path.join("output", "suggest.txt")
```

- `main()`: crear `output/` además de `output/data/`:
  ```python
  os.makedirs("output", exist_ok=True)
  os.makedirs(OUTPUT_DIR, exist_ok=True)
  ```
- Resto de lógica (`cargar_unknown`, `escribir_unknown_y_suggest`) intacta — solo cambian las constantes de path

## Mover archivos existentes (si los hay)

- `fields_unknown.json`, `suggest.txt` de raíz → `output/` (o borrarlos, se regeneran en el próximo run)

## README

- Estructura del proyecto: `fields_unknown.json` y `suggest.txt` → `output/...`
- Referencias a `suggest.txt` en flujo/estados → `output/suggest.txt`

## Verificación

```bash
python index.py --folder samples --file BRTM_1_p10-15.pdf --strict false
# → output/fields_unknown.json + output/suggest.txt creados
# → nada nuevo en raíz
```

---

**1 pregunta**: `parsed_fields.json` (de `parse_fields.py`) también es generado — ¿lo movemos también a `output/` en el mismo cambio, o se queda en raíz?

---

## User

No parse fields si queda como esta

---

## Assistant

**Tool: edit**

**Tool: grep**

---

## Assistant

**Tool: read**

---

## Assistant

**Tool: edit**

**Tool: bash**

---

## Assistant

Archivos ya no estaban en raíz (se borraron en tests). Actualizo README:

**Tool: edit**

**Tool: grep**

---

## Assistant

**Tool: edit**

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

Listo:

| Check | Resultado |
|---|---|
| `UNKNOWN_PATH` / `SUGGEST_PATH` → `output/` | ✅ |
| `os.makedirs("output")` en `main` | ✅ |
| Escritura en `output/` (nada en raíz) | ✅ |
| `cargar_unknown()` lee del nuevo path | ✅ (10 entries) |
| `parsed_fields.json` sigue en raíz | ✅ |
| README estructura + flujo actualizados | ✅ |

---


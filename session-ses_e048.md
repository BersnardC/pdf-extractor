# Extracción RPI con coords dinámicas y JSON

**Session ID:** ses_e048d6c80ffeNTvZdfhdPyeY8z
**Created:** 20/11/2026, 8:12:32 p.m.
**Updated:** 20/11/2026, 9:30:27 p.m.

---

## User

Los archivos en @docs\ son archivos de marcas de RPI brasil, donde se dispone la informacion de las marcas.. (No cargues los archivos porque pesan demasiado), yo he estructurdo ya 3 archivos con pymupdf, donde en @get_text.py evaluo la data y txtx por pagina, en @get_coords.py evaluo desde que coordenadas empieza texto en cada pagina y en @extractor_rpi.py extraigo la informacio y genero un json de ejemplon, no obstante las coordenadas x estan fijas, necesito poder extraerlas segun el @get_coords.py .. Por ello debo en @index.py elaborar un script simple a partir de los actuales, donde evalue los archivos uno por uno en @docs\ (aunque en primera instancia solo el @docs/BRTM_1.pdf) las fases son, leer el contenido, que QUÉ DEBE GENERAR
output/
   data/<marca>.json
   data/<marca>.png

- <marca> es el número de proceso del registro.
- El .json contiene los datos del registro. Por ejemplo:
   { "marca": "501546447", "fecha_publicacion": "10/11/2026", "titular": "...", ... } tal com en @extractor_rpi.py, algunas secciones de contenido pueden tener Publicação de pedido de registro para oposição (exame formal concluído)
Titular: GABRIEL SILVA CARVALHO [BR/MG]
Data de depósito: 22/10/2026
Apresentação: Mista
Natureza: Marca de Produto/Serviço
Elemento nominativo: Key2Go
CFE: 27.5.1, 27.5.9, 27.7.1 e 29.1.4
NCL(13): 42
Especificação: ATUALIZAÇÃO DE SOFTWARE DE
COMPUTADOR;DESENVOLVIMENTO DE PLATAFORMAS DE
COMPUTADOR;ELABORAÇÃO [CONCEPÇÃO] DE SOFTWARE DE
COMPUTADOR;MANUTENÇÃO DE SOFTWARE DE COMPUTADOR;PLATAFORMA
COMPUTACIONAL COMO SERVIÇO [PAAS];PROGRAMAÇÃO DE COMPUTADOR
[INFORMÁTICA];PROVIMENTO DE SOFTWARE DE COMPUTADOR ON-LINE NÃO
BAIXÁVEL;SOFTWARE COMO SERVIÇO [SAAS] (DA CLASSE 42) el json quiero evaluarlo de la misma forma normalizando elementos conocidos, por ejemplo basandome en @reglas_campos.json con un ligera funcion def normalizar_clave(texto):
    """Elimina tildes/cedillas y convierte a snake_case limpio."""
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-zA-Z0-9]+", "_", sin_tildes.lower()).strip("_") si el elemento del renglon de marcas es Texto titulo: pasa a texto_titulo? Elaboremos un plan

---

## Assistant

Voy a investigar la estructura del PDF y las coordenadas para elaborar un plan sólido. Primero exploro el proyecto y inspecciono las coordenadas (solo lectura).

**Tool: bash**

**Tool: bash**

---

## Assistant

Los PDFs son pesados (50-100MB). Voy a inspeccionar solo algunas páginas para entender la estructura de coordenadas.

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

Los bloques se mezclan. Voy a inspeccionar con más detalle usando `lines`/`dict` para entender la estructura real.

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

Ahora entiendo mejor la estructura. Voy a examinar más páginas para ver los inicios de registro y la columna izquierda.

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: bash**

**Tool: bash**

---

## Assistant

Tengo una visión clara. Verifico un par de detalles más sobre textos laterales y continuidad entre páginas.

**Tool: bash**

**Tool: bash**

---

## Assistant

Tengo una imagen clara de la estructura. Antes de presentar el plan, necesito aclarar algunos puntos:

**Tool: question**

---

## Assistant

Tengo todo lo necesario. Aquí está el plan:

---

## Plan: `index.py` — Extractor RPI con coordenadas X dinámicas

### Contexto verificado

| Elemento | Hallazgo |
|---|---|
| Encabezado | `MARCAS - RPI 2914 de 10/11/2026` en x0≈56.7, y0≈34 |
| N° proceso (marca) | 9 dígitos en x0≈69.5 |
| Columna de contenido | etiquetas `Titular:`, etc. en x0≈133.7 |
| Texto logo (zona der.) | x0>430 (`StarNote`, `AXIOAERO GROUP`) → campo `text_logo` |
| `get_text("blocks")` | **mezcla** marca + contenido en un solo bloque → usar `get_text("dict")` a nivel de **línea** |
| Registros multi-página | Un registro puede empezar en pág N y continuar en N+1 (ej. 501528691) |
| Labels vistos | Titular, Data de depósito, Data de recebimento pelo INPI, Número da Inscrição Internacional, Apresentação, Natureza, Elemento nominativo, CFE, NCL(11/13), Especificação, Especificação traduzida, Prioridade unionista, Procurador |
| Estado | `Publicação de pedido de registro para oposição (exame formal concluído)` o `...de designação concluído)` |

### Decisiones del usuario

1. **NCL(11)/NCL(13)** → clave siempre `ncl`
2. **Línea de estado** → campo `estado` en el JSON
3. **Textos zona derecha** → campo `text_logo` (logos mixtos de Brasil)
4. **Detección X dinámica** → por líneas etiquetadas

### Arquitectura de `index.py`

Script único, autocontenido, basado en la lógica de `extractor_rpi.py` + `get_coords.py`:

```
index.py
├── normalizar_clave(texto)          # tildes/cedillas → snake_case
├── cargar_reglas()                  # lee reglas_campos.json
├── detectar_columnas(lineas_pag)    # X dinámica → (umbral, x0_logo)
├── extraer_fecha_pub(doc)           # "RPI NNNN de DD/MM/AAAA"
├── procesar_pdf(ruta_pdf, out_dir)  # bucle principal por página
│   ├── por línea (get_text "dict"):
│   │   ├── ^\d{9}$ y x0<umbral  → nueva marca (guarda la anterior)
│   │   ├── x0>=umbral y <x0_logo → acumula contenido (label + multilinea)
│   │   ├── x0>=x0_logo           → acumula text_logo
│   │   └── y0<50                 → ignora (encabezado)
│   ├── parsea contenido → dict con claves normalizadas
│   ├── asocia imágenes por posición vertical → <marca>.png
│   └── guarda <marca>.json
└── main()                          # itera docs/*.pdf (empieza con BRTM_1)
```

### Detección dinámica de X (reemplaza `UMBRAL_COLUMNA_X=135`)

Por página (o en primer barrido del PDF):

1. **x0_marca** = x0 de líneas que matchean `^\d{9}$` (típ. 69.5)
2. **x0_contenido** = x0 de líneas con patrón `^[A-ZÁÉÍÓÚÑ][\w\s./()]*:` (típ. 133.7)
3. **x0_logo** = x0 mínimo de líneas con x0 > x0_contenido + 200 (típ. 441) — o fallback `ancho_pagina * 0.72`
4. **umbral** = `(x0_marca + x0_contenido) / 2` (típ. ≈101.6)

Clasificación por línea: `x0 < umbral` → columna izq.; `umbral ≤ x0 < x0_logo` → contenido; `x0 ≥ x0_logo` → text_logo.

### Normalización de claves

```python
def normalizar_clave(texto):
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto)
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-zA-Z0-9]+", "_", sin_tildes.lower()).strip("_")
```

Flujo por campo:
1. Extraer label del renglón (parte antes de `:`)
2. `normalizar_clave(label)` → ej. `"data_de_deposito"`
3. Buscar en `reglas_campos.json["campos_conocidos"]` → `"fecha_deposito"`
4. Si no está en reglas → usar el resultado de `normalizar_clave` como clave
5. **Excepción NCL**: `NCL(11)`/`NCL(13)` → regex special-case → `"ncl"`
6. `Texto titulo` → `texto_titulo` (confirmado: así funciona `normalizar_clave`)

Valores multilínea (ej. `Especificación:`) se concatenan hasta el siguiente label o nueva marca.

### Estructura de salida

```
output/
├── data/
│   ├── 501682642.json
│   ├── 501682642.png
│   └── ...
```

Ejemplo de JSON:

```json
{
  "marca": "501682642",
  "fecha_publicacion": "10/11/2026",
  "pagina_pdf": 21,
  "estado": "Publicação de pedido de registro para oposição (exame formal de designação concluído)",
  "titular": "Xuzhou JingAn Heavy Industry Manufacture Co., Ltd. [CN]",
  "fecha_deposito": "18/03/2026",
  "fecha_recepcion_inpi": "23/04/2026",
  "inscripcion_internacional": "1682642",
  "presentacion": "Mista",
  "naturaleza": "Madri Produto/Serviço",
  "elemento_nominativo": "JA",
  "clasificacion_viena": "27.5.1 e 28.3.0",
  "ncl": "7",
  "especificacion": "AGITATORS; MIXING MACHINES; ...",
  "especificacion_traducida": "Agitadores; máquinas misturadoras; ...",
  "text_logo": "StarNote",
  "tiene_logo": true
}
```

### Manejo de casos especiales

- **Registro multi-página**: se mantiene `registro_actual` abierto entre páginas hasta encontrar el siguiente `^\d{9}$`
- **Encabezado/pie**: `y0 < 50` o `y0 > alto-40` → ignorar
- **Intro legal** (pág. 10, "Publicam-se os pedidos..."): x0=56.7 pero no matchea `^\d{9}$` → se ignora por no ser marca
- **Imágenes**: mismo criterio de `extractor_rpi.py` (asociar por posición vertical entre marcas), convertir a RGB si hace falta
- **Encoding**: PDFs con caracteres latinos rotos (`o` vs `ó`) — PyMuPDF ya maneja la extracción; se usa `ensure_ascii=False` al guardar

### Orden de implementación

1. Escribir `index.py` completo (funciones auxiliares + `procesar_pdf` + `main`)
2. Ejecutar solo contra `docs/BRTM_1.pdf`
3. Verificar: ~N JSONs generados, claves normalizadas correctas, `ncl` unificado, `estado` presente, logos PNG
4. Si todo OK → habilitar iteración sobre los 4 PDFs

### Punto de verificación

```bash
python index.py   # procesa BRTM_1.pdf primero
# revisar output/data/501682642.json y .png como muestra
```

---

¿Procedo con la implementación siguiendo este plan?

---

## User

Correcto, importante, 3 acalaratorias.. El registro puede ocupar varias paginas debido a las Especificaciones o Especificaciones traducida, algoa asi Especificação: PLANT GROWTH REGULATING PREPARATIONS; PLANT GROWING
MEDIA; FERTILIZERS; PLANT FOOD; MANURES. (DA CLASSE 1), FUNGICIDES,
HERBICIDES, INSECTICIDES, PREPARATIONS FOR DESTROYING VERMIN,
PARASITICIDES, BIOCIDES. (DA CLASSE 5) E RESEARCH AND DEVELOPMENT
SERVICES IN THE FIELD OF AGRICULTURAL BIOLOGICALS; 'PLATFORM AS A
SERVICE' SERVICES IN THE FIELD OF RESEARCH AND DEVELOPMENT donde esa data puede ocupar varias paginas adicionales.. los ncl pueden ser varios, es decir 12, 11, x,x,x.. y lo otro muy importante, aunque estamos normalizando y esquematizando los campos Cuando encuentre campos o bloques que no reconoce, debe detectarlo y reportarlo (no ignorarlo ni inventarlo), y ofrecer una forma de resolver el fallo y volver a correr. 

---

## Assistant

Actualizo el plan con las 3 aclaraciones:

---

## Plan actualizado: `index.py`

### 1. Registros multi-página (Especificación / Especificación traducida)

- `registro_actual` **no se cierra al cambiar de página** — solo se cierra al encontrar el siguiente `^\d{9}$` (nueva marca) o al terminar el PDF.
- Líneas de continuación sin label (x0 en columna de contenido, sin `Etiqueta:`) → **se anexan al último campo abierto** de `registro_actual` (puede ser `especificacion` o `especificacion_traducida` que cruza páginas).
- `pagina_pdf` = página **donde inicia** el registro; opcional `pagina_fin` = última página del registro.
- Al guardar, si el último campo sigue abierto al terminar el PDF → se guarda lo acumulado (y se reporta en el log si el registro quedó incompleto por corte de PDF).

### 2. NCL múltiple

- Valor se guarda como **string** con los números tal cual (ej. `"9, 12, 37 e 42"`).
- Si en un mismo registro aparecen **varias etiquetas NCL** (`NCL(11)`, `NCL(13)`, etc.):
  - Todas mapean a clave `ncl`.
  - Si `ncl` ya existe → se convierte en **lista** (ej. `["9, 12, 37", "42"]`) o se concatenan con `"; "` — implementar como lista para no perder origen.
- Regex de detección: `^NCL\(\d+\):` → clave `ncl`.

### 3. Detección y reporte de campos desconocidos (no ignorar, no inventar)

Mecanismo en 3 niveles:

**A. En cada JSON** — los campos no mapeados se conservan con su label original normalizada, sin inventar nombre canónico:
```json
{
  "titular": "...",
  "campos_desconocidos": {
    "texto_titulo": "Mi Marca",
    "outro_campo": "valor"
  }
}
```
- Si `campos_desconocidos` está vacío → no se incluye la clave.
- Así **no se ignora ni se inventa** el dato.

**B. Reporte agregado** — `output/reportes/desconocidos.json`:
```json
{
  "fecha_ejecucion": "...",
  "pdf_procesado": "BRTM_1.pdf",
  "campos": [
    {
      "label_original": "Texto titulo",
      "clave_normalizada": "texto_titulo",
      "apariciones": 12,
      "ejemplo_valor": "Mi Marca",
      "ejemplo_marca": "501682642",
      "ejemplo_pagina": 21
    }
  ],
  "bloques_sin_label": [
    { "marca": "501527708", "pagina": 10, "texto_ejemplo": "...", "x0": 133.7 }
  ]
}
```
- `campos`: líneas con `Etiqueta: valor` cuya clave normalizada **no está** en `reglas_campos.json` ni en el set de claves conocidas del script (`ncl`, `estado`, `marca`, etc.).
- `bloques_sin_label`: líneas de contenido que no matchean patrón de label ni son continuación clara (texto "huérfano").

**C. Flujo de resolución y re-ejecución**:
1. Correr `python index.py` → genera JSONs + `reportes/desconocidos.json`.
2. Revisar el reporte → decidir por cada campo:
   - **Mapear**: agregar en `reglas_campos.json` → `"texto_titulo": "titulo_grafico"` (o la clave que corresponda).
   - **Aceptar como desconocido con su clave normalizada**: agregar a un `CAMPOS_CONOCIDOS_ADICIONALES` en `index.py` para que salga del reporte pero siga en `campos_desconocidos` del JSON… o mejor: si no se mapea, permanece en `campos_desconocidos` (decisión documentada en el reporte).
   - **Corregir parseo**: si es falso positivo (continuación mal detectada), ajustar regex/umbral en `index.py`.
3. Re-ejecutar → los JSONs se sobrescriben y el reporte se regenera sin esos campos.
4. **Modo estricto** `--estricto`: si hay desconocidos → imprime resumen y sale con código distinto de 0 (para CI/validación). Por defecto no-estricto: completa la corrida y deja el reporte.

### Estructura final de `index.py`

```
index.py
├── normalizar_clave(texto)
├── cargar_reglas() → dict
├── CLAVES_CONOCIDAS = {ncl, estado, marca, fecha_publicacion, ...}
├── detectar_columnas(lineas) → (umbral, x0_logo)   # X dinámica
├── parsear_contenido(lineas, reglas) → (campos, desconocidos, ultimo_campo)
├── extraer_fecha_pub(doc)
├── procesar_pdf(ruta, out_dir, estricto=False)
│   ├── estado: registro_actual, ultimo_campo, campos, desconocidos
│   ├── por línea:
│   │   ├── ^\d{9}$ + x0<umbral → guarda anterior, inicia nuevo
│   │   ├── x0≥umbral + label   → nuevo campo (o merge ncl)
│   │   ├── x0≥umbral sin label → anexa a ultimo_campo (multi-pág)
│   │   ├── x0≥x0_logo          → text_logo
│   │   └── y0<50               → ignora encabezado
│   ├── imágenes por y → <marca>.png
│   ├── guarda <marca>.json (con campos_desconocidos si hay)
│   └── acumula para reporte
├── escribir_reporte(desconocidos)
└── main()  # --pdf BRTM_1.pdf | --todos | --estricto
```

### Ejemplo de ejecución

```bash
# Primera corrida (solo BRTM_1)
python index.py --pdf docs/BRTM_1.pdf

# Revisar:
#   output/data/*.json, *.png
#   output/reportes/desconocidos.json

# Resolver: agregar mapeos en reglas_campos.json si aplica
# Re-ejecutar:
python index.py --pdf docs/BRTM_1.pdf

# Validación estricta:
python index.py --pdf docs/BRTM_1.pdf --estricto
```

### Verificación

1. Contar marcas en BRTM_1 vs JSONs generados (deben coincidir).
2. Muestra: `501528691` (cruza pág. 10→11) → `especificacion` completo.
3. `501682642` → `ncl: "7"`, `estado` presente, `text_logo` si hay.
4. Buscar `campos_desconocidos` en todos los JSONs y cruzar con el reporte.
5. Re-ejecutar tras tocar `reglas_campos.json` → reporte se limpia.

---

¿Hay algo que ajustar o procedo con la implementación?

---

## User

No necesitamos pasar --pdf, todos son pdf.. tampoco necesito que el archivo reejecuta solo, solo necesito las recomendaciones para ejecutar manualmente 

---

## Assistant

Plan final simplificado:

---

## Plan final: `index.py`

### Comportamiento

- Sin argumentos CLI: procesa **todos** los `docs/*.pdf` en orden (`BRTM_1` → `BRTM_4`).
- Genera `output/data/<marca>.json` + `<marca>.png` y `output/reportes/desconocidos.json`.
- Reporte de campos desconocidos para **revisión manual**; tú decides si actualizar `reglas_campos.json` y **vuelves a correr `python index.py` a mano**.

### Lógica clave (resumen)

1. **X dinámica** por líneas etiquetadas: `x0` de `^\d{9}$` (marca) y `x0` de `Etiqueta:` (contenido); umbral = punto medio; `x0_logo` = zona derecha → `text_logo`.
2. **Líneas** via `get_text("dict")` (no `blocks`, que mezcla columnas).
3. **Registro multi-página**: se cierra solo al ver siguiente marca o fin de PDF; líneas sin label se anexan al último campo (`especificacion` etc.).
4. **NCL**: todas las variantes → clave `ncl`; si varias en un registro → lista.
5. **Estado** → campo `estado`.
6. **Desconocidos**: label sin mapeo en `reglas_campos.json` ni en claves conocidas → va a `campos_desconocidos` en el JSON **y** al reporte (con valor de ejemplo, marca, página). No se ignora ni se inventa nombre.

### Estructura de salida

```
output/
├── data/
│   ├── 501682642.json
│   ├── 501682642.png
│   └── ...
└── reportes/
    └── desconocidos.json
```

### Ejecución manual (recomendaciones)

```bash
# 1. Correr
python index.py

# 2. Revisar muestra
#    output/data/501682642.json  → claves, ncl, estado, campos_desconocidos
#    output/data/501682642.png   → logo

# 3. Revisar reporte
#    output/reportes/desconocidos.json

# 4. Si hay campos desconocidos que mapear:
#    editar reglas_campos.json  (ej. "texto_titulo": "titulo_grafico")

# 5. Volver a correr a mano para regenerar
python index.py
```

### Verificación

- Nº de marcas detectadas en BRTM_1 ≈ Nº de JSONs generados.
- Registro que cruza páginas (ej. `501528691`, pág. 10→11): `especificacion` completo.
- `ncl` unificado; `estado` presente; `text_logo` solo si hay texto en zona de logo.
- Todo label no mapeado aparece en `campos_desconocidos` + reporte.

---

¿Procedo a implementar `index.py`?

---

## User

correcto, adelante

---

## Assistant

**Tool: todowrite**

---

## Assistant

**Tool: write**

---

## Assistant

Ahora ejecuto contra BRTM_1 primero para validar. Primero ajusto para procesar solo BRTM_1 en la prueba:

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

El archivo de reglas fue renombrado. Uso `reglas_campos-old.json`:

**Tool: read**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

El PDF tiene 8067 páginas; tarda. Primero valido con un rango reducido:

**Tool: bash**

---

## Assistant

**Tool: write**

---

## Assistant

**Tool: bash**

---

## Assistant

Prueba OK: 38 registros, 18 logos. Reviso la calidad de la salida:

**Tool: bash**

**Tool: read**

---

## Assistant

Veo problemas: la línea de estado cae como "sin label" en vez de `estado`. Reviso un JSON de muestra:

**Tool: read**

**Tool: read**

**Tool: bash**

---

## Assistant

Detecté 2 bugs:
1. `NCL(11)` no matchea el regex de label (faltan dígitos) → se anexa a `clasificacion_viena`
2. La línea de estado no se captura como `estado`

Los corrijo:

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

Limpio la salida de pruebas y relanzo:

**Tool: bash**

---

## Assistant

**Tool: read**

**Tool: bash**

---

## Assistant

`ncl` corregido. Falta `estado`: `_prueba.py` tiene lógica propia desactualizada. Añado `max_pag` a `index.procesar_pdf` y pruebo con él:

**Tool: read**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

`bloques_sin_label` bajó de 39 a 6. Verifico:

**Tool: read**

**Tool: bash**

**Tool: bash**

---

## Assistant

Casi todo OK. Mejoro: las continuaciones de campos desconocidos (`detalhes_do_despacho`) se pierden → deben anexarse al campo desconocido:

**Tool: read**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

Excelente: 0 bloques sin label, 38/38 con `estado`. Verifico registros multi-página y desconocidos:

**Tool: bash**

**Tool: read**

---

## Assistant

**Tool: bash**

---

## Assistant

Verifico un registro que sabemos cruza páginas (501528691, pág. 10→11):

**Tool: read**

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

**Tool: bash**

---

## Assistant

Faltan las marcas de la página 10. Depuro la detección de columnas en esa página:

**Tool: bash**

---

## Assistant

Encontré el bug: en la pág. 10 la línea intro `"Para apresentar oposição..."` (x0=56.7) matchea como label y arruina el umbral. Corrijo `detectar_columnas` para filtrar labels en la columna izquierda:

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

Ajusto el umbral para que quede cerca de la columna de contenido (descarta líneas intro intermedias):

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

44 registros incluyendo pág. 10. Verifico el multi-página 501528691 (cruza 10→11):

**Tool: read**

**Tool: bash**

---

## Assistant

El multi-página 501528691 está completo. Reviso el caso `Exigência de pagamento`:

**Tool: read**

---

## Assistant

`Exigência de pagamento` queda reportado como `sin_label` (comportamiento deseado: detectar, no ignorar). Limpio el script de prueba y hago la validación final:

**Tool: bash**

**Tool: bash**

---

## Assistant

**Tool: todowrite**

---

## Assistant

`index.py` implementado y validado con las primeras 40 páginas de `BRTM_1.pdf`.

## Resultados de la prueba (40 págs)

| Métrica | Valor |
|---|---|
| Registros JSON | 44 |
| Con `estado` | 44/44 |
| Con `ncl` | 35 |
| Con `text_logo` | 14 |
| Logos PNG | 19 |
| Campos desconocidos reportados | 2 tipos (`detalhes_do_despacho`, `duas_etapas`) |
| Bloques sin label | 1 (`Exigência de pagamento` → reportado) |

## Casos verificados

- **Multi-página**: `501528691` (pág. 10→11) → `especificacion` + `especificacion_traducida` completos
- **NCL**: `"ncl": "9, 12, 37 e 42"`; lista cuando hay varios (`['1, 5 e 42', '9, 12, 37 e 42']`)
- **X dinámica**: umbral detectado por líneas etiquetadas (falla de la pág. 10 con intro legal corregida)
- **Desconocidos**: van a `campos_desconocidos` en el JSON + `output/reportes/desconocidos.json`

## Correcciones aplicadas durante la prueba

1. Regex de label incluía dígitos → `NCL(11)` ya no se pega a `clasificacion_viena`
2. Línea `Publicação...` → campo `estado`
3. Continuaciones de campos desconocidos se anexan (no se pierden)
4. Umbral = `x0_contenido - 25` para descartar líneas intro intermedias

## Para correr completo (manual)

```bash
python index.py
```

Procesa los 4 PDFs de `docs/` → `output/data/*.json` + `*.png` + `output/reportes/desconocidos.json`. Tras revisar el reporte, actualiza `reglas_campos.json` si aplica y vuelve a correr.

---

## User

Perfecto, necesito modificques para que por defecto corra todos, pero tambien poder pasarle --file File y que ejecute solo ese en lugar de todos.. 

---

## Assistant

**Tool: read**

---

## Assistant

## Plan: añadir `--file` a `index.py`

Cambio mínimo en `main()` (index.py:434) usando `argparse`:

### Uso resultante

```bash
python index.py                      # todos los PDFs de docs/ (como ahora)
python index.py --file BRTM_1.pdf    # solo ese archivo
python index.py --file BRTM_3.pdf    # solo ese
```

### Cambio en `main()`

1. Importar `argparse` (arriba del archivo).
2. Al inicio de `main()`:
   ```python
   parser = argparse.ArgumentParser(...)
   parser.add_argument("--file", help="Procesar solo este PDF de docs/")
   args = parser.parse_args()
   ```
3. Selección de PDFs:
   - Sin `--file` → actual: todos los `.pdf` de `docs/` ordenados.
   - Con `--file BRTM_1.pdf` → lista solo ese nombre (acepta con o sin ruta; se usa `os.path.basename` y se busca en `DOCS_DIR`). Si no existe → mensaje de error y salir.
4. El resto del flujo (procesar, reporte, totales) queda igual.

### Detalle

- `--file` acepta `BRTM_1.pdf` o `docs/BRTM_1.pdf` (normaliza con `basename`).
- Validación: si el archivo no está en `docs/` → imprime `No existe docs/<file>` y sale con código 1.

¿Procedo?

---

## User

Perfcto, adelante

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: edit**

---

## Assistant

**Tool: bash**

---

## Assistant

`--help` y validación de archivo inexistente OK. Verifico la selección de archivo con una corrida parcial:

**Tool: bash**

---

## Assistant

Listo. Cambios en `index.py`:

```bash
python index.py                      # todos los PDFs de docs/
python index.py --file BRTM_1.pdf    # solo ese
python index.py --file docs/BRTM_3.pdf  # acepta ruta completa también
```

- Archivo inexistente → `No existe docs\<file>` y exit code 1.
- `--help` muestra el uso.

---


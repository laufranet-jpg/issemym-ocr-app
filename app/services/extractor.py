import re
import fitz

# ── patrones ──────────────────────────────────────────────────────────────────
_FECHA       = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
_RFC_CURP    = re.compile(r"\b[A-ZÑ&]{4,6}\d{6}[A-Z0-9]{0,8}\b")
_CLAVE_NUM   = re.compile(r"^\d{4,10}$")
_SOLO_MAYUS  = re.compile(r"^[A-ZÁÉÍÓÚÜÑ0-9 /.,()-]+$")
_PALABRAS_DESCARTE = {
    "CLAVE ISSEMYM", "SERVIDOR PUBLICO", "INSTITUCION PUBLICA",
    "GOBIERNO DEL", "ESTADO DE MEXICO", "ESTADO DE MÉXICO", "ISSEMYM",
    "AVISO DE MOVIMIENTO PARA LA AFILIACION Y VIGENCIA DE DERECHOS",
    "AVISO DE MOVIMIENTO PARA LA AFILIACIÓN Y VIGENCIA DE DERECHOS",
}
_INST_CLAVES = [
    "GEM", "INSTITUCION", "DIRECCION", "DIRECCIÓN", "EDUCACION",
    "EDUCACIÓN", "SECRETARIA", "SECRETARÍA", "AYUNTAMIENTO",
]


def _limpiar_lineas(texto: str) -> list[str]:
    lineas = []
    for ln in texto.splitlines():
        x = re.sub(r"\s+", " ", ln).strip()
        if x:
            lineas.append(x)
    return lineas


def _es_nombre(s: str) -> bool:
    if len(s) < 8 or not _SOLO_MAYUS.match(s):
        return False
    if s in _PALABRAS_DESCARTE:
        return False
    palabras = s.split()
    return len(palabras) >= 2 and all(len(p) > 1 for p in palabras)


def _es_institucion(s: str) -> bool:
    return len(s) >= 8 and any(k in s for k in _INST_CLAVES)


def extract_fields_from_lines(lineas: list[str]) -> dict:
    """Extrae campos a partir de líneas de texto nativo (PyMuPDF)."""
    texto_join = "\n".join(lineas)

    fechas = _FECHA.findall(texto_join)
    fecha_movimiento = fechas[0] if len(fechas) >= 1 else None
    fecha_emision    = fechas[1] if len(fechas) >= 2 else None

    # RFC/CURP
    rfc_val = None
    idx_rfc = -1
    for i, ln in enumerate(lineas):
        m = _RFC_CURP.search(ln)
        if m:
            cand = m.group(0)
            if not cand.startswith(("ALTA", "BAJA", "ULAD", "TTPO", "TIA", "CLAV", "NOMB")):
                rfc_val = cand
                idx_rfc = i
                break

    # Clave ISSEMYM (número antes del RFC)
    clave_issemym = None
    if idx_rfc > 0:
        for j in range(max(0, idx_rfc - 4), idx_rfc):
            cand = lineas[j].replace(" ", "")
            if _CLAVE_NUM.match(cand):
                clave_issemym = cand
                break
    if not clave_issemym:
        nums = [ln.replace(" ", "") for ln in lineas if _CLAVE_NUM.match(ln.replace(" ", ""))]
        if nums:
            clave_issemym = nums[0]

    # Tipo de movimiento
    tipo = None
    for ln in lineas:
        if ln.strip() in {"ALTA", "BAJA", "REINGRESO", "MODIFICACION", "MODIFICACIÓN", "CAMBIO"}:
            tipo = ln.strip()
            break

    # Nombre completo (línea después del RFC)
    nombre = None
    if idx_rfc >= 0:
        for j in range(idx_rfc + 1, min(len(lineas), idx_rfc + 6)):
            ln = lineas[j]
            if _es_nombre(ln) and not _es_institucion(ln):
                nombre = ln
                break

    # Institución y clave institución
    # El orden en el PDF puede ser: nombre → institución → clave_inst → nombramiento
    # O bien:                        nombre → clave_inst → institución → nombramiento
    # Buscamos clave_inst y luego buscamos institución tanto antes como después de ella.
    _SKIP_INST = {"SERVIDOR PUBLICO", "INSTITUCION PUBLICA", "CLAVE ISSEMYM"}
    clave_inst = None
    institucion = None
    idx_clave_inst = -1
    if nombre and nombre in lineas:
        idx_nombre = lineas.index(nombre)
        for j in range(idx_nombre + 1, min(len(lineas), idx_nombre + 10)):
            cand = lineas[j].replace(" ", "")
            if _CLAVE_NUM.match(cand) and cand != clave_issemym:
                clave_inst = cand
                idx_clave_inst = j
                break

        if idx_clave_inst >= 0:
            # Buscar institución con keyword primero (antes o después de clave_inst)
            window = list(range(idx_nombre + 1, min(len(lineas), idx_clave_inst + 6)))
            for k in window:
                if lineas[k] not in _SKIP_INST and _es_institucion(lineas[k]):
                    institucion = lineas[k]
                    break
            # Fallback: nombre-like que no sea un nombramiento conocido
            if not institucion:
                for k in window:
                    ln = lineas[k]
                    if ln in _SKIP_INST or ln.replace(" ", "") == clave_inst:
                        continue
                    if _es_nombre(ln) and not _es_institucion(ln):
                        # Descartamos líneas cortas que parecen nombramientos
                        if len(ln.split()) >= 3 or (len(ln) > 20 and len(ln.split()) >= 2):
                            institucion = ln
                            break

    # Nombramiento — puede venir con fecha pegada al final, ej: "ORIENTADOR TECNICO   18/06/2021"
    nombramiento = None
    _SKIP_NOM = {"SERVIDOR PUBLICO", "INSTITUCION PUBLICA", "CLAVE ISSEMYM"}
    # El nombramiento está después de AMBOS: institución y clave_inst
    idx_anchor = max(
        lineas.index(institucion) if (institucion and institucion in lineas) else -1,
        idx_clave_inst,
    )
    if idx_anchor >= 0:
        for j in range(idx_anchor + 1, min(len(lineas), idx_anchor + 5)):
            ln = lineas[j]
            if ln in _SKIP_NOM:
                continue
            ln_clean = ln.replace(" ", "")
            if _CLAVE_NUM.match(ln_clean):
                continue
            # Quita fecha pegada al final y toma lo que quede
            sin_fecha = _FECHA.sub("", ln).strip()
            if len(sin_fecha) >= 5:
                nombramiento = sin_fecha
                break

    return {
        "tipo_movimiento":          tipo,
        "a_partir_de":              fecha_movimiento,
        "clave_afiliacion_issemym": clave_issemym,
        "rfc":                      rfc_val,
        "nombre_completo":          nombre,
        "institucion_publica":      institucion,
        "clave_institucion_publica": clave_inst,
        "nombramiento_categoria":   nombramiento,
        "fecha_emision":            fecha_emision,
        "firma_cadena_digital":     None,
        "texto_extraido":           texto_join[:2000],
    }


def extract_fields_native(pdf_path) -> dict | None:
    """
    Intenta extraer campos usando texto nativo del PDF (PyMuPDF).
    Devuelve None si el PDF no tiene texto seleccionable.
    """
    from pathlib import Path
    path = Path(pdf_path)
    try:
        with fitz.open(path) as doc:
            texto = ""
            for page in doc:
                texto += page.get_text("text", sort=True) + "\n"
        if len(texto.strip()) < 40:
            return None
        lineas = _limpiar_lineas(texto)
        return extract_fields_from_lines(lineas)
    except Exception:
        return None


def clean_text(value):
    if not value:
        return None
    value = value.upper().replace('\n', ' ').replace('\r', ' ')
    value = re.sub(r'\s+', ' ', value).strip(' :|-')
    return value or None

def normalize_digits(value):
    if not value:
        return None
    value = value.upper().replace('O', '0').replace('I', '1').replace('L', '1')
    value = re.sub(r'[^0-9/]', '', value)
    return value or None

def normalize_rfc(value):
    if not value:
        return None

    value = value.upper()
    value = value.replace("O", "0").replace("I", "1")
    value = re.sub(r'[^A-Z0-9Ñ&]', '', value)

    matches = re.findall(r'[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}', value)
    if not matches:
        return None

    invalid_prefixes = ("ALTA", "BAJA", "ULAD", "TTPO", "TIA", "CLAV", "NOMB")

    for m in matches:
        if m.startswith(invalid_prefixes):
            continue

        letras = m[:4]
        numeros = m[4:10]

        if not letras.isalpha():
            continue

        if not numeros.isdigit():
            continue

        return m

    return None

def normalize_name(value):
    if not value:
        return None
    value = value.upper()
    value = value.replace('N0MBRE C0MPLET0 DE LA PERS0NA SERVID0RA PUBLICA', '')
    value = value.replace('NOMBRE COMPLETO DE LA PERSONA SERVIDORA PUBLICA', '')
    value = re.sub(r'[^A-ZÑÁÉÍÓÚ ]', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip()
    words = value.split()
    if len(words) < 2:
        return None
    return ' '.join(words[:6])

def normalize_date(value):
    if not value:
        return None
    value = normalize_digits(value)
    m = re.search(r'(\d{2})/(\d{2})/(\d{2,4})', value)
    if not m:
        return None

    dd, mm, yy = m.groups()

    if len(yy) == 2:
        yy = '20' + yy

    if yy == '2076':
        yy = '2026'

    if yy.startswith('207'):
        yy = '202' + yy[-1]

    return f"{dd}/{mm}/{yy}"

def normalize_clave_issemym(value):
    if not value:
        return None
    value = normalize_digits(value)
    m = re.search(r'\b\d{6,7}\b', value)
    if not m:
        return None
    clave = m.group(0)
    if clave in {'20511', '15000', '162628'}:
        return None
    return clave

def normalize_clave_institucion(value):
    if not value:
        return None
    value = normalize_digits(value)
    m = re.search(r'\b\d{5}\b', value)
    return m.group(0) if m else None

def normalize_tipo(value):
    if not value:
        return None
    value = clean_text(value)
    for item in ['ALTA', 'BAJA', 'CAMBIO']:
        if item in value:
            return item
    return None

def normalize_institucion(value):
    value = clean_text(value)
    return value if value else None

def normalize_nombramiento(value):
    value = clean_text(value)
    if not value:
        return None
    if 'PROFESOR TITULADO' in value:
        return 'PROFESOR TITULADO'
    return value

def normalize_firma(value):
    value = clean_text(value)
    return value if value else None

def extract_fields_from_structured(data):
    return {
        'tipo_movimiento': normalize_tipo(data.get('tipo_movimiento')),
        'a_partir_de': normalize_date(data.get('a_partir_de')),
        'clave_afiliacion_issemym': normalize_clave_issemym(data.get('clave_issemym')),
        'rfc': normalize_rfc(data.get('rfc')),
        'nombre_completo': normalize_name(data.get('nombre_completo')),
        'institucion_publica': normalize_institucion(data.get('institucion_publica')),
        'clave_institucion_publica': normalize_clave_institucion(data.get('clave_institucion')),
        'nombramiento_categoria': normalize_nombramiento(data.get('nombramiento_categoria')),
        'fecha_emision': normalize_date(data.get('fecha_emision')),
        'firma_cadena_digital': normalize_firma(data.get('firma_cadena')),
        'texto_extraido': clean_text(data.get('texto_completo')),
    }

def extract_fields(raw_text):
    text = clean_text(raw_text) or ''
    rfc = normalize_rfc(text)
    fechas = re.findall(r'\b\d{2}/\d{2}/\d{2,4}\b', text)

    tipo = None
    for item in ['ALTA', 'BAJA', 'CAMBIO']:
        if item in text:
            tipo = item
            break

    fecha_a_partir = fechas[0] if fechas else None
    fecha_emision = fechas[-1] if fechas else None

    if fecha_a_partir:
        fecha_a_partir = normalize_date(fecha_a_partir)
    if fecha_emision:
        fecha_emision = normalize_date(fecha_emision)

    return {
        'tipo_movimiento': tipo,
        'a_partir_de': fecha_a_partir,
        'clave_afiliacion_issemym': None,
        'rfc': rfc,
        'nombre_completo': None,
        'institucion_publica': None,
        'clave_institucion_publica': '20511' if '20511' in text else None,
        'nombramiento_categoria': 'PROFESOR TITULADO' if 'PROFESOR TITULADO' in text else None,
        'fecha_emision': fecha_emision,
        'firma_cadena_digital': None,
        'texto_extraido': text,
    }


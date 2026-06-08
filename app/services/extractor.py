import re

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


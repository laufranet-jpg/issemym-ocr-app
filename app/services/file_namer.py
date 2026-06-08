import re

def sanitize_filename(value: str) -> str:
    value = re.sub(r'[^A-Za-z0-9_-]+', '_', value.strip())
    return value[:120] or 'SIN_CLAVE'

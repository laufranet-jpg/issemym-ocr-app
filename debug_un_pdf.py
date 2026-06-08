import re
import csv
from pathlib import Path
import fitz

pdf = Path(r".\data\output\pagina_0001.pdf")
salida_csv = Path(r".\salida\debug_resultado.csv")
salida_txt = Path(r".\salida\debug_texto.txt")

PATRON_FECHA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
PATRON_RFC_CURP = re.compile(r"\b[A-ZÑ&]{4,6}\d{6}[A-Z0-9]{0,8}\b")
PATRON_NUM = re.compile(r"^\d{4,10}$")

def extraer_texto(pdf_path):
    texto = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            texto.append(page.get_text("text", sort=True))
    return "\n".join(texto)

def limpiar_lineas(texto):
    out = []
    for ln in texto.splitlines():
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            out.append(ln)
    return out

def extraer(lineas):
    texto = "\n".join(lineas)
    fechas = PATRON_FECHA.findall(texto)
    fecha_movimiento = fechas[0] if len(fechas) > 0 else ""
    fecha_emision = fechas[1] if len(fechas) > 1 else ""

    rfc_curp = ""
    for ln in lineas:
        m = PATRON_RFC_CURP.search(ln)
        if m:
            rfc_curp = m.group(0)
            break

    clave_issemym = ""
    for i, ln in enumerate(lineas):
        limpio = ln.replace(" ", "")
        if PATRON_NUM.match(limpio):
            if i + 1 < len(lineas) and rfc_curp and rfc_curp in lineas[i + 1]:
                clave_issemym = limpio
                break
    if not clave_issemym:
        nums = [ln.replace(" ", "") for ln in lineas if PATRON_NUM.match(ln.replace(" ", ""))]
        clave_issemym = nums[0] if nums else ""

    tipo_movimiento = ""
    for ln in lineas:
        if ln in ("ALTA", "BAJA", "REINGRESO", "MODIFICACION", "MODIFICACIÓN"):
            tipo_movimiento = ln
            break

    nombre_completo = ""
    if rfc_curp:
        for i, ln in enumerate(lineas):
            if rfc_curp in ln:
                for j in range(i + 1, min(i + 6, len(lineas))):
                    cand = lineas[j]
                    if len(cand.split()) >= 2 and cand.upper() == cand and "GEM" not in cand and "PUBLICA" not in cand and "PUBLICO" not in cand:
                        nombre_completo = cand
                        break
                break

    clave_institucion = ""
    institucion_publica = ""
    if nombre_completo:
        idx = lineas.index(nombre_completo)
        for j in range(idx + 1, min(idx + 10, len(lineas))):
            cand = lineas[j].replace(" ", "")
            if PATRON_NUM.match(cand) and cand != clave_issemym:
                clave_institucion = cand
                for k in range(j + 1, min(j + 5, len(lineas))):
                    if "GEM" in lineas[k] or "EDUCACION" in lineas[k] or "EDUCACIÓN" in lineas[k]:
                        institucion_publica = lineas[k]
                        break
                break

    nombramiento = ""
    if institucion_publica:
        idx = lineas.index(institucion_publica)
        for j in range(idx + 1, min(idx + 5, len(lineas))):
            cand = lineas[j]
            if not PATRON_FECHA.search(cand) and cand not in ("SERVIDOR PUBLICO", "INSTITUCION PUBLICA", "CLAVE ISSEMYM"):
                nombramiento = cand
                break

    firma_sello = ""
    for ln in lineas:
        if ln in ("SERVIDOR PUBLICO", "INSTITUCION PUBLICA"):
            firma_sello = ln
            break

    return {
        "tipo_movimiento": tipo_movimiento,
        "fecha_movimiento": fecha_movimiento,
        "clave_issemym": clave_issemym,
        "rfc_curp": rfc_curp,
        "nombre_completo": nombre_completo,
        "institucion_publica": institucion_publica,
        "clave_institucion": clave_institucion,
        "nombramiento": nombramiento,
        "fecha_emision": fecha_emision,
        "firma_sello": firma_sello
    }

texto = extraer_texto(pdf)
salida_txt.write_text(texto, encoding="utf-8")
lineas = limpiar_lineas(texto)
resultado = extraer(lineas)

with open(salida_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(resultado.keys()))
    writer.writeheader()
    writer.writerow(resultado)

print("RESULTADO:")
for k, v in resultado.items():
    print(f"{k}: {v}")

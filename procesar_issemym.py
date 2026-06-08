import re
from pathlib import Path
import pandas as pd
import fitz

CARPETA_PDFS = r"C:\Users\PACO LAPTOP\Documents\issemym_ocr_app\pdfs_entrada"
SALIDA_EXCEL = r"C:\Users\PACO LAPTOP\Documents\issemym_ocr_app\salida\issemym_concentrado.xlsx"
HOJA_DATOS = "datos"
HOJA_LOG = "log"
RENOMBRAR_ARCHIVOS = True

PATRON_FECHA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
PATRON_RFC_CURP = re.compile(r"\b[A-ZÑ&]{4,6}\d{6}[A-Z0-9]{0,8}\b")
PATRON_CLAVE = re.compile(r"^\d{4,10}$")
PATRON_FORMATO = re.compile(r"FO-CPSS-[A-Z0-9-]+")
PATRON_SOLO_MAYUS = re.compile(r"^[A-ZÁÉÍÓÚÜÑ0-9 /.,()-]+$")

def extraer_texto_pdf(pdf_path: Path) -> str:
    partes = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            partes.append(page.get_text("text", sort=True))
    return "\n".join(partes)

def limpiar_lineas(texto: str):
    lineas = []
    for ln in texto.splitlines():
        x = re.sub(r"\s+", " ", ln).strip()
        if x:
            lineas.append(x)
    return lineas

def es_nombre_probable(s: str) -> bool:
    if len(s) < 8:
        return False
    if not PATRON_SOLO_MAYUS.match(s):
        return False
    descartes = {
        "CLAVE ISSEMYM", "SERVIDOR PUBLICO", "INSTITUCION PUBLICA",
        "GOBIERNO DEL", "ESTADO DE MEXICO", "ESTADO DE MÉXICO", "ISSEMYM",
        "AVISO DE MOVIMIENTO PARA LA AFILIACION Y VIGENCIA DE DERECHOS",
        "AVISO DE MOVIMIENTO PARA LA AFILIACIÓN Y VIGENCIA DE DERECHOS"
    }
    if s in descartes:
        return False
    palabras = s.split()
    return len(palabras) >= 2 and all(len(p) > 1 for p in palabras)

def es_institucion_probable(s: str) -> bool:
    claves = ["GEM", "INSTITUCION", "DIRECCION", "DIRECCIÓN", "EDUCACION", "EDUCACIÓN", "SECRETARIA", "SECRETARÍA", "AYUNTAMIENTO"]
    return len(s) >= 8 and any(k in s for k in claves)

def extraer_campos_desde_lineas(lineas):
    texto_join = "\n".join(lineas)

    fechas = PATRON_FECHA.findall(texto_join)
    fecha_movimiento = fechas[0] if len(fechas) >= 1 else ""
    fecha_emision = fechas[1] if len(fechas) >= 2 else ""

    rfc_curp = ""
    for ln in lineas:
        m = PATRON_RFC_CURP.search(ln)
        if m:
            rfc_curp = m.group(0)
            break

    clave_issemym = ""
    idx_rfc = -1
    if rfc_curp:
        for i, ln in enumerate(lineas):
            if rfc_curp in ln:
                idx_rfc = i
                break

    if idx_rfc > 0:
        for j in range(max(0, idx_rfc - 3), idx_rfc):
            cand = lineas[j].replace(" ", "")
            if PATRON_CLAVE.match(cand):
                clave_issemym = cand
                break

    if not clave_issemym:
        nums = [ln.replace(" ", "") for ln in lineas if PATRON_CLAVE.match(ln.replace(" ", ""))]
        if nums:
            clave_issemym = nums[0]

    tipo_movimiento = ""
    for ln in lineas:
        if ln in {"ALTA", "BAJA", "REINGRESO", "MODIFICACION", "MODIFICACIÓN"}:
            tipo_movimiento = ln
            break

    nombre_completo = ""
    if idx_rfc >= 0:
        for j in range(idx_rfc + 1, min(len(lineas), idx_rfc + 6)):
            ln = lineas[j]
            if es_nombre_probable(ln) and not es_institucion_probable(ln):
                nombre_completo = ln
                break

    clave_institucion = ""
    institucion_publica = ""
    if nombre_completo:
        idx_nombre = lineas.index(nombre_completo)
        for j in range(idx_nombre + 1, min(len(lineas), idx_nombre + 8)):
            cand = lineas[j].replace(" ", "")
            if PATRON_CLAVE.match(cand) and cand != clave_issemym:
                clave_institucion = cand
                idx_clave_inst = j
                for k in range(j + 1, min(len(lineas), j + 6)):
                    if es_institucion_probable(lineas[k]) or es_nombre_probable(lineas[k]):
                        institucion_publica = lineas[k]
                        break
                break

    nombramiento = ""
    if institucion_publica:
        idx_inst = lineas.index(institucion_publica)
        for j in range(idx_inst + 1, min(len(lineas), idx_inst + 6)):
            ln = lineas[j]
            if not PATRON_FECHA.search(ln) and ln not in {"SERVIDOR PUBLICO", "INSTITUCION PUBLICA", "CLAVE ISSEMYM"}:
                if len(ln) >= 5:
                    nombramiento = ln
                    break

    firma_sello = ""
    for ln in lineas:
        if ln in {"SERVIDOR PUBLICO", "INSTITUCION PUBLICA"}:
            firma_sello = ln
            break

    formato = ""
    mform = PATRON_FORMATO.search(texto_join)
    if mform:
        formato = mform.group(0)

    sueldo_mensual = ""
    observaciones = ""

    return {
        "tipo_movimiento": tipo_movimiento,
        "fecha_movimiento": fecha_movimiento,
        "clave_issemym": clave_issemym,
        "rfc_curp": rfc_curp,
        "nombre_completo": nombre_completo,
        "institucion_publica": institucion_publica,
        "clave_institucion": clave_institucion,
        "nombramiento": nombramiento,
        "sueldo_mensual": sueldo_mensual,
        "fecha_emision": fecha_emision,
        "firma_sello": firma_sello,
        "observaciones": observaciones,
        "formato": formato,
    }

def nombre_unico(destino: Path) -> Path:
    if not destino.exists():
        return destino
    base = destino.stem
    suf = destino.suffix
    i = 1
    while True:
        candidato = destino.with_name(f"{base}_{i}{suf}")
        if not candidato.exists():
            return candidato
        i += 1

def procesar_pdfs():
    carpeta = Path(CARPETA_PDFS)
    pdfs = sorted(carpeta.glob("*.pdf"))

    if not pdfs:
        raise FileNotFoundError(f"No se encontraron PDFs en: {carpeta}")

    registros = []
    log = []

    for pdf in pdfs:
        status = "OK"
        error = ""
        archivo_renombrado = pdf.name

        try:
            texto = extraer_texto_pdf(pdf)
            lineas = limpiar_lineas(texto)
            campos = extraer_campos_desde_lineas(lineas)

            clave = campos.get("clave_issemym", "").strip()
            if clave and RENOMBRAR_ARCHIVOS:
                destino = pdf.with_name(f"{clave}{pdf.suffix.lower()}")
                destino = nombre_unico(destino) if destino.exists() and destino.resolve() != pdf.resolve() else destino
                if destino.resolve() != pdf.resolve():
                    pdf.rename(destino)
                    archivo_renombrado = destino.name

            if not clave:
                status = "SIN_CLAVE"

            registros.append({
                "archivo_original": pdf.name,
                "archivo_renombrado": archivo_renombrado,
                **campos
            })

        except Exception as e:
            status = "ERROR"
            error = str(e)
            registros.append({
                "archivo_original": pdf.name,
                "archivo_renombrado": "",
                "tipo_movimiento": "",
                "fecha_movimiento": "",
                "clave_issemym": "",
                "rfc_curp": "",
                "nombre_completo": "",
                "institucion_publica": "",
                "clave_institucion": "",
                "nombramiento": "",
                "sueldo_mensual": "",
                "fecha_emision": "",
                "firma_sello": "",
                "observaciones": "",
                "formato": "",
            })

        log.append({
            "archivo_original": pdf.name,
            "archivo_renombrado": archivo_renombrado,
            "estatus": status,
            "error": error
        })

    df = pd.DataFrame(registros)
    df_log = pd.DataFrame(log)

    columnas = [
        "archivo_original",
        "archivo_renombrado",
        "clave_issemym",
        "tipo_movimiento",
        "fecha_movimiento",
        "rfc_curp",
        "nombre_completo",
        "institucion_publica",
        "clave_institucion",
        "nombramiento",
        "sueldo_mensual",
        "fecha_emision",
        "firma_sello",
        "observaciones",
        "formato",
    ]
    df = df.reindex(columns=columnas)

    salida = Path(SALIDA_EXCEL)
    salida.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=HOJA_DATOS, index=False)
        df_log.to_excel(writer, sheet_name=HOJA_LOG, index=False)

    print(f"Excel generado en: {salida}")
    print(f"Registros procesados: {len(df)}")

if __name__ == "__main__":
    procesar_pdfs()

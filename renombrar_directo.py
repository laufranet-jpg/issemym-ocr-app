import re
from pathlib import Path
import fitz

CARPETA = Path(r"C:\Users\PACO LAPTOP\Documents\issemym_ocr_app\data\output")

PATRON_RFC_CURP = re.compile(r"\b[A-ZÑ&]{4,6}\d{6}[A-Z0-9]{0,8}\b")
PATRON_NUM = re.compile(r"^\d{4,10}$")

def extraer_texto(pdf_path):
    partes = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            partes.append(page.get_text("text", sort=True))
    return "\n".join(partes)

def limpiar_lineas(texto):
    out = []
    for ln in texto.splitlines():
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            out.append(ln)
    return out

def extraer_clave(lineas):
    idx_rfc = -1
    for i, ln in enumerate(lineas):
        if PATRON_RFC_CURP.search(ln):
            idx_rfc = i
            break
    if idx_rfc > 0:
        for j in range(max(0, idx_rfc - 4), idx_rfc):
            cand = lineas[j].replace(" ", "")
            if PATRON_NUM.match(cand):
                return cand.zfill(7)
    nums = [ln.replace(" ", "") for ln in lineas if PATRON_NUM.match(ln.replace(" ", ""))]
    return nums[0].zfill(7) if nums else ""

def nombre_unico(destino):
    if not destino.exists():
        return destino
    i = 1
    while True:
        candidato = destino.with_name(f"{destino.stem}_{i}{destino.suffix}")
        if not candidato.exists():
            return candidato
        i += 1

pdfs = sorted(CARPETA.glob("*.pdf"), key=lambda p: p.name.lower())
renombrados = sin_clave = errores = 0

for pdf in pdfs:
    try:
        clave = extraer_clave(limpiar_lineas(extraer_texto(pdf)))
        if not clave:
            print(f"SIN CLAVE: {pdf.name}")
            sin_clave += 1
            continue
        destino = nombre_unico(pdf.with_name(f"{clave}{pdf.suffix.lower()}"))
        if destino.resolve() != pdf.resolve():
            print(f"{pdf.name} -> {destino.name}")
            pdf.rename(destino)
            renombrados += 1
    except Exception as e:
        print(f"ERROR {pdf.name}: {e}")
        errores += 1

print(f"\nRenombrados : {renombrados}")
print(f"Sin clave   : {sin_clave}")
print(f"Errores     : {errores}")
print(f"Total PDFs  : {len(pdfs)}")

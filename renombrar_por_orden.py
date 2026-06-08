from pathlib import Path
import pandas as pd

EXCEL = Path(r"C:\Users\PACO LAPTOP\Documents\issemym_ocr_app\salida\issemym_concentrado.xlsx")
CARPETA = Path(r"C:\Users\PACO LAPTOP\Documents\issemym_ocr_app\data\output")

df = pd.read_excel(EXCEL, sheet_name="datos", dtype=str).fillna("")
pdfs = sorted(CARPETA.glob("*.pdf"), key=lambda p: p.name.lower())

if "clave_issemym" not in df.columns:
    raise ValueError("El Excel no contiene la columna clave_issemym")

claves = [str(x).strip() for x in df["clave_issemym"].tolist()]

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

renombrados = 0
sin_clave = 0

for pdf, clave in zip(pdfs, claves):
    if not clave:
        sin_clave += 1
        continue

    clave = clave.zfill(7)
    destino = pdf.with_name(f"{clave}{pdf.suffix.lower()}")

    if destino.exists() and destino.resolve() != pdf.resolve():
        destino = nombre_unico(destino)

    if destino.resolve() != pdf.resolve():
        pdf.rename(destino)
        renombrados += 1

print(f"PDFs en carpeta: {len(pdfs)}")
print(f"Claves en Excel: {len(claves)}")
print(f"Renombrados: {renombrados}")
print(f"Sin clave: {sin_clave}")

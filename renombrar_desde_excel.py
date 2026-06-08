from pathlib import Path
import pandas as pd

EXCEL = Path(r"C:\Users\PACO LAPTOP\Documents\issemym_ocr_app\salida\issemym_concentrado.xlsx")
CARPETA = Path(r"C:\Users\PACO LAPTOP\Documents\issemym_ocr_app\data\output")

df = pd.read_excel(EXCEL, sheet_name="datos", dtype=str).fillna("")

if "archivo_original" not in df.columns or "clave_issemym" not in df.columns:
    raise ValueError("El Excel no contiene las columnas archivo_original y clave_issemym")

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

renombrados = []
sin_clave = []
no_encontrados = []

for _, row in df.iterrows():
    original = str(row["archivo_original"]).strip()
    clave = str(row["clave_issemym"]).strip()

    if not original:
        continue

    origen = CARPETA / original

    if not origen.exists():
        no_encontrados.append(original)
        continue

    if not clave:
        sin_clave.append(original)
        continue

    clave = clave.zfill(7)
    destino = CARPETA / f"{clave}{origen.suffix.lower()}"

    if destino.exists() and destino.resolve() != origen.resolve():
        destino = nombre_unico(destino)

    if destino.resolve() != origen.resolve():
        origen.rename(destino)

    renombrados.append((original, destino.name))

print(f"Renombrados: {len(renombrados)}")
print(f"Sin clave: {len(sin_clave)}")
print(f"No encontrados: {len(no_encontrados)}")

for x in renombrados[:20]:
    print(f"{x[0]} -> {x[1]}")

import fitz
from pathlib import Path

pdf = Path(r".\pdfs_entrada\pagina_0001.pdf")
doc = fitz.open(pdf)
texto = []
for page in doc:
    texto.append(page.get_text("text", sort=True))

Path(r".\salida\debug_pagina_0001.txt").write_text("\n\n".join(texto), encoding="utf-8")
print("OK")

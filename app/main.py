from pathlib import Path
import pandas as pd
import pandas as pd
from fastapi.responses import FileResponse
import shutil
import re

from fastapi import FastAPI, Request, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
import pandas as pd

from .database import Base, engine, get_db
from .models import DocumentRecord
from .services.pdf_splitter import split_pdf
from .services.ocr_service import ocr_pdf_page, ocr_structured_fields
from .services.extractor import extract_fields, extract_fields_from_structured
from .services.file_namer import sanitize_filename

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ISSEMYM OCR App")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def save_upload(upload: UploadFile) -> Path:
    destination = INPUT_DIR / upload.filename
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return destination


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process", response_class=HTMLResponse)
def process_pdf(request: Request, pdf_file: UploadFile = File(...), db: Session = Depends(get_db)):
    uploaded_path = save_upload(pdf_file)
    split_files = split_pdf(uploaded_path, OUTPUT_DIR)

    processed = 0

    for idx, single_pdf in enumerate(split_files, start=1):
        structured_raw = ocr_structured_fields(single_pdf, 0)
        fields = extract_fields_from_structured(structured_raw)

        if fields.get("rfc") and not re.fullmatch(r"[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}", fields["rfc"]):
            fields["rfc"] = None

        if fields.get("rfc") and fields["rfc"].startswith(("ALTA", "BAJA", "ULAD", "TIA", "TTPO")):
            fields["rfc"] = None

        if not fields.get("rfc") and not fields.get("tipo_movimiento"):
            full_text = ocr_pdf_page(single_pdf, 0)
            fields = extract_fields(full_text)

        clave = fields.get("clave_afiliacion_issemym")
        final_name = f"{sanitize_filename(clave)}.pdf" if clave else f"SIN_CLAVE_{idx:04d}.pdf"
        final_path = single_pdf.with_name(final_name)

        counter = 1
        while final_path.exists() and final_path.name != single_pdf.name:
            stem = final_path.stem
            if "_dup" in stem:
                stem = stem.rsplit("_dup", 1)[0]
            final_path = final_path.with_name(f"{stem}_dup{counter}.pdf")
            counter += 1

        single_pdf.rename(final_path)

        record = DocumentRecord(
            tipo_movimiento=fields.get("tipo_movimiento"),
            a_partir_de=fields.get("a_partir_de"),
            clave_afiliacion_issemym=fields.get("clave_afiliacion_issemym"),
            rfc=fields.get("rfc"),
            nombre_completo=fields.get("nombre_completo"),
            institucion_publica=fields.get("institucion_publica"),
            clave_institucion_publica=fields.get("clave_institucion_publica"),
            nombramiento_categoria=fields.get("nombramiento_categoria"),
            fecha_emision=fields.get("fecha_emision"),
            firma_cadena_digital=fields.get("firma_cadena_digital"),
            nombre_archivo_pdf=final_path.name,
            ruta_archivo_pdf=str(final_path),
            pagina_origen=idx,
            texto_extraido=fields.get("texto_extraido"),
        )

        db.add(record)
        processed += 1

    db.commit()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "message": f"Proceso completado. Documentos procesados: {processed}",
        },
    )


@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = "", db: Session = Depends(get_db)):
    results = []

    if q.strip():
        token = f"%{q.strip()}%"
        results = (
            db.query(DocumentRecord)
            .filter(
                or_(
                    DocumentRecord.tipo_movimiento.ilike(token),
                    DocumentRecord.a_partir_de.ilike(token),
                    DocumentRecord.clave_afiliacion_issemym.ilike(token),
                    DocumentRecord.rfc.ilike(token),
                    DocumentRecord.nombre_completo.ilike(token),
                    DocumentRecord.institucion_publica.ilike(token),
                    DocumentRecord.clave_institucion_publica.ilike(token),
                    DocumentRecord.nombramiento_categoria.ilike(token),
                    DocumentRecord.fecha_emision.ilike(token),
                    DocumentRecord.firma_cadena_digital.ilike(token),
                    DocumentRecord.nombre_archivo_pdf.ilike(token),
                )
            )
            .order_by(DocumentRecord.id.desc())
            .all()
        )

    return templates.TemplateResponse(
        "search.html",
        {"request": request, "results": results, "q": q},
    )


@app.get("/detail/{record_id}", response_class=HTMLResponse)
def detail(record_id: int, request: Request, db: Session = Depends(get_db)):
    record = db.query(DocumentRecord).filter(DocumentRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    return templates.TemplateResponse(
        "detail.html",
        {"request": request, "record": record},
    )


@app.get("/pdf/{record_id}")
def open_pdf(record_id: int, db: Session = Depends(get_db)):
    record = db.query(DocumentRecord).filter(DocumentRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    pdf_path = Path(record.ruta_archivo_pdf)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Archivo PDF no encontrado")

    return FileResponse(
        path=pdf_path,
        filename=record.nombre_archivo_pdf,
        media_type="application/pdf",
    )


@app.post("/procesar-lote-web")
async def procesar_lote_web(file: UploadFile = File(...), db: Session = Depends(get_db)):
    import uuid
    import fitz
    
    # 1. Guardar el documento maestro original en la carpeta de entrada
    pdf_original = INPUT_DIR / file.filename
    with open(pdf_original, "wb") as buffer:
        buffer.write(await file.read())
        
    # Crear un subdirectorio temporal único para aislar las hojas desglosadas
    id_lote = str(uuid.uuid4())[:6]
    carpeta_paginas = OUTPUT_DIR / f"paginas_{id_lote}"
    carpeta_paginas.mkdir(parents=True, exist_ok=True)
    
    # Separar el PDF maestro en archivos individuales de 1 hoja cada uno
    split_pdf(pdf_original, carpeta_paginas)
    
    # 2 y 3. Recorrer cada hoja desglosada, extraer texto y renombrar
    archivos_hojas = sorted(carpeta_paginas.glob("*.pdf"))
    
    for index, ruta_hoja in enumerate(archivos_hojas, start=1):
        # Intentar extracción directa de texto nativo con PyMuPDF
        texto_extraido = ""
        with fitz.open(ruta_hoja) as doc:
            for page in doc:
                texto_extraido += page.get_text("text", sort=True)
                
        # Si la página viene vacía (es un escaneo plano), aplicar tu OCR existente
        if not texto_extraido.strip():
            try:
                texto_extraido = ocr_pdf_page(ruta_hoja)
            except Exception:
                texto_extraido = ""
                
        # Aplicar reglas de expresiones regulares para identificar las variables críticas
        fechas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", texto_extraido)
        fecha_movimiento = fechas[0] if len(fechas) > 0 else ""
        fecha_emision = fechas[1] if len(fechas) > 1 else ""
        
        rfcs = re.findall(r"\b[A-ZÑ&]{4,6}\d{6}[A-Z0-9]{0,8}\b", texto_extraido)
        rfc_val = rfcs[0] if rfcs else ""
        
        # Aislar clave ISSEMYM buscando patrones de dígitos numéricos
        clave_issemym = "0000000"
        lineas = [ln.strip() for ln in texto_extraido.splitlines() if ln.strip()]
        for ln in lineas:
            cand = ln.replace(" ", "")
            if re.match(r"^\d{4,10}$", cand):
                clave_issemym = cand.zfill(7)
                break
                
        # Buscar el nombre completo del servidor público
        nombre_completo = "DESCONOCIDO"
        for ln in lineas:
            if re.match(r"^[A-ZÁÉÍÓÚÜÑ ]+$", ln) and len(ln) > 12:
                if not any(k in ln for k in ["ISSEMYM", "DOCUMENTO", "MOVIMIENTO", "FECHA", "INSTITUCION"]):
                    nombre_completo = ln
                    break
                    
        # Identificar tipo de movimiento básico
        tipo_movimiento = "ALTA"
        if "BAJA" in texto_extraido.upper():
            tipo_movimiento = "BAJA"
        elif "CAMBIO" in texto_extraido.upper():
            tipo_movimiento = "CAMBIO"
            
        # Renombrar físicamente el archivo utilizando la clave oficial extraída
        nombre_nuevo = f"{clave_issemym}_{id_lote}_{index}.pdf"
        ruta_renombrada = OUTPUT_DIR / nombre_nuevo
        shutil.copy(ruta_hoja, ruta_renombrada)
        
        # 4. Alimentar tu base de datos SQLite para habilitar las consultas inmediatas
        nuevo_registro = DocumentRecord(
            tipo_movimiento=tipo_movimiento,
            a_partir_de=fecha_movimiento,
            clave_afiliacion_issemym=clave_issemym,
            rfc=rfc_val,
            nombre_completo=nombre_completo,
            institucion_publica="CONSOLIDADO WEB",
            clave_institucion_publica="001",
            nombramiento_categoria="PROCESADO",
            fecha_emision=fecha_emision,
            nombre_archivo_pdf=nombre_nuevo,
            ruta_archivo_pdf=str(ruta_renombrada),
            pagina_origen=index,
            texto_extraido=texto_extraido
        )
        db.add(nuevo_registro)
        
    db.commit()
    
    # Redireccionar automáticamente al buscador web para reflejar los nuevos datos cargados
    return RedirectResponse(url="/", status_code=303)

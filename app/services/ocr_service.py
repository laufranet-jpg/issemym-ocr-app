from pathlib import Path
import fitz
import cv2
import numpy as np
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_native_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"
    doc.close()
    return text.strip()

def render_page_as_array(pdf_path: Path, page_number: int = 0, zoom: float = 3.0):
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    doc.close()
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img

def preprocess_for_ocr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    th = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 15
    )
    th = cv2.fastNlMeansDenoising(th, None, 20, 7, 21)
    return th

def crop_region(img, x1, y1, x2, y2):
    h, w = img.shape[:2]
    return img[int(y1*h):int(y2*h), int(x1*w):int(x2*w)]

def ocr_image(img, psm=6, whitelist=None):
    config = f'--oem 3 --psm {psm}'
    if whitelist:
        config += f' -c tessedit_char_whitelist="{whitelist}"'
    return pytesseract.image_to_string(img, lang="eng", config=config).strip()

def ocr_pdf_page(pdf_path: Path, page_number: int = 0) -> str:
    img = render_page_as_array(pdf_path, page_number, zoom=3.0)
    proc = preprocess_for_ocr(img)
    return ocr_image(proc, psm=6)

def ocr_structured_fields(pdf_path: Path, page_number: int = 0) -> dict:
    img = render_page_as_array(pdf_path, page_number, zoom=3.0)
    proc = preprocess_for_ocr(img)

    regions = {
        "tipo_movimiento":        (0.03, 0.18, 0.23, 0.34),
        "a_partir_de":            (0.24, 0.18, 0.50, 0.34),
        "clave_issemym":          (0.50, 0.18, 0.74, 0.34),
        "rfc":                    (0.03, 0.30, 0.24, 0.46),
        "nombre_completo":        (0.24, 0.30, 0.74, 0.46),
        "institucion_publica":    (0.03, 0.43, 0.55, 0.60),
        "clave_institucion":      (0.55, 0.43, 0.74, 0.60),
        "nombramiento_categoria": (0.03, 0.58, 0.55, 0.76),
        "fecha_emision":          (0.55, 0.58, 0.74, 0.76),
        "firma_cadena":           (0.03, 0.73, 0.92, 0.93),
    }

    data = {}
    for key, box in regions.items():
        roi = crop_region(proc, *box)
        if key in ("clave_issemym", "clave_institucion", "a_partir_de", "fecha_emision"):
            data[key] = ocr_image(roi, psm=7, whitelist="0123456789/")
        elif key == "rfc":
            data[key] = ocr_image(roi, psm=7, whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        elif key == "tipo_movimiento":
            data[key] = ocr_image(roi, psm=7, whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        else:
            data[key] = ocr_image(roi, psm=6)

    data["texto_completo"] = ocr_image(proc, psm=6)
    return data

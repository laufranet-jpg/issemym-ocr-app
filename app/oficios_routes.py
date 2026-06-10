"""
Rutas del módulo de Oficios — importadas en main.py
"""
from datetime import datetime as _dt
from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from .database import get_db
from .models import DocumentRecord, OficioPlantilla, OficioGenerado
from .auth import SEARCH_ROLES, ADMIN_ROLES


# ─── Variable resolver ────────────────────────────────────────────────────────

def _resolve_vars(html: str, record=None, numero_oficio: str = "") -> str:
    """Sustituye {{variable}} en el HTML de la plantilla con datos reales."""
    today = _dt.now().strftime("%d de %B de %Y")
    meses = {
        "January": "enero",   "February": "febrero", "March": "marzo",
        "April": "abril",     "May": "mayo",          "June": "junio",
        "July": "julio",      "August": "agosto",     "September": "septiembre",
        "October": "octubre", "November": "noviembre","December": "diciembre",
    }
    for en, es in meses.items():
        today = today.replace(en, es)

    vals = {
        "fecha_actual":       today,
        "numero_oficio":      numero_oficio or "_______________",
        "nombre_completo":    "",
        "clave_issemym":      "",
        "rfc":                "",
        "tipo_movimiento":    "",
        "a_partir_de":        "",
        "institucion_publica": "",
        "clave_institucion":  "",
        "nombramiento":       "",
        "fecha_emision":      "",
        "archivo_pdf":        "",
    }
    if record:
        vals.update({
            "nombre_completo":    record.nombre_completo            or "",
            "clave_issemym":      record.clave_afiliacion_issemym   or "",
            "rfc":                record.rfc                        or "",
            "tipo_movimiento":    record.tipo_movimiento            or "",
            "a_partir_de":        record.a_partir_de                or "",
            "institucion_publica": record.institucion_publica       or "",
            "clave_institucion":  record.clave_institucion_publica  or "",
            "nombramiento":       record.nombramiento_categoria     or "",
            "fecha_emision":      record.fecha_emision              or "",
            "archivo_pdf":        record.nombre_archivo_pdf         or "",
        })
    for key, val in vals.items():
        html = html.replace("{{" + key + "}}", val)
    return html


# ─── Semilla de plantillas ────────────────────────────────────────────────────

PLANTILLAS_DEFAULT = [
    {
        "nombre": "Solicitud de Datos Faltantes",
        "descripcion": "Oficio para solicitar información incompleta de un trabajador.",
        "orden": 1,
        "contenido_html": """<p style="text-align:right;">Toluca de Lerdo, Estado de México, a {{fecha_actual}}</p>
<p>&nbsp;</p>
<p><strong>OFICIO NÚM. {{numero_oficio}}</strong></p>
<p>&nbsp;</p>
<p><strong>ASUNTO: SOLICITUD DE DATOS COMPLEMENTARIOS</strong></p>
<p>&nbsp;</p>
<p>C. RESPONSABLE DE RECURSOS HUMANOS<br>
{{institucion_publica}}<br>
CLAVE: {{clave_institucion}}<br>
P R E S E N T E.</p>
<p>&nbsp;</p>
<p>Por medio del presente, y en atención a la revisión del Aviso de Movimiento para la Afiliación y Vigencia de Derechos del Instituto de Seguridad Social del Estado de México y Municipios (ISSEMYM), correspondiente al trabajador:</p>
<p>&nbsp;</p>
<p><strong>Nombre completo:</strong> {{nombre_completo}}<br>
<strong>Clave de afiliación ISSEMYM:</strong> {{clave_issemym}}<br>
<strong>RFC / CURP:</strong> {{rfc}}<br>
<strong>Nombramiento / Categoría:</strong> {{nombramiento}}<br>
<strong>Tipo de movimiento:</strong> {{tipo_movimiento}}<br>
<strong>Fecha de vigencia:</strong> {{a_partir_de}}</p>
<p>&nbsp;</p>
<p>Me permito solicitarle atentamente que en el plazo de <strong>cinco días hábiles</strong> a partir de la recepción del presente, remita la información y/o documentación complementaria requerida para la correcta tramitación del aviso antes referido:</p>
<p>&nbsp;</p>
<ol>
<li>____________________________________________________</li>
<li>____________________________________________________</li>
<li>____________________________________________________</li>
</ol>
<p>&nbsp;</p>
<p>Sin otro particular, quedo a sus órdenes para cualquier aclaración.</p>
<p>&nbsp;</p>
<p>A T E N T A M E N T E</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>_____________________________________________<br>
<strong>NOMBRE Y FIRMA DEL RESPONSABLE</strong><br>
Secretaría de Educación del Estado de México</p>""",
    },
    {
        "nombre": "Solicitud de Corrección de Datos",
        "descripcion": "Oficio para solicitar la corrección de datos erróneos en un aviso.",
        "orden": 2,
        "contenido_html": """<p style="text-align:right;">Toluca de Lerdo, Estado de México, a {{fecha_actual}}</p>
<p>&nbsp;</p>
<p><strong>OFICIO NÚM. {{numero_oficio}}</strong></p>
<p>&nbsp;</p>
<p><strong>ASUNTO: CORRECCIÓN DE DATOS EN AVISO DE MOVIMIENTO</strong></p>
<p>&nbsp;</p>
<p>C. RESPONSABLE DE RECURSOS HUMANOS<br>
{{institucion_publica}}<br>
CLAVE: {{clave_institucion}}<br>
P R E S E N T E.</p>
<p>&nbsp;</p>
<p>En relación al Aviso de Movimiento para la Afiliación y Vigencia de Derechos correspondiente al trabajador <strong>{{nombre_completo}}</strong>, con clave ISSEMYM <strong>{{clave_issemym}}</strong>, se detectaron las siguientes inconsistencias que requieren corrección:</p>
<p>&nbsp;</p>
<table border="1" cellpadding="6" cellspacing="0" width="100%">
<thead><tr style="background-color:#8C1C40;color:#fff;">
<th>Campo</th><th>Dato registrado</th><th>Dato correcto</th>
</tr></thead>
<tbody>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</tbody>
</table>
<p>&nbsp;</p>
<p>Por lo anterior, se le solicita enviar el aviso corregido y la documentación soporte correspondiente a la brevedad posible.</p>
<p>&nbsp;</p>
<p>A T E N T A M E N T E</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>_____________________________________________<br>
<strong>NOMBRE Y FIRMA DEL RESPONSABLE</strong><br>
Secretaría de Educación del Estado de México</p>""",
    },
    {
        "nombre": "Acuse de Recepción de Aviso",
        "descripcion": "Confirma la recepción y registro del aviso de movimiento.",
        "orden": 3,
        "contenido_html": """<p style="text-align:right;">Toluca de Lerdo, Estado de México, a {{fecha_actual}}</p>
<p>&nbsp;</p>
<p><strong>OFICIO NÚM. {{numero_oficio}}</strong></p>
<p>&nbsp;</p>
<p><strong>ASUNTO: ACUSE DE RECEPCIÓN — AVISO DE MOVIMIENTO ISSEMYM</strong></p>
<p>&nbsp;</p>
<p>C. RESPONSABLE DE RECURSOS HUMANOS<br>
{{institucion_publica}}<br>
CLAVE: {{clave_institucion}}<br>
P R E S E N T E.</p>
<p>&nbsp;</p>
<p>Por este medio se hace constar que esta área ha recibido y registrado correctamente el <strong>Aviso de Movimiento para la Afiliación y Vigencia de Derechos</strong> con los siguientes datos:</p>
<p>&nbsp;</p>
<p><strong>Trabajador:</strong> {{nombre_completo}}<br>
<strong>Clave ISSEMYM:</strong> {{clave_issemym}}<br>
<strong>RFC / CURP:</strong> {{rfc}}<br>
<strong>Tipo de movimiento:</strong> {{tipo_movimiento}}<br>
<strong>Vigencia a partir de:</strong> {{a_partir_de}}<br>
<strong>Nombramiento:</strong> {{nombramiento}}<br>
<strong>Fecha de emisión del aviso:</strong> {{fecha_emision}}<br>
<strong>Archivo de referencia:</strong> {{archivo_pdf}}</p>
<p>&nbsp;</p>
<p>El presente documento sirve como constancia de recepción. Para cualquier aclaración, comuníquese con esta área.</p>
<p>&nbsp;</p>
<p>A T E N T A M E N T E</p>
<p>&nbsp;</p>
<p>&nbsp;</p>
<p>_____________________________________________<br>
<strong>NOMBRE Y FIRMA DEL RESPONSABLE</strong><br>
Secretaría de Educación del Estado de México</p>""",
    },
]


def seed_oficio_plantillas(db: Session):
    """Inserta plantillas predeterminadas si la tabla está vacía."""
    if db.query(OficioPlantilla).first():
        return
    for data in PLANTILLAS_DEFAULT:
        db.add(OficioPlantilla(**data))
    db.commit()

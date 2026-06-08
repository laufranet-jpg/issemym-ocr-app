from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from .database import Base

class DocumentRecord(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    tipo_movimiento = Column(String(255), index=True)
    a_partir_de = Column(String(50), index=True)
    clave_afiliacion_issemym = Column(String(100), index=True)
    rfc = Column(String(20), index=True)
    nombre_completo = Column(String(255), index=True)
    institucion_publica = Column(String(255), index=True)
    clave_institucion_publica = Column(String(100), index=True)
    nombramiento_categoria = Column(String(255), index=True)
    fecha_emision = Column(String(50), index=True)
    firma_cadena_digital = Column(Text)
    nombre_archivo_pdf = Column(String(255), index=True)
    ruta_archivo_pdf = Column(String(500))
    pagina_origen = Column(Integer)
    texto_extraido = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

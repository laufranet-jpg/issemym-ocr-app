from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50),  unique=True, index=True, nullable=False)
    email         = Column(String(255), unique=True, index=True, nullable=True)
    full_name     = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    # Roles separados por coma: "busqueda,dashboards"  |  "adjuntar,admin"
    role          = Column(String(100), nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    @property
    def roles(self) -> set[str]:
        """Devuelve el conjunto de roles del usuario."""
        if not self.role:
            return set()
        return {r.strip() for r in self.role.split(",") if r.strip()}

    def has_any(self, *allowed: str) -> bool:
        """True si el usuario tiene al menos uno de los roles indicados."""
        return bool(self.roles & set(allowed))


import re
import bcrypt

ROLES = {
    "busqueda":   ("Búsqueda",      "#0d6efd"),
    "adjuntar":   ("Adjuntar datos","#198754"),
    "dashboards": ("Dashboards",    "#C49A2A"),
    "admin":      ("Administrador", "#8C1C40"),
}

# Qué rutas-acción puede hacer cada rol
UPLOAD_ROLES    = {"adjuntar", "admin"}
EDIT_ROLES      = {"adjuntar", "admin"}
SEARCH_ROLES    = {"busqueda", "adjuntar", "dashboards", "admin"}
DASHBOARD_ROLES = {"dashboards", "admin"}
ADMIN_ROLES     = {"admin"}
ALL_ROLES       = set(ROLES)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_password(password: str) -> list[str]:
    """Devuelve lista de errores; vacía = válida."""
    errors: list[str] = []
    if len(password) < 8:
        errors.append("Mínimo 8 caracteres")
    if not re.search(r"[A-Z]", password):
        errors.append("Al menos una mayúscula (A-Z)")
    if not re.search(r"[a-z]", password):
        errors.append("Al menos una minúscula (a-z)")
    if not re.search(r"\d", password):
        errors.append("Al menos un número (0-9)")
    if not re.search(r'[!@#$%^&*()\-_=+\[\]{};:\'",.<>?/\\|`~]', password):
        errors.append("Al menos un carácter especial (!@#$%...)")
    return errors

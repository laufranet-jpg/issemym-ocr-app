# CLAUDE.md — ISSEMYM OCR App
> Documento de referencia permanente. Claude lee esto al inicio de cada sesión.
> Última actualización: 2026-06-08

---

## ¿Qué es este proyecto?

Sistema web de gestión documental para la **Secretaría de Educación del Estado de México**.
Procesa PDFs de *"Avisos de Movimiento para la Afiliación y Vigencia de Derechos"* del ISSEMYM:
extrae datos con OCR, los guarda en base de datos y permite buscar, editar, exportar y enviar por correo.

**URL local**: `http://127.0.0.1:8000`
**LAN oficina**: `http://<IP_SERVIDOR>:8000`

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x |
| BD (dev) | SQLite (`data/issemym.db`) |
| BD (prod) | PostgreSQL (via `DATABASE_URL` env var) |
| Templates | Jinja2 + Bootstrap 5.3 |
| OCR | PyMuPDF (nativo) → pytesseract (fallback) |
| Auth | SessionMiddleware (Starlette) + bcrypt 5.x directo |
| Export | openpyxl (XLSX) |
| Email | outlook.live.com/compose + descarga PDF automática |
| Procesamiento | ThreadPoolExecutor (4 workers), SSE para progreso |

---

## Estructura del proyecto

```
issemym_ocr_app/
├── app/
│   ├── main.py                  ← Todas las rutas FastAPI
│   ├── models.py                ← DocumentRecord + User
│   ├── auth.py                  ← Hashing, validación contraseña, constantes de roles
│   ├── database.py              ← Engine SQLite/PostgreSQL, get_db()
│   ├── services/
│   │   ├── extractor.py         ← Extracción campos OCR (lógica principal)
│   │   ├── pdf_splitter.py      ← Divide PDF multipágina
│   │   ├── ocr_service.py       ← pytesseract wrapper
│   │   └── file_namer.py        ← sanitize_filename()
│   ├── templates/
│   │   ├── index.html           ← Home: upload PDF + stats hero
│   │   ├── search.html          ← Buscador con filtros
│   │   ├── detail.html          ← Detalle + edición + visor PDF + email
│   │   ├── dashboard.html       ← Gráficas Chart.js
│   │   ├── admin_usuarios.html  ← Lista usuarios
│   │   ├── admin_usuario_form.html ← Crear/editar usuario (checkboxes multi-rol)
│   │   ├── perfil.html          ← Cambio de contraseña propio
│   │   ├── login.html           ← Login
│   │   ├── 403.html             ← Acceso denegado
│   │   ├── _header_user.html    ← Partial: nombre + chips de roles
│   │   └── _footer.html         ← "2026 FICG Systems..."
│   └── static/
│       └── style.css            ← Estilos GEM (burgundy #8C1C40, oro #C49A2A)
├── data/
│   ├── input/                   ← PDFs originales subidos
│   ├── output/                  ← PDFs por página (renombrados CLAVE.pdf)
│   ├── issemym.db               ← SQLite (se crea automáticamente)
│   └── .session_key             ← Clave sesión (auto-generada, NO borrar)
├── deploy/                      ← Archivos para Oracle Cloud / Linux
│   ├── deploy.sh
│   ├── issemym.service
│   ├── nginx.conf
│   ├── .env.production
│   └── INSTRUCCIONES.md
├── iniciar_servidor.bat         ← Arranque LAN Windows (doble clic)
├── requirements.txt
└── CLAUDE.md                    ← Este archivo
```

---

## Modelos de base de datos

### `DocumentRecord` — tabla `documents`
```python
id, tipo_movimiento, a_partir_de,          # "ALTA"/"BAJA"/"CAMBIO", "DD/MM/YYYY"
clave_afiliacion_issemym, rfc,             # "1310581", "LASJ940303FF2"
nombre_completo, institucion_publica,      # nombres completos
clave_institucion_publica,                 # "20534"
nombramiento_categoria, fecha_emision,     # "PROFESOR SUPER B", "05/10/2022"
firma_cadena_digital, nombre_archivo_pdf,  # cadena digital, "1310581.pdf"
ruta_archivo_pdf, pagina_origen,           # ruta absoluta, número de página
texto_extraido, created_at
```

> ⚠️ `a_partir_de` y `fecha_emision` se guardan como **texto DD/MM/YYYY**.
> Para filtrar por rango de fechas se usa `_date_sortable_expr()` que convierte
> `DD/MM/YYYY → YYYYMMDD` con `func.substr().op("||")` (NO usar `+` — es suma aritmética).

### `User` — tabla `users`
```python
id, username (UNIQUE), email (UNIQUE nullable),
full_name, hashed_password,
role,        # CSV: "busqueda,dashboards" | "adjuntar,admin"
is_active, created_at, created_by_id (FK)
```
Propiedades: `.roles` → `set[str]`, `.has_any(*roles)` → `bool`

---

## Sistema de roles

| Rol | Permisos |
|-----|----------|
| `busqueda` | Buscar, ver, exportar XLSX, enviar correo |
| `adjuntar` | + Subir PDFs, editar y renombrar registros |
| `dashboards` | + Ver dashboard (solo lectura) |
| `admin` | Acceso total + gestión de usuarios |

Un usuario puede tener **múltiples roles** separados por coma en `User.role`.

En templates usar siempre: `{% if has_role(current_user, "adjuntar", "admin") %}`
**NUNCA**: `{% if current_user.role in ["adjuntar","admin"] %}` — eso solo compara un rol.

En Python usar: `user.has_any(*UPLOAD_ROLES)` — NUNCA `user.role in UPLOAD_ROLES`.

---

## Rutas API

```
GET  /                          → Home
GET/POST /login                 → Login
GET  /logout                    → Logout
GET  /search                    → Buscador
GET  /api/search                → JSON (q, tipo, desde, hasta, page, per_page)
GET  /api/stats                 → JSON totales/tipos/años/instituciones
GET  /api/export                → Descarga XLSX
GET  /api/email_data/{id}       → JSON {outlook_url, pdf_url, pdf_name}
POST /process                   → Upload PDF, SSE streaming
GET  /detail/{id}               → Detalle registro
POST /update/{id}               → Guardar cambios
POST /rename/{id}               → Renombrar archivo
GET  /pdf/{id}                  → Servir PDF inline
GET  /email/{id}                → Redirect a Outlook web (fallback sin JS)
GET  /dashboard                 → Dashboard
GET/POST /perfil                → Ver/cambiar contraseña
GET  /admin/usuarios            → Lista usuarios
GET/POST /admin/usuarios/nuevo  → Crear usuario
GET/POST /admin/usuarios/{id}/editar  → Editar usuario
POST /admin/usuarios/{id}/toggle      → Activar/desactivar
```

---

## Reglas críticas de desarrollo

### Contraseñas
- Usar `hash_password()` y `verify_password()` de `app/auth.py`
- **NO usar passlib** — incompatible con bcrypt 5.x (`bcrypt.__about__` fue eliminado)
- `validate_password()` devuelve lista de errores (vacía = OK)
- Reglas: 8+ chars, mayúscula, minúscula, número, carácter especial

### Formularios multi-valor (checkboxes de roles)
- Los handlers POST que reciben múltiples checkboxes deben ser `async def`
- Usar `fd = await request.form()` y `fd.getlist("roles")` — NO `Form()` params

### Fechas
- Almacenadas como texto `DD/MM/YYYY`
- Para comparar rangos en SQL: usar `_date_sortable_expr()` + `_ddmmyyyy_to_yyyymmdd()`
- El operador `+` sobre `func.substr()` es ARITMÉTICO — usar `.op("||")` para concatenar

### Jinja2
- `set()` NO está disponible — usar `[]` o `{}` literales
- Helper global: `has_role(user, *roles)` → registrado en `templates.env.globals`

---

## Usuario administrador inicial
- **Username**: `admin`
- **Password**: `Admin@2026!`
- Se crea solo al primer arranque si no hay usuarios en la BD

---

## Cómo arrancar

### Desarrollo
```cmd
cd C:\Users\PACO LAPTOP\Documents\issemym_ocr_app
venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000
```

### Red local de oficina (LAN)
```cmd
# Doble clic en:
iniciar_servidor.bat
# Las demás PCs acceden a http://<IP_SERVIDOR>:8000
```

### Instalar dependencias (primera vez)
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Colores institucionales GEM
```css
--gem-dark:        #5A1128;
--gem-burgundy:    #8C1C40;
--gem-gold:        #C49A2A;
--gem-gold-light:  #e8c96a;
```

---

## Bugs ya resueltos — NO repetir

| # | Síntoma | Causa | Fix |
|---|---------|-------|-----|
| 1 | `AttributeError: module 'bcrypt' has no attribute '__about__'` | passlib incompatible con bcrypt 5.x | Eliminar passlib, usar bcrypt directamente |
| 2 | `TypeError: NoneType - int` en pool_size | `pool_size=None` en SQLite | `_engine_kwargs` condicional por tipo de BD |
| 3 | Institución pública extrae valor de nombramiento | PDF con orden campos invertido | Búsqueda bidireccional en `extractor.py` |
| 4 | Error al renderizar formulario nuevo usuario | `set()` no existe en Jinja2 | Usar `[]` en su lugar |
| 5 | Filtro de fechas no funciona | `+` sobre `func.substr()` = suma numérica | Usar `.op("||")` para concatenar strings en SQL |
| 6 | Botón correo descargaba .eml | `Content-Disposition: attachment` | Redirigir a `outlook.live.com/compose` + descargar PDF |

---

## Despliegue en Oracle Cloud (si se necesita)
Ver `deploy/INSTRUCCIONES.md` — Oracle AMD Always Free, Ubuntu 22.04, 1GB RAM.
Script automatizado: `deploy/deploy.sh` (crea SWAP 2GB, instala todo, configura nginx + systemd).

---

## Contacto del proyecto
- **Organización**: Gobierno del Estado de México · Secretaría de Educación
- **Sistema**: ISSEMYM – Trámites Externos
- **Copyright**: 2026 FICG Systems. Todos los derechos reservados.

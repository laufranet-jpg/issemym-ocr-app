#!/usr/bin/env bash
# =============================================================================
# ISSEMYM Trámites Externos — Script de despliegue
# Servidor: Oracle Cloud Always Free AMD (Ubuntu 22.04, 1 GB RAM, 47 GB disco)
#
# USO:
#   1. Sube este script al servidor:
#        scp deploy/deploy.sh ubuntu@TU_IP:/home/ubuntu/
#   2. Conéctate por SSH:
#        ssh ubuntu@TU_IP
#   3. Ejecuta:
#        chmod +x deploy.sh && sudo bash deploy.sh
# =============================================================================

set -euo pipefail

# ── Configuración — EDITA ESTOS VALORES ANTES DE EJECUTAR ────────────────────
APP_DIR="/opt/issemym"
APP_USER="issemym"
DB_NAME="issemym_db"
DB_USER="issemym_user"
DB_PASS="$(openssl rand -base64 24 | tr -d '/+=')"   # se genera automáticamente
REPO_URL="https://github.com/TU_USUARIO/TU_REPO.git" # o deja vacío para subir manualmente
SERVER_IP="$(curl -s ifconfig.me 2>/dev/null || echo 'TU_IP')"
# ─────────────────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

[[ $EUID -ne 0 ]] && error "Ejecuta como root: sudo bash deploy.sh"

info "=== ISSEMYM — Despliegue en Oracle Cloud AMD ==="
info "IP del servidor: $SERVER_IP"

# ── 1. SWAP (crítico con 1 GB RAM) ───────────────────────────────────────────
info "Configurando SWAP de 2 GB..."
if ! swapon --show | grep -q /swapfile; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    # Reducir agresividad de swap (solo usar cuando sea necesario)
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    sysctl -p
    info "SWAP 2 GB activado."
else
    info "SWAP ya configurado."
fi

# ── 2. ACTUALIZAR SISTEMA ─────────────────────────────────────────────────────
info "Actualizando sistema..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq

# ── 3. INSTALAR DEPENDENCIAS ──────────────────────────────────────────────────
info "Instalando dependencias del sistema..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    postgresql postgresql-contrib \
    nginx \
    tesseract-ocr tesseract-ocr-spa \
    libmupdf-dev \
    git curl wget \
    build-essential \
    ufw \
    certbot python3-certbot-nginx \
    htop unzip

info "Dependencias instaladas."

# ── 4. USUARIO DE LA APLICACIÓN ───────────────────────────────────────────────
info "Creando usuario '$APP_USER'..."
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --create-home --shell /bin/bash "$APP_USER"
    info "Usuario '$APP_USER' creado."
else
    info "Usuario '$APP_USER' ya existe."
fi

# ── 5. CÓDIGO DE LA APLICACIÓN ────────────────────────────────────────────────
info "Configurando directorio de la aplicación en $APP_DIR..."
mkdir -p "$APP_DIR"

if [[ -n "$REPO_URL" && "$REPO_URL" != *"TU_USUARIO"* ]]; then
    info "Clonando repositorio: $REPO_URL"
    if [[ -d "$APP_DIR/.git" ]]; then
        git -C "$APP_DIR" pull
    else
        git clone "$REPO_URL" "$APP_DIR"
    fi
else
    warn "No se configuró REPO_URL."
    warn "Sube el código manualmente:"
    warn "  scp -r issemym_ocr_app/* ubuntu@$SERVER_IP:$APP_DIR/"
fi

# Crear directorios de datos
mkdir -p "$APP_DIR/data/input"
mkdir -p "$APP_DIR/data/output"

# ── 6. ENTORNO VIRTUAL PYTHON ────────────────────────────────────────────────
info "Creando entorno virtual Python..."
python3.11 -m venv "$APP_DIR/venv"
source "$APP_DIR/venv/bin/activate"

info "Instalando dependencias Python..."
pip install --quiet --upgrade pip
pip install --quiet -r "$APP_DIR/requirements.txt"
deactivate
info "Dependencias Python instaladas."

# ── 7. POSTGRESQL ─────────────────────────────────────────────────────────────
info "Configurando PostgreSQL..."
systemctl enable postgresql
systemctl start postgresql

# Esperar a que PostgreSQL esté listo
sleep 3

# Crear usuario y base de datos
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null || \
    sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || \
    info "Base de datos ya existe."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

# ── Optimización PostgreSQL para 1 GB RAM ─────────────────────────────────────
PG_CONF=$(find /etc/postgresql -name "postgresql.conf" | head -1)
info "Optimizando PostgreSQL para 1 GB RAM: $PG_CONF"
cat >> "$PG_CONF" << 'PGCONF'

# --- Optimización ISSEMYM para 1 GB RAM ---
max_connections = 25
shared_buffers = 128MB
effective_cache_size = 384MB
maintenance_work_mem = 32MB
checkpoint_completion_target = 0.9
wal_buffers = 4MB
default_statistics_target = 100
work_mem = 2MB
min_wal_size = 256MB
max_wal_size = 512MB
random_page_cost = 1.1
log_timezone = 'America/Mexico_City'
timezone = 'America/Mexico_City'
PGCONF

systemctl restart postgresql
info "PostgreSQL configurado y reiniciado."

# ── 8. ARCHIVO .env ───────────────────────────────────────────────────────────
info "Creando archivo .env..."
cat > "$APP_DIR/.env" << EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
APP_ENV=production
EOF
chmod 600 "$APP_DIR/.env"
info "Archivo .env creado."

# ── 9. PERMISOS ───────────────────────────────────────────────────────────────
info "Configurando permisos..."
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 750 "$APP_DIR"

# ── 10. SYSTEMD SERVICE ──────────────────────────────────────────────────────
info "Configurando servicio systemd..."
cp "$(dirname "$0")/issemym.service" /etc/systemd/system/issemym.service
# Ajustar WorkingDirectory y EnvironmentFile por si el script no tiene la ruta correcta
sed -i "s|/opt/issemym|$APP_DIR|g" /etc/systemd/system/issemym.service

systemctl daemon-reload
systemctl enable issemym
info "Servicio issemym configurado."

# ── 11. NGINX ─────────────────────────────────────────────────────────────────
info "Configurando nginx..."
cp "$(dirname "$0")/nginx.conf" /etc/nginx/sites-available/issemym
sed -i "s|TU_IP_O_DOMINIO|$SERVER_IP|g" /etc/nginx/sites-available/issemym
sed -i "s|/opt/issemym|$APP_DIR|g" /etc/nginx/sites-available/issemym

# Habilitar el sitio
ln -sf /etc/nginx/sites-available/issemym /etc/nginx/sites-enabled/issemym
# Deshabilitar el sitio default
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl enable nginx && systemctl restart nginx
info "Nginx configurado."

# ── 12. FIREWALL ─────────────────────────────────────────────────────────────
info "Configurando firewall UFW..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
info "Firewall configurado."

# Oracle Cloud también requiere abrir puertos en Security List (ver instrucciones)

# ── 13. INICIALIZAR BASE DE DATOS ────────────────────────────────────────────
info "Inicializando base de datos (creando tablas)..."
cd "$APP_DIR"
source "$APP_DIR/venv/bin/activate"
DATABASE_URL="postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME" \
    python3 -c "
from app.database import Base, engine
Base.metadata.create_all(bind=engine)
print('Tablas creadas correctamente.')
"
deactivate

# ── 14. ARRANCAR APLICACIÓN ──────────────────────────────────────────────────
info "Arrancando aplicación..."
systemctl start issemym
sleep 4

if systemctl is-active --quiet issemym; then
    info "Aplicación corriendo correctamente."
else
    warn "La aplicación no arrancó. Revisa los logs:"
    warn "  journalctl -u issemym -n 50"
fi

# ── RESUMEN FINAL ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  DESPLIEGUE COMPLETADO${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  URL de la app:     ${YELLOW}http://$SERVER_IP${NC}"
echo -e "  Usuario admin:     ${YELLOW}admin${NC}"
echo -e "  Contraseña admin:  ${YELLOW}Admin@2026!${NC}"
echo ""
echo -e "  Base de datos:     ${YELLOW}$DB_NAME${NC}"
echo -e "  Usuario BD:        ${YELLOW}$DB_USER${NC}"
echo -e "  Contraseña BD:     ${YELLOW}$DB_PASS${NC}"
echo ""
echo -e "${YELLOW}  ⚠ IMPORTANTE — Lee deploy/INSTRUCCIONES.md para:${NC}"
echo -e "     1. Abrir puertos en Oracle Cloud Security List"
echo -e "     2. Instalar certificado SSL (HTTPS)"
echo -e "     3. Subir el código si no usaste git"
echo ""
echo -e "${GREEN}  Comandos útiles:${NC}"
echo -e "  Ver logs:          journalctl -u issemym -f"
echo -e "  Reiniciar app:     systemctl restart issemym"
echo -e "  Estado:            systemctl status issemym"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"

# Guardar contraseña de BD en archivo seguro
echo "DB_PASS=$DB_PASS" > /root/issemym_credenciales.txt
chmod 600 /root/issemym_credenciales.txt
info "Credenciales guardadas en /root/issemym_credenciales.txt"

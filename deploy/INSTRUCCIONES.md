# Guía de despliegue — Oracle Cloud Always Free AMD

## Requisitos previos

- Cuenta Oracle Cloud (gratuita en cloud.oracle.com)
- Instancia creada: **Ubuntu 22.04 / AMD / VM.Standard.E2.1.Micro**
- Llave SSH generada para conectarte

---

## Paso 1 — Crear la instancia en Oracle Cloud

1. Entra a **cloud.oracle.com → Compute → Instances → Create Instance**
2. Configura:
   - **Name:** issemym-server
   - **Image:** Ubuntu 22.04
   - **Shape:** VM.Standard.E2.1.Micro (Always Free AMD)
   - **Storage:** 47 GB (máximo gratis)
   - **SSH keys:** Sube tu llave pública
3. Anota la **IP pública** que aparece al crear la instancia

---

## Paso 2 — Abrir puertos en Oracle Cloud

⚠️ Oracle Cloud tiene **dos** capas de firewall. Debes abrir puertos en ambas.

### 2a. Security List (firewall de la red virtual)

1. Ve a **Networking → Virtual Cloud Networks → tu-VCN → Security Lists**
2. Entra a la **Default Security List**
3. Agrega estas reglas de **Ingress** (entrada):

| Protocolo | Puerto | Origen | Descripción |
|-----------|--------|--------|-------------|
| TCP | 80 | 0.0.0.0/0 | HTTP |
| TCP | 443 | 0.0.0.0/0 | HTTPS |
| TCP | 22 | 0.0.0.0/0 | SSH (ya existe) |

### 2b. El script de deploy ya configura UFW (firewall del servidor)

---

## Paso 3 — Subir el código al servidor

### Opción A: Desde tu computadora con scp
```bash
# En tu computadora (PowerShell o Git Bash)
scp -r "C:\Users\PACO LAPTOP\Documents\issemym_ocr_app\*" ubuntu@TU_IP:/tmp/issemym/
```

### Opción B: Usando GitHub (recomendado para futuras actualizaciones)
```bash
# En tu computadora
cd "C:\Users\PACO LAPTOP\Documents\issemym_ocr_app"
git push origin main

# En el servidor, edita REPO_URL en deploy.sh antes de ejecutarlo
```

---

## Paso 4 — Conectarte al servidor

```bash
# En PowerShell o Git Bash
ssh ubuntu@TU_IP

# Si usas archivo de llave:
ssh -i ruta/a/tu-llave.pem ubuntu@TU_IP
```

---

## Paso 5 — Ejecutar el script de despliegue

```bash
# En el servidor
# Primero copia los archivos de deploy/
scp deploy/deploy.sh deploy/issemym.service deploy/nginx.conf ubuntu@TU_IP:/home/ubuntu/

# Luego en el servidor:
chmod +x /home/ubuntu/deploy.sh
sudo bash /home/ubuntu/deploy.sh
```

El script tarda aproximadamente **5–10 minutos** en completarse.

---

## Paso 6 — Mover el código a su lugar

Si no usaste GitHub, después del deploy mueve el código:

```bash
# En el servidor
sudo cp -r /tmp/issemym/* /opt/issemym/
sudo chown -R issemym:issemym /opt/issemym/
sudo systemctl restart issemym
```

---

## Paso 7 — Verificar que funciona

```bash
# Estado del servicio
sudo systemctl status issemym

# Logs en tiempo real
sudo journalctl -u issemym -f

# Prueba rápida
curl http://localhost:8000/login
```

Abre en el navegador: **http://TU_IP**

Credenciales iniciales:
- Usuario: `admin`
- Contraseña: `Admin@2026!`

---

## Paso 8 — HTTPS con dominio propio (opcional)

Si tienes un dominio apuntando a tu IP:

```bash
# En el servidor
sudo certbot --nginx -d tu-dominio.com

# Certbot configura nginx automáticamente y renueva el certificado solo
# Verificar renovación automática:
sudo certbot renew --dry-run
```

Después edita `/etc/nginx/sites-available/issemym` y descomenta la sección HTTPS.

---

## Comandos de mantenimiento

```bash
# Ver logs de la app
sudo journalctl -u issemym -f

# Reiniciar la app
sudo systemctl restart issemym

# Ver uso de RAM (crítico con 1 GB)
free -h

# Ver uso de disco (vigilar PDFs)
df -h /opt/issemym/data/

# Conectarse a la base de datos
sudo -u postgres psql issemym_db

# Backup de la base de datos
sudo -u postgres pg_dump issemym_db > /home/ubuntu/backup_$(date +%Y%m%d).sql

# Actualizar la app (si usas GitHub)
cd /opt/issemym
sudo git pull
sudo -u issemym /opt/issemym/venv/bin/pip install -r requirements.txt
sudo systemctl restart issemym
```

---

## Advertencia sobre el disco (47 GB)

Con 300,000 PDFs de una página (~200 KB promedio):
- **300,000 × 200 KB = ~60 GB** ← supera el disco gratuito

**Soluciones:**
1. Comprimir los PDFs después de procesarlos
2. Usar Oracle Object Storage (20 GB gratis adicionales)
3. Subir los PDFs en lotes y archivar los antiguos
4. Aumentar el volumen de bloque (costo extra ~$0.025/GB/mes)

---

## Monitoreo de recursos

Con 1 GB RAM el servidor es ajustado. Monitorea regularmente:

```bash
# Ver todos los procesos
htop

# Ver RAM en uso
free -h

# Si la app se cae por falta de RAM, el SWAP de 2 GB la rescata
# pero el rendimiento baja. Si pasa seguido, considera ARM A1.
```

---

## Estructura final en el servidor

```
/opt/issemym/
├── app/                    ← código Python
│   ├── main.py
│   ├── models.py
│   ├── static/
│   └── templates/
├── data/
│   ├── input/              ← PDFs originales subidos
│   ├── output/             ← PDFs divididos (uno por registro)
│   └── .session_key        ← clave de sesión (generada auto)
├── venv/                   ← entorno virtual Python
├── .env                    ← variables de entorno (DATABASE_URL)
└── requirements.txt
```

# ============================================================
#  ISSEMYM OCR App — Setup automatico para PC servidor
#  Ejecutar como Administrador en PowerShell
#  Compatible con Windows 10/11
# ============================================================

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host "`n>>> $msg" -ForegroundColor Cyan
}
function Write-OK($msg) {
    Write-Host "    OK: $msg" -ForegroundColor Green
}
function Write-WARN($msg) {
    Write-Host "    AVISO: $msg" -ForegroundColor Yellow
}

Write-Host @"

  ============================================================
    ISSEMYM - Instalacion automatica del servidor
    Secretaria de Educacion del Estado de Mexico
  ============================================================

"@ -ForegroundColor Magenta

# ── Verificar que se ejecuta como Administrador ───────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")
if (-not $isAdmin) {
    Write-Host "ERROR: Ejecuta este script como Administrador." -ForegroundColor Red
    Write-Host "Clic derecho sobre PowerShell -> 'Ejecutar como administrador'" -ForegroundColor Yellow
    exit 1
}

# ── Habilitar winget si no esta disponible ────────────────────
Write-Step "Verificando winget (Windows Package Manager)..."
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
    Write-WARN "winget no encontrado. Instalando App Installer desde Microsoft Store..."
    Start-Process "ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1" -Wait
    Write-Host "    Instala 'App Installer' desde la tienda y vuelve a ejecutar este script." -ForegroundColor Yellow
    exit 0
}
Write-OK "winget disponible"

# ── Instalar Git ──────────────────────────────────────────────
Write-Step "Instalando Git..."
$gitCheck = Get-Command git -ErrorAction SilentlyContinue
if ($gitCheck) {
    Write-OK "Git ya instalado: $(git --version)"
} else {
    winget install --id Git.Git -e --source winget --silent --accept-package-agreements --accept-source-agreements
    $env:PATH += ";C:\Program Files\Git\cmd"
    Write-OK "Git instalado"
}

# ── Instalar Python 3.11 ──────────────────────────────────────
Write-Step "Instalando Python 3.11..."
$pyCheck = Get-Command python -ErrorAction SilentlyContinue
if ($pyCheck) {
    $pyVer = python --version 2>&1
    Write-OK "Python ya instalado: $pyVer"
} else {
    winget install --id Python.Python.3.11 -e --source winget --silent --accept-package-agreements --accept-source-agreements
    $env:PATH += ";C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311;C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311\Scripts"
    Write-OK "Python 3.11 instalado"
}

# ── Instalar Node.js LTS ──────────────────────────────────────
Write-Step "Instalando Node.js LTS..."
$nodeCheck = Get-Command node -ErrorAction SilentlyContinue
if ($nodeCheck) {
    Write-OK "Node.js ya instalado: $(node --version)"
} else {
    winget install --id OpenJS.NodeJS.LTS -e --source winget --silent --accept-package-agreements --accept-source-agreements
    $env:PATH += ";C:\Program Files\nodejs"
    Write-OK "Node.js instalado"
}

# ── Instalar Tesseract OCR ────────────────────────────────────
Write-Step "Instalando Tesseract OCR..."
$tessPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (Test-Path $tessPath) {
    Write-OK "Tesseract ya instalado"
} else {
    winget install --id UB-Mannheim.TesseractOCR -e --source winget --silent --accept-package-agreements --accept-source-agreements
    Write-OK "Tesseract instalado"
}

# Agregar Tesseract al PATH del sistema
$tessDir = "C:\Program Files\Tesseract-OCR"
$currentPath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
if ($currentPath -notlike "*Tesseract*") {
    [System.Environment]::SetEnvironmentVariable("PATH", "$currentPath;$tessDir", "Machine")
    $env:PATH += ";$tessDir"
    Write-OK "Tesseract agregado al PATH del sistema"
}

# ── Instalar Claude Code ──────────────────────────────────────
Write-Step "Instalando Claude Code..."
$claudeCheck = Get-Command claude -ErrorAction SilentlyContinue
if ($claudeCheck) {
    Write-OK "Claude Code ya instalado"
} else {
    # Refrescar PATH para npm
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
    npm install -g @anthropic-ai/claude-code
    Write-OK "Claude Code instalado"
}

# ── Crear carpeta del proyecto ────────────────────────────────
Write-Step "Preparando carpeta del proyecto..."
$projectDir = "C:\issemym_app"
if (-not (Test-Path $projectDir)) {
    New-Item -ItemType Directory -Path $projectDir | Out-Null
    Write-OK "Carpeta creada: $projectDir"
} else {
    Write-OK "Carpeta ya existe: $projectDir"
}

# ── Configurar Firewall ───────────────────────────────────────
Write-Step "Configurando Firewall de Windows (puerto 8000)..."
$ruleName = "ISSEMYM App Puerto 8000"
$ruleExists = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $ruleExists) {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort 8000 `
        -Action Allow `
        -Profile Any | Out-Null
    Write-OK "Regla de firewall creada para puerto 8000"
} else {
    Write-OK "Regla de firewall ya existe"
}

# ── Obtener IP local ──────────────────────────────────────────
Write-Step "Obteniendo IP local de la red..."
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.*" } |
       Select-Object -First 1).IPAddress
Write-OK "IP local del servidor: $ip"

# ── Resumen final ─────────────────────────────────────────────
Write-Host @"

  ============================================================
    INSTALACION COMPLETADA
  ============================================================

  PROXIMOS PASOS:
  1. Copia el proyecto a: C:\issemym_app\
     (todo el contenido de tu carpeta issemym_ocr_app)

  2. Abre PowerShell en C:\issemym_app y ejecuta:
        python -m venv venv
        venv\Scripts\activate
        pip install -r requirements.txt

  3. Prueba el servidor:
        iniciar_servidor.bat

  4. Desde cualquier PC de la oficina abre:
        http://${ip}:8000

  5. Para usar Claude Code:
        cd C:\issemym_app
        claude
     (te pedira login con tu cuenta Anthropic — solo la primera vez)

  ============================================================
"@ -ForegroundColor Green

# ── Crear acceso directo en el escritorio ────────────────────
Write-Step "Creando acceso directo en el escritorio..."
$desktopPath = [System.Environment]::GetFolderPath("CommonDesktopDirectory")
$shortcutPath = "$desktopPath\ISSEMYM Servidor.lnk"

if (-not (Test-Path $shortcutPath)) {
    $WScript = New-Object -ComObject WScript.Shell
    $shortcut = $WScript.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "C:\issemym_app\iniciar_servidor.bat"
    $shortcut.WorkingDirectory = "C:\issemym_app"
    $shortcut.Description = "Iniciar servidor ISSEMYM"
    $shortcut.IconLocation = "C:\Windows\System32\shell32.dll,14"
    $shortcut.Save()
    Write-OK "Acceso directo creado en el escritorio"
}

Write-Host "`nPresiona Enter para cerrar..." -ForegroundColor Gray
Read-Host

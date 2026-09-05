# ============================================================
# INSTALADOR COMPLETO - Classificador de Matrizes
# Windows 10/11 - PowerShell
# ============================================================
# Como usar:
#   1. Abra o PowerShell na pasta do programa
#   2. Execute:
#        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#        .\INSTALAR_TUDO.ps1
# ============================================================

$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "Instalador - Classificador de Matrizes"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR - CLASSIFICADOR DE MATRIZES" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Pasta onde esta este script (= pasta do programa)
$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $BaseDir) { $BaseDir = (Get-Location).Path }
Set-Location $BaseDir
Write-Host "[1/6] Pasta do programa: $BaseDir" -ForegroundColor Green

# ------------------------------------------------------------
# 1) Encontrar o Python
# ------------------------------------------------------------
Write-Host ""
Write-Host "[2/6] Procurando Python..." -ForegroundColor Yellow

$PythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1 | Out-String
        if ($ver -match "Python") {
            $PythonCmd = $cmd
            Write-Host "      Encontrado: $cmd  ($($ver.Trim()))" -ForegroundColor Green
            break
        }
    } catch {
    }
}

if (-not $PythonCmd) {
    Write-Host ""
    Write-Host "ERRO: Python nao encontrado!" -ForegroundColor Red
    Write-Host "Baixe em: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Na instalacao, MARQUE a opcao: Add python.exe to PATH" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Pressione Enter para sair"
    exit 1
}

# ------------------------------------------------------------
# 2) Atualizar pip e instalar bibliotecas
# ------------------------------------------------------------
Write-Host ""
Write-Host "[3/6] Instalando bibliotecas Python..." -ForegroundColor Yellow
Write-Host "      (numpy, vosk, sounddevice, soundfile, piper-tts)" -ForegroundColor Gray

& $PythonCmd -m pip install --upgrade pip
& $PythonCmd -m pip install numpy vosk sounddevice soundfile piper-tts

if ($LASTEXITCODE -ne 0) {
    Write-Host "AVISO: alguma biblioteca pode ter falhado. Continuando..." -ForegroundColor Yellow
} else {
    Write-Host "      Bibliotecas instaladas." -ForegroundColor Green
}

# ------------------------------------------------------------
# 3) Criar pastas
# ------------------------------------------------------------
Write-Host ""
Write-Host "[4/6] Criando pastas piper_voices e vosk_models..." -ForegroundColor Yellow

$PiperDir = Join-Path $BaseDir "piper_voices"
$VoskDir  = Join-Path $BaseDir "vosk_models"
New-Item -ItemType Directory -Force -Path $PiperDir | Out-Null
New-Item -ItemType Directory -Force -Path $VoskDir  | Out-Null
Write-Host "      Pastas criadas." -ForegroundColor Green

# ------------------------------------------------------------
# 4) Baixar modelo Piper (voz)
# ------------------------------------------------------------
Write-Host ""
Write-Host "[5/6] Baixando modelo de voz Piper (pt_BR-faber-medium)..." -ForegroundColor Yellow
Write-Host "      Isso pode demorar alguns minutos." -ForegroundColor Gray

$OnnxUrl  = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"
$JsonUrl  = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"
$OnnxFile = Join-Path $PiperDir "pt_BR-faber-medium.onnx"
$JsonFile = Join-Path $PiperDir "pt_BR-faber-medium.onnx.json"

function Download-IfNeeded {
    param($Url, $Dest, $Label)
    if ((Test-Path $Dest) -and ((Get-Item $Dest).Length -gt 1000)) {
        Write-Host "      Ja existe: $Label" -ForegroundColor Green
        return
    }
    Write-Host "      Baixando $Label ..." -ForegroundColor Gray
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
        Write-Host "      OK: $Label" -ForegroundColor Green
    } catch {
        Write-Host "      FALHA ao baixar $Label" -ForegroundColor Red
        Write-Host "      Baixe manualmente: $Url" -ForegroundColor Yellow
        Write-Host "      e salve em: $Dest" -ForegroundColor Yellow
    }
}

Download-IfNeeded -Url $OnnxUrl -Dest $OnnxFile -Label "pt_BR-faber-medium.onnx"
Download-IfNeeded -Url $JsonUrl -Dest $JsonFile -Label "pt_BR-faber-medium.onnx.json"

# ------------------------------------------------------------
# 5) Baixar modelo Vosk
# ------------------------------------------------------------
Write-Host ""
Write-Host "[6/6] Baixando modelo Vosk (vosk-model-small-pt-0.3)..." -ForegroundColor Yellow
Write-Host "      Isso pode demorar (arquivo cerca de 40 MB)." -ForegroundColor Gray

$VoskZipUrl  = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
$VoskZipFile = Join-Path $VoskDir "vosk-model-small-pt-0.3.zip"
$VoskModel   = Join-Path $VoskDir "vosk-model-small-pt-0.3"
$VoskCheck   = Join-Path $VoskModel "am\final.mdl"

if ((Test-Path $VoskModel) -and (Test-Path $VoskCheck)) {
    Write-Host "      Modelo Vosk ja existe." -ForegroundColor Green
} else {
    try {
        if (-not (Test-Path $VoskZipFile) -or ((Get-Item $VoskZipFile).Length -lt 1000000)) {
            Write-Host "      Baixando ZIP..." -ForegroundColor Gray
            Invoke-WebRequest -Uri $VoskZipUrl -OutFile $VoskZipFile -UseBasicParsing
        }
        Write-Host "      Extraindo..." -ForegroundColor Gray
        Expand-Archive -Path $VoskZipFile -DestinationPath $VoskDir -Force
        Write-Host "      Modelo Vosk instalado." -ForegroundColor Green
    } catch {
        Write-Host "      FALHA ao baixar/extrair Vosk." -ForegroundColor Red
        Write-Host "      Baixe manualmente: $VoskZipUrl" -ForegroundColor Yellow
        Write-Host "      Extraia em: $VoskDir" -ForegroundColor Yellow
    }
}

# ------------------------------------------------------------
# 6) Verificar instalacao
# ------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  VERIFICACAO FINAL" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$ok = $true

Write-Host ""
Write-Host "Bibliotecas Python:" -ForegroundColor White
foreach ($mod in @("numpy", "vosk", "sounddevice", "soundfile", "piper")) {
    $code = "import $mod"
    & $PythonCmd -c $code 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] $mod" -ForegroundColor Green
    } else {
        Write-Host "  [FALTA] $mod" -ForegroundColor Red
        $ok = $false
    }
}

Write-Host ""
Write-Host "Modelos:" -ForegroundColor White
if (Test-Path $OnnxFile) {
    $sz = [math]::Round((Get-Item $OnnxFile).Length / 1MB, 1)
    Write-Host "  [OK] Piper voz ($sz MB)" -ForegroundColor Green
} else {
    Write-Host "  [FALTA] Piper voz (.onnx)" -ForegroundColor Red
    $ok = $false
}
if (Test-Path $JsonFile) {
    Write-Host "  [OK] Piper config (.json)" -ForegroundColor Green
} else {
    Write-Host "  [FALTA] Piper config (.json)" -ForegroundColor Red
    $ok = $false
}
if (Test-Path $VoskCheck) {
    Write-Host "  [OK] Vosk portugues" -ForegroundColor Green
} else {
    Write-Host "  [FALTA] Vosk portugues" -ForegroundColor Red
    $ok = $false
}

Write-Host ""
Write-Host "Estrutura esperada:" -ForegroundColor White
Write-Host "  $BaseDir\"
Write-Host "  +-- classificador_matrizes.py"
Write-Host "  +-- piper_voices\"
Write-Host "  |   +-- pt_BR-faber-medium.onnx"
Write-Host "  |   +-- pt_BR-faber-medium.onnx.json"
Write-Host "  +-- vosk_models\"
Write-Host "      +-- vosk-model-small-pt-0.3\"

Write-Host ""
if ($ok) {
    Write-Host "INSTALACAO CONCLUIDA COM SUCESSO!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Para rodar o programa:" -ForegroundColor Cyan
    $script = Get-ChildItem -Path $BaseDir -Filter "classificador_matrizes*.py" | Select-Object -First 1
    if ($script) {
        Write-Host ("  {0} `"{1}`"" -f $PythonCmd, $script.FullName) -ForegroundColor White
    } else {
        Write-Host "  $PythonCmd classificador_matrizes.py" -ForegroundColor White
    }
} else {
    Write-Host "INSTALACAO INCOMPLETA. Corrija os itens [FALTA] acima." -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Pressione Enter para sair"

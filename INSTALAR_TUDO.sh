#!/usr/bin/env bash
# ============================================================
# INSTALADOR COMPLETO - Classificador de Matrizes
# Ubuntu / Linux
# ============================================================
# Uso:
#   chmod +x INSTALAR_TUDO.sh
#   ./INSTALAR_TUDO.sh
# ============================================================

set -e
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"

echo ""
echo "============================================================"
echo "  INSTALADOR - CLASSIFICADOR DE MATRIZES (Linux)"
echo "============================================================"
echo ""
echo "[1/6] Pasta do programa: $BASE_DIR"

# Python
echo ""
echo "[2/6] Procurando Python..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "ERRO: Python não encontrado. Instale com:"
    echo "  sudo apt install python3 python3-pip"
    exit 1
fi
echo "      Encontrado: $($PYTHON --version)"

# Dependências do sistema (PortAudio)
echo ""
echo "[3/6] Verificando dependências do sistema..."
if command -v apt-get >/dev/null 2>&1; then
    if ! dpkg -s libportaudio2 >/dev/null 2>&1; then
        echo "      Instalando libportaudio2 (pode pedir senha)..."
        sudo apt-get update -qq
        sudo apt-get install -y libportaudio2
    else
        echo "      libportaudio2 OK"
    fi
fi

# Bibliotecas Python
echo ""
echo "[4/6] Instalando bibliotecas Python..."
$PYTHON -m pip install --upgrade pip --user 2>/dev/null || $PYTHON -m pip install --upgrade pip
$PYTHON -m pip install --user numpy vosk sounddevice soundfile piper-tts 2>/dev/null || \
$PYTHON -m pip install numpy vosk sounddevice soundfile piper-tts
echo "      Bibliotecas instaladas."

# Pastas
echo ""
echo "[5/6] Criando pastas e baixando modelos..."
mkdir -p piper_voices vosk_models

ONNX="piper_voices/pt_BR-faber-medium.onnx"
JSON="piper_voices/pt_BR-faber-medium.onnx.json"
ONNX_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx"
JSON_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json"

download() {
    local url="$1" dest="$2" label="$3"
    if [ -f "$dest" ] && [ "$(stat -c%s "$dest" 2>/dev/null || stat -f%z "$dest" 2>/dev/null)" -gt 1000 ]; then
        echo "      Já existe: $label"
        return
    fi
    echo "      Baixando $label ..."
    if command -v wget >/dev/null 2>&1; then
        wget -q --show-progress -O "$dest" "$url" || curl -L -o "$dest" "$url"
    else
        curl -L -o "$dest" "$url"
    fi
}

download "$ONNX_URL" "$ONNX" "pt_BR-faber-medium.onnx"
download "$JSON_URL" "$JSON" "pt_BR-faber-medium.onnx.json"

VOSK_DIR="vosk_models/vosk-model-small-pt-0.3"
VOSK_ZIP="vosk_models/vosk-model-small-pt-0.3.zip"
VOSK_URL="https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"

if [ -f "$VOSK_DIR/am/final.mdl" ]; then
    echo "      Modelo Vosk já existe."
else
    echo "      Baixando Vosk (~40 MB)..."
    if [ ! -f "$VOSK_ZIP" ]; then
        if command -v wget >/dev/null 2>&1; then
            wget -q --show-progress -O "$VOSK_ZIP" "$VOSK_URL" || curl -L -o "$VOSK_ZIP" "$VOSK_URL"
        else
            curl -L -o "$VOSK_ZIP" "$VOSK_URL"
        fi
    fi
    echo "      Extraindo..."
    unzip -qo "$VOSK_ZIP" -d vosk_models/
    echo "      Modelo Vosk instalado."
fi

# Verificação
echo ""
echo "[6/6] Verificação final"
echo "============================================================"
OK=1
for mod in numpy vosk sounddevice soundfile piper; do
    if $PYTHON -c "import $mod" 2>/dev/null; then
        echo "  [OK] $mod"
    else
        echo "  [FALTA] $mod"
        OK=0
    fi
done

[ -f "$ONNX" ] && echo "  [OK] Piper voz" || { echo "  [FALTA] Piper voz"; OK=0; }
[ -f "$JSON" ] && echo "  [OK] Piper config" || { echo "  [FALTA] Piper config"; OK=0; }
[ -f "$VOSK_DIR/am/final.mdl" ] && echo "  [OK] Vosk português" || { echo "  [FALTA] Vosk português"; OK=0; }

echo ""
if [ "$OK" -eq 1 ]; then
    echo "INSTALAÇÃO CONCLUÍDA COM SUCESSO!"
    echo ""
    echo "Para rodar:"
    echo "  $PYTHON classificador_matrizes.py"
else
    echo "INSTALAÇÃO INCOMPLETA. Corrija os itens [FALTA] acima."
fi
echo ""

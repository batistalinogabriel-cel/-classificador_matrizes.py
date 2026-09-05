# Classificador Automático de Matrizes

Programa em Python para **classificar e transformar matrizes** com:

- **Voz neural** (Piper) — o programa fala os resultados
- **Reconhecimento de voz** (Vosk) — digite números e comandos falando
- **Teclado em tempo real**
- Funciona em **Windows 10/11** e **Ubuntu/Linux**

---

## Classificações suportadas

| # | Classificação |
|---|---------------|
| 1 | Matriz quadrada |
| 2 | Matriz retangular |
| 3 | Matriz nula (zero) |
| 4 | Matriz coluna |
| 5 | Matriz linha |
| 6 | Matriz diagonal |
| 7 | Matriz escalar |
| 8 | Matriz identidade |
| 9 | Matriz unidade |
| 10 | Matriz triangular superior |
| 11 | Matriz triangular inferior |
| 12 | Transposta |
| 13 | Matriz simétrica |
| 14 | Matriz antissimétrica |
| 15 | Matriz normal |

---

## Requisitos

- **Python 3.10+**
- Microfone (opcional; o teclado funciona sem ele)
- ~100 MB livres para os modelos de voz

### Bibliotecas Python

```text
numpy
vosk
sounddevice
soundfile
piper-tts
```

---

## Instalação rápida (Windows)

### 1. Instale o Python

Baixe em: https://www.python.org/downloads/

Na instalação, **marque** a opção:

> ☑ Add python.exe to PATH

### 2. Baixe este repositório

- Botão verde **Code → Download ZIP**, ou
- Clone: `git clone https://github.com/SEU_USUARIO/classificador-matrizes.git`

### 3. Rode o instalador automático

Abra o **PowerShell** na pasta do projeto e execute:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\INSTALAR_TUDO.ps1
```

O script:

1. Encontra o Python
2. Instala as bibliotecas
3. Cria as pastas `piper_voices` e `vosk_models`
4. Baixa o modelo de voz Piper (português)
5. Baixa o modelo Vosk (português)
6. Verifica se tudo ficou correto

### 4. Execute o programa

```powershell
python classificador_matrizes.py
```

---

## Instalação (Ubuntu / Linux)

```bash
sudo apt update
sudo apt install -y python3 python3-pip libportaudio2

python3 -m pip install --upgrade pip
python3 -m pip install numpy vosk sounddevice soundfile piper-tts

# Opcional: script de download dos modelos
bash INSTALAR_TUDO.sh

python3 classificador_matrizes.py
```

---

## Estrutura de pastas

Após a instalação:

```text
classificador-matrizes/
├── classificador_matrizes.py      ← programa principal
├── INSTALAR_TUDO.ps1              ← instalador Windows
├── INSTALAR_TUDO.sh               ← instalador Linux
├── PASSO_A_PASSO_INSTALACAO.txt   ← guia detalhado
├── README.md
├── piper_voices/
│   ├── pt_BR-faber-medium.onnx
│   └── pt_BR-faber-medium.onnx.json
└── vosk_models/
    └── vosk-model-small-pt-0.3/
        ├── am/
        ├── conf/
        └── ...
```

> **Importante:** os modelos **não** estão no GitHub (são grandes).  
> O instalador baixa automaticamente. Se preferir, baixe manualmente (links abaixo).

---

## Download manual dos modelos

### Voz Piper (pt_BR-faber-medium)

Coloque em `piper_voices/`:

- [pt_BR-faber-medium.onnx](https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx)
- [pt_BR-faber-medium.onnx.json](https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json)

### Reconhecimento Vosk (português)

1. Baixe: https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip  
2. Extraia em `vosk_models/`  
3. A pasta final deve ser: `vosk_models/vosk-model-small-pt-0.3/`

Variáveis de ambiente opcionais:

```text
PIPER_VOICE_MODEL   → caminho completo do .onnx
VOSK_MODEL_PATH     → pasta do modelo Vosk
```

---

## Como usar

### Menu principal

| Tecla | Ação |
|-------|------|
| `1` | Informar matriz e analisar (classificações 1–11) |
| `2` | Transformar matriz (transposta, simetria, normalidade) |
| `3` | Sair |
| `M` | Ativar / desativar microfone |

### Entrada por voz (exemplos)

| Fala | Resultado |
|------|-----------|
| `um espaço dois espaço três` | `1 2 3` |
| `dois por três` | `2 3` |
| `um dois três excluir` | `1 2` (apaga o último) |
| `um dois três pronto` | `1 2 3` + Enter |

Comandos de voz:

- Números: zero, um, dois, …, nove  
- `menos`, `vírgula` / `ponto`  
- `espaço` / `por`  
- `apagar` / `excluir`  
- `pronto` / `confirmar` / `enter`

### Dicas

- Fale **depois** que o Piper terminar de falar (o microfone ignora o áudio enquanto a voz está ativa).
- Após uma análise, pressione `R` para repetir o áudio.
- Você pode reutilizar a **transposta** da última matriz informada.

---

## Problemas comuns

| Problema | Solução |
|----------|---------|
| `python` / `py` não reconhecido | Reinstale o Python marcando **Add to PATH** |
| Modelo Piper não encontrado | Rode o instalador ou baixe os `.onnx` manualmente |
| Modelo Vosk não encontrado | Extraia o ZIP em `vosk_models/vosk-model-small-pt-0.3/` |
| Microfone indisponível | Instale `sounddevice` e permita o microfone no sistema |
| Avisos vermelhos no VS Code | Ctrl+Shift+P → **Python: Select Interpreter** |
| Sem áudio no Linux | `sudo apt install libportaudio2` |

---

## Licença e créditos

- **Piper** — síntese de voz neural ([rhasspy/piper](https://github.com/rhasspy/piper))
- **Vosk** — reconhecimento de fala offline ([alphacep/vosk-api](https://github.com/alphacep/vosk-api))
- **NumPy** — operações com matrizes

Este projeto é educacional. Use e adapte livremente.

---

## Publicar no GitHub (para quem for compartilhar)

1. Crie conta em https://github.com  
2. **New repository** → nome: `classificador-matrizes`  
3. **Não** marque “Add README” se já tiver este arquivo  
4. Envie os arquivos:

```bash
git init
git add classificador_matrizes.py INSTALAR_TUDO.ps1 INSTALAR_TUDO.sh PASSO_A_PASSO_INSTALACAO.txt README.md
git commit -m "Versão multiplataforma Windows + Ubuntu"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/classificador-matrizes.git
git push -u origin main
```

Ou use o **GitHub Desktop** / arraste os arquivos pelo site.

**Não envie** as pastas `piper_voices/` e `vosk_models/` (arquivos grandes). O instalador baixa para cada usuário.

[![GitHub](https://img.shields.io/badge/GitHub-551A8B?style=for-the-badge&logo=github&logoColor=white)](https://github.com/)
[![Python](https://img.shields.io/badge/Python-104E8B?style=for-the-badge&logo=python&logoColor=gold)](https://www.python.org/)
[![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)](https://numpy.org/)
[![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=for-the-badge&logo=visual-studio-code&logoColor=white)](https://code.visualstudio.com/)
[![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)](https://ubuntu.com/)

# **CLASSIFICADOR AUTOMÁTICO DE MATRIZES**

<img align="right" height="260px" width="260px" alt="matriz" src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Abacus.png"/>

**Sobre o projeto:**

Programa em **Python** para **classificar e transformar matrizes** de forma interativa, com **voz neural** (Piper) e **reconhecimento de fala** (Vosk). O usuário informa a matriz pelo teclado ou por voz; o sistema analisa, classifica e lê os resultados em português.

O projeto é **multiplataforma**: funciona em **Windows 10/11** e **Ubuntu/Linux**, com o mesmo código-fonte.

## Problema / proposta

> **Como tornar o estudo de classificação de matrizes mais acessível e interativo, combinando cálculo automático, feedback por voz e entrada por microfone?**

---

## Público beneficiado

Estudantes de álgebra linear, professores, pessoas com deficiência visual ou dificuldade de digitação, e qualquer pessoa que queira praticar classificação de matrizes de forma acessível.

<img align="left" height="48px" width="48px" alt="estudante" src="https://cdn-icons-png.flaticon.com/512/3135/3135755.png"/>
<img align="left" height="48px" width="48px" alt="professor" src="https://cdn-icons-png.flaticon.com/512/1995/1995574.png"/>
<img align="left" height="48px" width="48px" alt="acessibilidade" src="https://cdn-icons-png.flaticon.com/512/3976/3976625.png"/>
<img align="left" height="48px" width="48px" alt="matematica" src="https://cdn-icons-png.flaticon.com/512/2103/2103633.png"/>

<br>
<br>
<br>

## Equipe

<img align="right" height="120px" width="120px" alt="dev" src="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExajA3cnB5YTZ0MzFoMHBzamZoM2pud3N5NWp4YjJ1cmV2bjV4NXc0ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/UQVIaWYcyR8pBIDrev/giphy.gif"/>

| Profile | Integrante | Responsabilidades |
| :------ | :--------- | :---------------- |
| [![Gabriel Batista Lino](https://github.com/batistalinogabriel-cel.png?size=60)](https://github.com/batistalinogabriel-cel "Gabriel Batista Lino no GitHub") | **Gabriel Batista Lino** | Desenvolvimento, voz, microfone e multiplataforma |

> Se houver mais integrantes, inclua linhas na tabela no mesmo formato.

## Objetivos

### Objetivo geral

Desenvolver um classificador interativo de matrizes, com saída por voz e entrada por teclado ou microfone, utilizável em Windows e Ubuntu.

### Objetivos específicos

* Classificar matrizes segundo critérios clássicos de álgebra linear (quadrada, diagonal, identidade, etc.)
* Calcular a transposta e verificar simetria, antissimetria e normalidade
* Oferecer feedback falado (Piper) de todas as classificações e resultados
* Permitir preenchimento da matriz por voz (Vosk) com comandos em português
* Garantir funcionamento multiplataforma (Windows + Linux) com o mesmo código
* Facilitar a instalação por meio de scripts automáticos

## Classificações suportadas

| # | Classificação | # | Classificação |
|:-:|:--------------|:-:|:--------------|
| 1 | Matriz quadrada | 9 | Matriz unidade |
| 2 | Matriz retangular | 10 | Triangular superior |
| 3 | Matriz nula (zero) | 11 | Triangular inferior |
| 4 | Matriz coluna | 12 | Transposta |
| 5 | Matriz linha | 13 | Matriz simétrica |
| 6 | Matriz diagonal | 14 | Matriz antissimétrica |
| 7 | Matriz escalar | 15 | Matriz normal |
| 8 | Matriz identidade | | |

## Tecnologias

| Tecnologia | Uso |
|:-----------|:----|
| **Python 3.10+** | Linguagem principal |
| **NumPy** | Operações e testes com matrizes |
| **Piper** | Síntese de voz neural em português |
| **Vosk** | Reconhecimento de fala offline |
| **sounddevice / soundfile** | Captura e reprodução de áudio |
| **termios / msvcrt** | Teclado em tempo real (Linux / Windows) |

## Instalação rápida

### Windows

1. Instale o [Python](https://www.python.org/downloads/) (marque **Add python.exe to PATH**)
2. Baixe ou clone este repositório
3. No PowerShell, na pasta do projeto:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\INSTALAR_TUDO.ps1
python classificador_matrizes.py
```

### Ubuntu / Linux

```bash
chmod +x INSTALAR_TUDO.sh
./INSTALAR_TUDO.sh
python3 classificador_matrizes.py
```

Os instaladores baixam automaticamente:

* bibliotecas Python (`numpy`, `vosk`, `sounddevice`, `soundfile`, `piper-tts`)
* modelo de voz **Piper** (`pt_BR-faber-medium`)
* modelo de reconhecimento **Vosk** (`vosk-model-small-pt-0.3`)

## Como usar

### Menu principal

| Tecla | Ação |
|:-----:|:-----|
| `1` | Informar matriz e analisar (classificações 1 a 11) |
| `2` | Transformar matriz (transposta, simetria, normalidade) |
| `3` | Sair |
| `M` | Ativar / desativar microfone |

### Entrada por voz (exemplos)

| Fala | Resultado |
|:-----|:----------|
| `um espaço dois espaço três` | `1 2 3` |
| `dois por três` | `2 3` |
| `um dois três excluir` | `1 2` (apaga o último) |
| `um dois três pronto` | `1 2 3` + Enter |

**Comandos de voz:** zero–nove · menos · vírgula · espaço / por · apagar / excluir · pronto / confirmar / enter

### Dicas

* Fale **depois** que o Piper terminar (o microfone ignora o áudio enquanto a voz está ativa)
* Após uma análise, pressione **R** para repetir o áudio
* É possível reutilizar a **transposta** da última matriz informada

## Estrutura do projeto

```text
classificador-matrizes/
│
├── classificador_matrizes.py      # Programa principal
├── INSTALAR_TUDO.ps1              # Instalador Windows
├── INSTALAR_TUDO.sh               # Instalador Linux
├── PASSO_A_PASSO_INSTALACAO.txt   # Guia detalhado
├── README.md                      # Documentação principal
├── .gitignore                     # Ignora modelos grandes
│
├── piper_voices/                  # (baixado pelo instalador)
│   ├── pt_BR-faber-medium.onnx
│   └── pt_BR-faber-medium.onnx.json
│
└── vosk_models/                   # (baixado pelo instalador)
    └── vosk-model-small-pt-0.3/
```

> As pastas `piper_voices/` e `vosk_models/` **não** entram no Git (arquivos grandes).  
> O instalador cria e preenche essas pastas em cada máquina.

## Download manual dos modelos

Se preferir não usar o instalador:

**Piper** → pasta `piper_voices/`

* [pt_BR-faber-medium.onnx](https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx)
* [pt_BR-faber-medium.onnx.json](https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json)

**Vosk** → pasta `vosk_models/`

* [vosk-model-small-pt-0.3.zip](https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip) (extrair na pasta)

Variáveis de ambiente opcionais:

```text
PIPER_VOICE_MODEL   → caminho completo do arquivo .onnx
VOSK_MODEL_PATH     → pasta do modelo Vosk
```

## Problemas comuns

| Problema | Solução |
|:---------|:--------|
| `python` / `py` não reconhecido | Reinstale o Python marcando **Add to PATH** |
| Modelo Piper não encontrado | Rode o instalador ou baixe os `.onnx` manualmente |
| Modelo Vosk não encontrado | Extraia o ZIP em `vosk_models/vosk-model-small-pt-0.3/` |
| Microfone indisponível | Permita o microfone no sistema; no Linux: `sudo apt install libportaudio2` |
| Avisos no VS Code (Pylance) | `Ctrl+Shift+P` → **Python: Select Interpreter** |

## Metodologia

O programa segue o fluxo:

**Entrada (teclado ou voz) → Validação → Classificação (NumPy) → Saída escrita + falada (Piper)**

O microfone permanece aberto enquanto estiver ativo; o áudio é descartado enquanto o Piper fala, evitando que a própria voz do programa seja interpretada como comando.

## Créditos

* [Piper](https://github.com/rhasspy/piper) — síntese de voz neural  
* [Vosk](https://github.com/alphacep/vosk-api) — reconhecimento de fala offline  
* [NumPy](https://numpy.org/) — operações com matrizes  

<img align="left" height="80px" width="80px" alt="ok" src="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExaWZ3czZ2b2Jnd2xqZ3JzODYxZm12dXNseXF6dzdhYmFpYnd1emZhdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/lqLda21veZpX5t4Ymb/giphy.gif"/>

<br>
<br>
<br>

## Status

---

**Concluído / em uso**

Versão multiplataforma (Windows + Ubuntu) com classificação 1–15, voz Piper, microfone Vosk e instaladores automáticos.

---

**Classificador Automático de Matrizes**  
Projeto educacional de álgebra linear com acessibilidade por voz.

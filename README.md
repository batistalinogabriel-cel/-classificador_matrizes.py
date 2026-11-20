[![GitHub](https://img.shields.io/badge/GitHub-551A8B?style=for-the-badge&logo=github&logoColor=white)](https://github.com/)
[![Python](https://img.shields.io/badge/Python-104E8B?style=for-the-badge&logo=python&logoColor=gold)](https://www.python.org/)
[![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)](https://numpy.org/)
[![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=for-the-badge&logo=visual-studio-code&logoColor=white)](https://code.visualstudio.com/)
[![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)](https://ubuntu.com/)

# **CLASSIFICADOR AUTOMÁTICO DE MATRIZES**

<img align="right" height="260px" width="240px" alt="matriz" src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Abacus.png"/>

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

<img align="right" height="450px" width="450px" alt="dev" src="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExajA3cnB5YTZ0MzFoMHBzamZoM2pud3N5NWp4YjJ1cmV2bjV4NXc0ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/UQVIaWYcyR8pBIDrev/giphy.gif"/>

| Profile | Integrante 
| :------ | :--------- 
| [![Gabriel Batista Lino](https://github.com/batistalinogabriel-cel.png?size=100)](https://github.com/batistalinogabriel-cel "Gabriel Batista Lino no GitHub") | **Gabriel Batista Lino** 
|[![Alexandre Augusto Heredia](https://github.com/AlexandreAHeredia.png?size=100)](https://github.com/AlexandreAHeredia "Alexandre Augusto Heredia no GitHub")| **Alexandre Augusto Heredia**   
|[![Rafael de Souza Schmoeller](https://github.com/rafaelsouzasch-stack.png?size=100)](https://github.com/rafaelsouzasch-stack "GRafael de Souza Schmoeller") | **Rafael de Souza Schmoeller**  
|[![Rafael Victor Zanette Nunes](https://github.com/xnunes-ia.png?size=100)](https://github.com/xnunes-ia "Rafael Victor Zanette Nunes no GitHub") | **Rafael Victor Zanette Nunes**
|[![Felipe Gabriel Vacari](https://github.com/FelipeVacar1.png?size=100)](https://github.com/FelipeVacar1 "Felipe Gabriel Vacari no GitHub")| **Felipe Gabriel Vacari**   

## Objetivos

### Objetivo geral

Desenvolver um classificador interativo de matrizes, com saída por voz e entrada por teclado ou microfone, utilizável em Windows e Ubuntu.

### Objetivos específicos

* Classificar matrizes segundo critérios clássicos de álgebra linear (quadrada, diagonal, identidade, etc.)
* Calcular a transposta e verificar simetria, antissimetria e normalidade
* Oferecer feedback falado (Piper) de todas as classificações e resultados
* Permitir preenchimento da matriz por voz (Vosk) com comandos em português
* Evitar eco do sintetizador (microfone mudo durante a fala + modo fone)
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

### Teclas globais (qualquer tela)

| Tecla | Voz | Ação |
|:-----:|:----|:-----|
| `Esc` | silêncio, parar, chega, calar, cortar | Corta a fala na hora |
| `A` | rápido, acelerar | Voz mais rápida |
| `D` | devagar, lento | Voz mais lenta |
| `M` | microfone, eme | Liga ou desliga o microfone |
| `F` | fone, fones, efe | Liga ou desliga o modo fone |
| `H` | ajuda, agá | Repete a ajuda das teclas |
| `R` | repetir, repete, repita | Repete o último áudio (quando a opção existe) |

A velocidade vai de **0,50×** a **2,50×**, em passos de **0,10**. O padrão é **1,25×**. O menu mostra o valor atual.

`Esc` durante a narração corta a fala e não perde a tecla seguinte.

### Modo fone e anti-eco

| Modo fone | Comportamento |
|:----------|:--------------|
| **DESATIVADO** (padrão, alto-falante) | Microfone mudo enquanto o Piper fala; pausa de cerca de 0,85 s depois; filtro de eco residual por cerca de 1 s |
| **ATIVADO** (fone de ouvido) | Microfone também mudo durante a fala; pausa curta (cerca de 0,15 s); **sem** filtro de eco residual |

Fale os comandos **nas pausas**, depois que a voz terminar.

### Entrada por voz

| Fala | Resultado |
|:-----|:----------|
| `um espaço dois espaço três` | `1 2 3` |
| `dois por três` | `2 3` (`por` = espaço) |
| `vinte e três` | `23` |
| `cento e vinte espaço cinco` | `120 5` |
| `um dois três excluir` | `1 2` |
| `um dois três pronto` | `1 2 3` + Enter |
| `fone` | Alterna o modo fone |
| `repetir` | Repete o último áudio |
| `parar` | Corta a fala |

Números falados vão de **0 a 999** (`dez`, `vinte e três`, `cento e vinte`, `duzentos`…).

### Vocabulário

**Números e edição**

| Fala | Tecla |
|:-----|:------|
| zero … nove, ou o número por extenso até 999 | dígitos |
| menos / negativo | `-` |
| vírgula / ponto | `,` |
| espaço / por | espaço |
| apagar / excluir / voltar | backspace |
| pronto / confirmar / enter | Enter |

**Operadores**

| Fala | Símbolo |
|:-----|:--------|
| mais / soma | `+` |
| vezes / multiplica | `*` |
| dividido / divide | `/` |
| igual / resultado | `=` |

Palavras de preenchimento (`por favor`, `então`, `agora`, `ok`, `sim`) são ignoradas. Palavra fora da gramática vira `[unk]` e também é ignorada.

### Dicas

* Fale **depois** que o Piper terminar.
* Com fone, pressione **F** ou diga **fone**.
* Pressione **H** (ou diga **ajuda**) para ouvir as teclas.
* A explicação de como digitar a matriz só é falada na **primeira** matriz da sessão.
* Depois da análise, pressione **R** ou diga **repetir**.
* Dá para reutilizar a transposta da última matriz informada.

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
├── video_explicativo.pptx.zip     # vídeo explicativo
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
| Eco no alto-falante | Deixe o **modo fone DESATIVADO**, ou use fone e pressione **F** / diga **fone** |
| A voz não para | Pressione **Esc** ou diga **parar** |
| Comando ignorado | Espere o Piper terminar e fale na pausa |
| “Velocidade não muda” | A versão instalada do Piper não tem `SynthesisConfig`; atualize `piper-tts` |
| Avisos no VS Code (Pylance) | `Ctrl+Shift+P` → **Python: Select Interpreter** |

## Metodologia

O programa segue o fluxo:

**Entrada (teclado ou voz) → Validação → Classificação (NumPy) → Saída escrita + falada (Piper)**

Controle de áudio e microfone:

1. Enquanto o Piper fala, o microfone fica mudo (não envia áudio ao Vosk).
2. Depois da fala há uma pausa curta (modo fone) ou maior (alto-falante).
3. No alto-falante, um filtro de cerca de 1 s ignora texto parecido com o que o Piper acabou de dizer.
4. No modo fone esse filtro fica desligado, para não rejeitar a fala real.
5. A gramática do Vosk só aceita o vocabulário do programa; o resto vira `[unk]` e é descartado.
6. Frases de controle (fone, microfone, ajuda, velocidade, parar) não são lidas de volta.
7. Teclas vindas da voz não disparam um segundo feedback falado de cada dígito.
8. Áudios já sintetizados (mesma frase e mesma velocidade) ficam em cache.
9. Cortar a fala descarta o que ainda estava na fila ou em síntese.
10. Comparações de matriz usam tolerância pequena; matriz normal com inteiros é conferida em aritmética exata.

## Créditos

* [Piper](https://github.com/rhasspy/piper) — síntese de voz neural  
* [Vosk](https://github.com/alphacep/vosk-api) — reconhecimento de fala offline  
* [NumPy](https://numpy.org/) — operações com matrizes  


<br>
<br>
<br>

<img align="left" height="94px" width="94px" alt="Warpnet" src="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExaWZ3czZ2b2Jnd2xqZ3JzODYxZm12dXNseXF6dzdhYmFpYnd1emZhdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/lqLda21veZpX5t4Ymb/giphy.gif"/>

<div align="center">
</div>

##    Status 
---
## Status

---

**Concluído / em uso**

Versão multiplataforma (Windows + Ubuntu) com:

* classificações 1–15
* voz Piper + microfone Vosk
* números falados de 0 a 999
* velocidade da voz ajustável (A / D)
* corte da fala (Esc)
* modo fone (F ou “fone”)
* anti-eco (microfone mudo durante a fala)
* ajuda de teclas (H)
* cache de áudio e instaladores automáticos

---

**Classificador Automático de Matrizes**
Projeto educacional de álgebra linear com acessibilidade por voz.

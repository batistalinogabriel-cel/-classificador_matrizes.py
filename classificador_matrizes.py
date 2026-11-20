import os
import sys
import wave
import queue
import tempfile
import shutil
import subprocess
import threading
import json
import time
import unicodedata
import platform
import atexit
import codecs
import collections
import io
import signal
import numpy as np

# ============================================================
# DETECÇÃO DO SISTEMA OPERACIONAL
# ============================================================
SISTEMA = platform.system()
WINDOWS = SISTEMA == "Windows"
LINUX = SISTEMA == "Linux"

if WINDOWS:
    import msvcrt
else:
    import termios
    import tty
    import select

try:
    from piper import PiperVoice
except ImportError:
    print("ERRO: a biblioteca piper-tts não está instalada.")
    print("Instale com:")
    if WINDOWS:
        print("    py -m pip install piper-tts")
    else:
        print("    python3 -m pip install piper-tts")
    sys.exit(1)

try:
    from piper import SynthesisConfig
except ImportError:
    SynthesisConfig = None

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    import vosk
except ImportError:
    vosk = None

NOME_ARQUIVO_VOZ = "pt_BR-faber-medium.onnx"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _candidatos_modelo_voz():
    """
    Lista de locais onde o modelo de voz Piper pode estar, em ordem
    de prioridade. Assim o programa funciona em qualquer computador,
    independentemente do nome do usuário ou de onde o projeto foi copiado.
    """
    candidatos = []

    variavel_ambiente = os.environ.get("PIPER_VOICE_MODEL", "")
    if variavel_ambiente:
        candidatos.append(variavel_ambiente)

    candidatos.append(os.path.join(BASE_DIR, "piper_voices", NOME_ARQUIVO_VOZ))
    candidatos.append(os.path.join(BASE_DIR, NOME_ARQUIVO_VOZ))
    candidatos.append(os.path.join(os.path.expanduser("~"), "piper_voices", NOME_ARQUIVO_VOZ))
    candidatos.append(os.path.join(os.path.expanduser("~"), NOME_ARQUIVO_VOZ))
    return candidatos


PASTAS_IGNORADAS_NA_BUSCA = {
    ".cache", ".config", ".local", ".git", "node_modules", "__pycache__",
}


def _buscar_na_home(aceita, profundidade_max=6, tempo_max=5.0):
    """
    Último recurso para achar um modelo: percorre a HOME, mas com limite de
    profundidade e de tempo, para o programa não travar na abertura em
    computadores com muitas pastas.
    aceita(raiz, diretorios, arquivos) devolve o caminho achado ou None.
    """
    home = os.path.expanduser("~")
    nivel_home = home.rstrip(os.sep).count(os.sep)
    limite = time.monotonic() + tempo_max
    try:
        for raiz, diretorios, arquivos in os.walk(home):
            if time.monotonic() > limite:
                return None
            if raiz.count(os.sep) - nivel_home >= profundidade_max:
                diretorios[:] = []
            else:
                diretorios[:] = [d for d in diretorios if d not in PASTAS_IGNORADAS_NA_BUSCA]
            achado = aceita(raiz, diretorios, arquivos)
            if achado:
                return achado
    except Exception:
        pass
    return None


def _achar_voz_piper(raiz, diretorios, arquivos):
    for arquivo in arquivos:
        if arquivo.startswith("pt_BR") and arquivo.endswith(".onnx"):
            return os.path.join(raiz, arquivo)
    return None


def _achar_modelo_vosk(raiz, diretorios, arquivos):
    for d in diretorios:
        if d.startswith("vosk-model") and os.path.isfile(os.path.join(raiz, d, "am", "final.mdl")):
            return os.path.join(raiz, d)
    return None


def localizar_modelo_voz():
    for caminho in _candidatos_modelo_voz():
        if caminho and os.path.isfile(caminho):
            return caminho

    # Último recurso: procura qualquer voz Piper em português dentro da HOME.
    return _buscar_na_home(_achar_voz_piper)


MODELO_VOZ = localizar_modelo_voz()

# Velocidade da voz (quanto maior, mais rápida a fala). Ajustável com A / D.
# O Piper recebe length_scale = 1 / velocidade (1,25x -> 0,8).
VELOCIDADE_VOZ = 1.25
VELOCIDADE_MIN = 0.50
VELOCIDADE_MAX = 2.50
PASSO_VELOCIDADE = 0.10

VOLUME_VOZ = 1.0
LARGURA = 65

if not MODELO_VOZ:
    print("ERRO: modelo de voz Piper em português não encontrado.")
    print("Procurado em:")
    for caminho in _candidatos_modelo_voz():
        print(f"  - {caminho}")
    print()
    print("Solução: baixe uma voz Piper em português (ex.: pt_BR-faber-medium)")
    print("e coloque o arquivo .onnx (e o .onnx.json que vem junto) em uma das")
    print("pastas acima — por exemplo ~/piper_voices/ — ou defina a variável de")
    print("ambiente PIPER_VOICE_MODEL apontando para o caminho completo do .onnx.")
    sys.exit(1)

if not os.path.isfile(MODELO_VOZ + ".json"):
    print(f"AVISO: arquivo '{os.path.basename(MODELO_VOZ)}.json' não encontrado ao lado do modelo.")
    print("O Piper pode falhar ao carregar a voz sem esse arquivo de configuração.\n")

print("Carregando voz neural...")
try:
    VOZ = PiperVoice.load(MODELO_VOZ)
except Exception as erro:
    print(f"ERRO ao carregar o Piper: {erro}")
    sys.exit(1)
print("Voz neural carregada.\n")

velocidade_voz = VELOCIDADE_VOZ
lock_velocidade = threading.Lock()


def config_voz_atual(velocidade=None):
    """Monta a configuração do Piper (velocidade vigente, se não for informada)."""
    if SynthesisConfig is None:
        return None
    if velocidade is None:
        with lock_velocidade:
            velocidade = velocidade_voz
    return SynthesisConfig(
        volume=VOLUME_VOZ,
        length_scale=1.0 / velocidade
    )


fila_voz = queue.Queue()

# Cada fala entra na fila com o número da "geração" em que foi pedida.
# Cortar a fala incrementa a geração: o que já estava em síntese não toca.
geracao_fala = 0
lock_geracao = threading.Lock()


def _geracao_fala():
    with lock_geracao:
        return geracao_fala


def _nova_geracao_fala():
    global geracao_fala
    with lock_geracao:
        geracao_fala += 1
        return geracao_fala


def _enfileirar_fala(texto):
    fila_voz.put((texto, _geracao_fala()))


processo_atual = None
lock_processo = threading.Lock()
stream_reproducao = None  # usado com sounddevice

# Guarda a última matriz digitada pelo usuário (para reaproveitar a transposta)
ULTIMA_MATRIZ = None

# A instrução de digitação só é falada por extenso na primeira matriz.
INSTRUCOES_MATRIZ_FALADAS = False

# Controle de gravação/repetição de áudio de uma operação
GRAVANDO_FALA = False
BUFFER_FALA = []
ULTIMO_AUDIO = []


# Falas já sintetizadas (texto + velocidade -> bytes do WAV), das mais
# recentes para as mais antigas. Dígitos, "espaço", avisos e a repetição do
# áudio (tecla R) deixam de esperar o Piper sintetizar de novo.
LIMITE_CACHE_AUDIO = 48 * 1024 * 1024
cache_audio = collections.OrderedDict()
bytes_cache_audio = 0
lock_cache_audio = threading.Lock()


def _guardar_no_cache(chave, wav):
    global bytes_cache_audio
    if len(wav) > LIMITE_CACHE_AUDIO // 4:
        return
    with lock_cache_audio:
        if chave in cache_audio:
            return
        cache_audio[chave] = wav
        bytes_cache_audio += len(wav)
        while bytes_cache_audio > LIMITE_CACHE_AUDIO and cache_audio:
            _, removido = cache_audio.popitem(last=False)
            bytes_cache_audio -= len(removido)


def gerar_audio(texto):
    """Sintetiza o texto e devolve os bytes de um WAV (sem arquivo temporário)."""
    with lock_velocidade:
        velocidade = velocidade_voz
    chave = (texto, velocidade if SynthesisConfig is not None else None)

    with lock_cache_audio:
        wav = cache_audio.get(chave)
        if wav is not None:
            cache_audio.move_to_end(chave)
            return wav

    config = config_voz_atual(velocidade)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        if config is None:
            VOZ.synthesize_wav(texto, wav_file)
        else:
            VOZ.synthesize_wav(texto, wav_file, syn_config=config)
    wav = buffer.getvalue()
    _guardar_no_cache(chave, wav)
    return wav


# Após o Piper terminar: pausa + filtro de eco.
COOLDOWN_ECO_SEGUNDOS = 0.45
# Sem fone: microfone fica surdo este tempo APÓS cada fala (anti-eco alto-falante).
SURDO_APOS_FALA_SEGUNDOS = 0.85
# Com fone: surdo bem mais curto (quase não há eco).
SURDO_APOS_FALA_FONE = 0.15
# Por quanto tempo rejeitar texto parecido com o que o Piper falou.
# (Curta: o período surdo já cobre o eco; uma janela longa rejeitava o
# usuário dizendo "dois" logo depois de o menu falar "dois".)
JANELA_ECO_POS_FALA = 1.0

# False = alto-falante (anti-eco, surdo mais longo após a fala).
# True  = fone: também NÃO reconhece durante a fala do Piper (zero eco);
#         após a fala, volta a ouvir mais rápido.
# Em ambos os modos o microfone fica mudo enquanto o Piper fala.
modo_fone = False
lock_modo_fone = threading.Lock()
pedido_interromper_audio = threading.Event()
# Ligado enquanto o Piper está tocando uma fala (o microfone fica mudo).
audio_piper_falando = threading.Event()

# Texto que o Piper está falando / falou recentemente.
texto_piper_atual = ""
ultimo_texto_piper = ""
ultimo_texto_piper_ate = 0.0
# Até este instante (monotonic) o microfone ignora reconhecimento (anti-eco).
microfone_surdo_ate = 0.0
lock_texto_piper = threading.Lock()


def normalizar_frase(texto):
    forma = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in forma if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def _definir_texto_piper(texto):
    global texto_piper_atual, ultimo_texto_piper, ultimo_texto_piper_ate
    texto = (texto or "").strip()
    with lock_texto_piper:
        texto_piper_atual = texto
        if texto:
            ultimo_texto_piper = texto
            ultimo_texto_piper_ate = time.monotonic() + JANELA_ECO_POS_FALA


def _marcar_microfone_surdo(segundos=None):
    """Impede reconhecimento por alguns instantes (anti-eco)."""
    global microfone_surdo_ate
    if segundos is None:
        with lock_modo_fone:
            fone = modo_fone
        segundos = SURDO_APOS_FALA_FONE if fone else SURDO_APOS_FALA_SEGUNDOS
    with lock_texto_piper:
        microfone_surdo_ate = max(microfone_surdo_ate, time.monotonic() + segundos)


def _microfone_esta_surdo():
    with lock_texto_piper:
        return time.monotonic() < microfone_surdo_ate


def _textos_filtro_eco():
    """Textos atuais e recentes do Piper usados para detectar eco."""
    agora = time.monotonic()
    with lock_texto_piper:
        textos = []
        if texto_piper_atual:
            textos.append(texto_piper_atual)
        if ultimo_texto_piper and agora <= ultimo_texto_piper_ate:
            textos.append(ultimo_texto_piper)
        return textos


def _parece_eco_do_piper(texto_reconhecido):
    """
    True se o que o Vosk ouviu parece ser o próprio Piper
    (eco do alto-falante), e não a voz do usuário.

    Com modo fone ATIVO não há eco acústico no microfone:
    este filtro é desligado para não rejeitar a fala real do usuário
    (ex.: Piper falou "dois" e o usuário também diz "dois").
    """
    with lock_modo_fone:
        if modo_fone:
            return False

    rec = normalizar_frase(texto_reconhecido)
    if not rec:
        return False
    for falado_raw in _textos_filtro_eco():
        falado = normalizar_frase(falado_raw)
        if not falado:
            continue
        if rec == falado:
            return True
        if f" {rec} " in f" {falado} " or f" {falado} " in f" {rec} ":
            return True
        palavras_rec = set(rec.split())
        palavras_fal = set(falado.split())
        if not palavras_rec:
            continue
        inter = palavras_rec & palavras_fal
        if inter and (len(inter) / len(palavras_rec) >= 0.4):
            return True
        if len(palavras_rec) <= 3 and palavras_rec <= palavras_fal:
            return True
    return False


def reproduzir_audio(wav, geracao=None):
    """
    Reproduz um áudio WAV (bytes) usando sounddevice + soundfile (multiplataforma).
    Pode ser interrompido a qualquer momento por interromper_audio_atual().
    """
    global processo_atual, stream_reproducao, texto_piper_atual, ultimo_texto_piper_ate
    interrompido = False

    def cancelada():
        if pedido_interromper_audio.is_set():
            return True
        return geracao is not None and geracao != _geracao_fala()

    try:
        pedido_interromper_audio.clear()
        if cancelada():
            interrompido = True
            return
        audio_piper_falando.set()

        if sd is not None and sf is not None:
            try:
                dados, taxa = sf.read(io.BytesIO(wav), dtype="float32")
                duracao = max(0.05, float(len(dados)) / float(taxa))
                sd.play(dados, taxa, blocking=False)
                with lock_processo:
                    stream_reproducao = True
                fim = time.monotonic() + duracao + 0.15
                while time.monotonic() < fim:
                    if cancelada():
                        interrompido = True
                        try:
                            sd.stop()
                        except Exception:
                            pass
                        break
                    time.sleep(0.025)
                if not interrompido:
                    try:
                        sd.wait()
                    except Exception:
                        pass
            finally:
                with lock_processo:
                    stream_reproducao = None
        else:
            comando = _detectar_comando_reproducao()
            if comando is None:
                print("\nERRO: nenhum método de reprodução de áudio disponível.")
                return
            processo = None
            caminho = None
            try:
                # Os players externos precisam de um arquivo.
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as arquivo:
                    arquivo.write(wav)
                    caminho = arquivo.name
                processo = subprocess.Popen(
                    comando + [caminho],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                with lock_processo:
                    processo_atual = processo
                while processo.poll() is None:
                    if cancelada():
                        interrompido = True
                        try:
                            processo.terminate()
                        except Exception:
                            pass
                        break
                    time.sleep(0.03)
                try:
                    processo.wait(timeout=0.3)
                except Exception:
                    pass
            finally:
                with lock_processo:
                    if processo_atual is processo:
                        processo_atual = None
                _remover_arquivo(caminho)
    finally:
        if not interrompido and not cancelada():
            time.sleep(COOLDOWN_ECO_SEGUNDOS)
        audio_piper_falando.clear()
        with lock_texto_piper:
            texto_piper_atual = ""
            if ultimo_texto_piper:
                ultimo_texto_piper_ate = time.monotonic() + JANELA_ECO_POS_FALA
        # Período surdo: evita eco do alto-falante virar comando
        _marcar_microfone_surdo()


def _detectar_comando_reproducao():
    """
    Fallback para Linux quando sounddevice/soundfile não estão instalados.
    Não é usado no Windows.
    """
    if WINDOWS:
        return None
    candidatos = [
        ["aplay", "-q"],
        ["paplay"],
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
        ["mpv", "--no-video", "--really-quiet"],
        ["mpg123", "-q"],
    ]
    for comando in candidatos:
        if shutil.which(comando[0]):
            return comando
    return None


def interromper_audio_atual():
    """Corta imediatamente qualquer áudio do Piper em reprodução."""
    global processo_atual, stream_reproducao
    _nova_geracao_fala()
    pedido_interromper_audio.set()
    with lock_processo:
        tocando = stream_reproducao is not None
        if tocando and sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
            stream_reproducao = None
        processo = processo_atual
        processo_atual = None
    if processo is not None:
        try:
            if processo.poll() is None:
                processo.terminate()
                try:
                    processo.wait(timeout=0.2)
                except Exception:
                    try:
                        processo.kill()
                    except Exception:
                        pass
        except Exception:
            pass
    # Libera o estado "falando" na hora (sem esperar cooldown)
    audio_piper_falando.clear()


def limpar_fila():
    while True:
        try:
            fila_voz.get_nowait()
            fila_voz.task_done()
        except queue.Empty:
            return


def _remover_arquivo(caminho):
    if caminho and os.path.exists(caminho):
        try:
            os.remove(caminho)
        except OSError:
            pass


def trabalhador_voz():
    while True:
        item = fila_voz.get()
        if item is None:
            fila_voz.task_done()
            return
        texto, geracao = item
        try:
            if geracao != _geracao_fala():
                continue
            wav = gerar_audio(texto)
            if geracao != _geracao_fala():
                continue
            reproduzir_audio(wav, geracao)
        except Exception as erro:
            print(f"\nErro na síntese de voz: {erro}")
        finally:
            fila_voz.task_done()


thread_voz = threading.Thread(target=trabalhador_voz, daemon=True)
thread_voz.start()


def falar(texto, imprimir=False):
    if imprimir:
        print(texto)
    if GRAVANDO_FALA:
        BUFFER_FALA.append(texto)
    _definir_texto_piper(texto)
    _enfileirar_fala(texto)


def falar_somente(texto):
    if GRAVANDO_FALA:
        BUFFER_FALA.append(texto)
    _definir_texto_piper(texto)
    _enfileirar_fala(texto)


def falar_interrompendo(texto, imprimir=False):
    """
    Corta imediatamente o áudio em reprodução e qualquer item
    pendente na fila, falando apenas o texto atual.
    Usado na digitação em tempo real e na navegação do menu.
    """
    limpar_fila()
    interromper_audio_atual()
    if imprimir:
        print(texto)
    _definir_texto_piper(texto)
    _enfileirar_fala(texto)


def cortar_fala():
    """Silencia tudo: áudio tocando, fila e falas ainda em síntese."""
    limpar_fila()
    interromper_audio_atual()
    _definir_texto_piper("")


def esperar_voz():
    fila_voz.join()


def esperar_voz_cortavel():
    """
    Espera a fala terminar, mas sem prender o teclado (só para a thread principal).
    Esc corta a fala. Qualquer outra tecla também corta e é devolvida
    ao próximo leitor, para o que o usuário digitou não se perder.
    """
    while fila_voz.unfinished_tasks > 0:
        tecla = proxima_tecla(0.05)
        if tecla is None:
            continue
        if tecla != "\x1b":
            teclas_devolvidas.append((tecla, ultima_tecla_silenciosa))
        cortar_fala()
        return


def iniciar_captura_audio():
    """
    Começa a gravar, em ordem, todos os textos enviados por
    falar()/falar_somente(), para permitir repetição posterior.
    """
    global GRAVANDO_FALA, BUFFER_FALA
    GRAVANDO_FALA = True
    BUFFER_FALA = []


def parar_captura_audio():
    """
    Encerra a gravação e guarda o resultado em ULTIMO_AUDIO.
    """
    global GRAVANDO_FALA, ULTIMO_AUDIO
    GRAVANDO_FALA = False
    ULTIMO_AUDIO = list(BUFFER_FALA)


def repetir_ultimo_audio():
    """
    Reenfileira, na mesma ordem, todo o áudio gravado da
    última operação e aguarda a reprodução terminar.
    """
    if not ULTIMO_AUDIO:
        falar_interrompendo("Não há áudio para repetir.", imprimir=True)
        esperar_voz_cortavel()
        return

    limpar_fila()
    interromper_audio_atual()

    for texto in ULTIMO_AUDIO:
        _enfileirar_fala(texto)

    esperar_voz_cortavel()


def oferecer_repeticao_audio():
    """
    Após uma operação (análise ou transformação), oferece ao
    usuário a opção de repetir o áudio quantas vezes quiser
    antes de voltar ao menu.
    """
    while True:
        print()
        linha_fina()
        print("  [R]  Repetir áudio")
        print("  [Qualquer outra tecla]  Voltar ao menu")
        linha_fina()

        falar_somente("R repete. Outra tecla volta ao menu.")

        tecla = ler_tecla_menu()

        if tecla.lower() == "r":
            print()
            print("Repetindo áudio...")
            repetir_ultimo_audio()
        else:
            return


DIGITOS = {
    "0": "zero", "1": "um", "2": "dois", "3": "três", "4": "quatro",
    "5": "cinco", "6": "seis", "7": "sete", "8": "oito", "9": "nove"
}


def numero_para_texto(valor):
    valor = float(valor)
    if np.isnan(valor):
        return "indefinido"
    if np.isinf(valor):
        return "infinito" if valor > 0 else "-infinito"
    if abs(valor) < 1e-9 or abs(valor - round(valor)) < 1e-9:
        return str(int(round(valor)))
    texto = f"{valor:.4f}".rstrip("0").rstrip(".")
    if texto in ("", "0", "-0"):
        # Não mostrar zero para um valor que não é zero (ex.: 0,00004).
        texto = f"{valor:.15f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def numero_para_fala(valor):
    texto = numero_para_texto(valor)
    if texto in ("indefinido", "infinito"):
        return texto
    if texto == "-infinito":
        return "menos infinito"
    resultado = []
    for caractere in texto:
        if caractere == "-":
            resultado.append("menos")
        elif caractere == ",":
            resultado.append("vírgula")
        elif caractere in DIGITOS:
            resultado.append(DIGITOS[caractere])
    return " ".join(resultado)


# ============================================================
# MICROFONE (RECONHECIMENTO DE VOZ) — MULTIPLATAFORMA
# ============================================================
TAXA_VOSK = 16000
MODELO_MICROFONE = None
MODELO_VOSK = None
MICROFONE_DISPONIVEL = False
MICROFONE_ATIVO = False
ERRO_MICROFONE = ""

# Procura automaticamente o modelo, inclusive dentro da HOME e da pasta do programa.
CAMINHOS_MODELO_VOSK = [
    os.environ.get("VOSK_MODEL_PATH", ""),
    os.path.join(BASE_DIR, "vosk_models", "vosk-model-small-pt-0.3"),
    os.path.join(os.path.expanduser("~"), "vosk_models", "vosk-model-small-pt-0.3"),
    os.path.join(os.path.expanduser("~"), "vosk-model-small-pt-0.3"),
]

for caminho_modelo in CAMINHOS_MODELO_VOSK:
    if caminho_modelo and os.path.isdir(caminho_modelo):
        MODELO_MICROFONE = caminho_modelo
        break

# Último recurso: procura diretórios vosk-model* dentro da HOME.
if MODELO_MICROFONE is None:
    MODELO_MICROFONE = _buscar_na_home(_achar_modelo_vosk)

if vosk is None:
    ERRO_MICROFONE = "A biblioteca Vosk não está instalada."
elif MODELO_MICROFONE is None:
    ERRO_MICROFONE = "Modelo Vosk em português não encontrado."
elif sd is None:
    ERRO_MICROFONE = "A biblioteca sounddevice não está instalada."
else:
    try:
        vosk.SetLogLevel(-1)
        MODELO_VOSK = vosk.Model(MODELO_MICROFONE)
        MICROFONE_DISPONIVEL = True
    except Exception as erro:
        ERRO_MICROFONE = f"Não foi possível carregar o modelo Vosk: {erro}"

if not MICROFONE_DISPONIVEL:
    print("\nAVISO: reconhecimento por microfone indisponível.")
    print(f"Motivo: {ERRO_MICROFONE}")
    print("Instalação recomendada:")
    if WINDOWS:
        print("    py -m pip install numpy vosk sounddevice soundfile piper-tts")
    else:
        print("    python3 -m pip install numpy vosk sounddevice soundfile piper-tts")
        print("    (no Ubuntu pode ser necessário: sudo apt install libportaudio2)")
    print("Modelo esperado: vosk_models/vosk-model-small-pt-0.3 (ao lado do programa)\n")

fila_teclas_voz = queue.Queue()
# Textos reconhecidos pelo Vosk (callback só enfileira; outra thread processa)
fila_frases_reconhecidas = queue.Queue()
thread_microfone = None
thread_frases = None
parar_microfone_evento = threading.Event()
parar_microfone_evento.set()
# Impede processar_texto_reconhecido reentrante (loop de eco)
lock_processar_voz = threading.Lock()

# ------------------------------------------------------------
# Vocabulário de voz
# Todas as chaves ficam sem acento e em minúsculas: a frase reconhecida
# é normalizada antes da consulta ("Três" -> "tres").
# ------------------------------------------------------------
UNIDADES_FALADAS = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
    "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
}
ESPECIAIS_FALADOS = {
    "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
    "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezasseis": 16,
    "dezessete": 17, "dezassete": 17, "dezoito": 18, "dezenove": 19,
    "dezanove": 19,
}
DEZENAS_FALADAS = {
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
    "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90,
}
CENTENAS_FALADAS = {
    "cem": 100, "cento": 100,
    "duzentos": 200, "duzentas": 200, "trezentos": 300, "trezentas": 300,
    "quatrocentos": 400, "quatrocentas": 400, "quinhentos": 500,
    "quinhentas": 500, "seiscentos": 600, "seiscentas": 600,
    "setecentos": 700, "setecentas": 700, "oitocentos": 800,
    "oitocentas": 800, "novecentos": 900, "novecentas": 900,
}
NUMEROS_FALADOS = {}
for _tabela in (UNIDADES_FALADAS, ESPECIAIS_FALADOS, DEZENAS_FALADAS, CENTENAS_FALADAS):
    NUMEROS_FALADOS.update(_tabela)

# Palavras que viram uma tecla. Os números (de zero a novecentos e noventa e
# nove) são montados por frase_para_teclas(), não por esta tabela.
PALAVRA_PARA_TECLA = {
    "zero": "0", "um": "1", "uma": "1", "dois": "2", "duas": "2",
    "tres": "3", "quatro": "4", "cinco": "5", "seis": "6",
    "sete": "7", "oito": "8", "nove": "9",
    "menos": "-", "negativo": "-", "subtrai": "-", "subtrair": "-",
    "virgula": ",", "ponto": ",",
    "espaco": " ", "por": " ",
    "apaga": "\x7f", "apagar": "\x7f", "apague": "\x7f", "voltar": "\x7f",
    "excluir": "\x7f",
    "confirma": "\r", "confirmar": "\r", "confirme": "\r",
    "enter": "\r", "pronto": "\r", "terminar": "\r", "terminado": "\r",
    "finalizar": "\r", "finaliza": "\r",
    "vezes": "*", "vez": "*", "multiplica": "*", "multiplicar": "*",
    "dividido": "/", "divide": "/", "dividir": "/",
    "mais": "+", "soma": "+", "somar": "+",
    "igual": "=", "resultado": "=",
    # Letras (nome falado da letra) e comandos que equivalem a uma tecla.
    "r": "R", "erre": "R", "ere": "R", "repetir": "R", "repete": "R",
    "repita": "R",
    "f": "F", "efe": "F", "efes": "F", "fone": "F", "fones": "F",
    "eme": "M", "microfone": "M",
    "aga": "H", "ajuda": "H",
    "rapido": "A", "acelerar": "A", "acelera": "A",
    "devagar": "D", "lento": "D", "desacelerar": "D",
    "silencio": "\x1b", "calar": "\x1b", "cala": "\x1b", "parar": "\x1b",
    "pare": "\x1b", "cortar": "\x1b", "escape": "\x1b", "chega": "\x1b",
}

PALAVRAS_IGNORADAS = {
    "digite", "digitar", "numero", "numeros",
    "elemento", "elementos", "linha", "linhas", "coluna", "colunas",
    "o", "a", "e", "de", "da", "do",
    "favor", "porfavor", "entao", "agora", "faca",
    "ok", "okay", "certo", "sim", "nao",
    "[unk]",
}

# Comandos que só mexem no programa: não vale a pena ler a frase de volta.
TECLAS_DE_CONTROLE = {"R", "F", "M", "H", "A", "D", "\x1b"}

# Forma com acento, como costuma estar no vocabulário do modelo Vosk.
FORMAS_ACENTUADAS = {
    "tres": "três", "virgula": "vírgula", "espaco": "espaço",
    "efe": "éfe", "efes": "éfes", "aga": "agá", "erre": "errê",
    "silencio": "silêncio", "rapido": "rápido", "entao": "então",
    "numero": "número", "numeros": "números", "faca": "faça",
    "nao": "não",
}


def _montar_gramatica_vosk():
    """
    Lista de palavras que o Vosk pode reconhecer. "[unk]" faz o que não é
    comando virar "desconhecido", em vez de ser forçado para o número ou
    comando mais parecido (principal causa de comandos falsos).
    """
    palavras = set(PALAVRA_PARA_TECLA) | set(NUMEROS_FALADOS) | {"e"}
    for chave in list(palavras):
        if chave in FORMAS_ACENTUADAS:
            palavras.add(FORMAS_ACENTUADAS[chave])
    return sorted(palavras) + ["[unk]"]


GRAMATICA_VOSK = _montar_gramatica_vosk()


def normalizar_palavra(palavra):
    forma_decomposta = unicodedata.normalize("NFKD", palavra)
    return "".join(c for c in forma_decomposta if not unicodedata.combining(c)).lower()


def limpar_texto_vosk(texto):
    """Remove os marcadores "[unk]" (palavra fora da gramática)."""
    return " ".join(
        p for p in (texto or "").split() if p.lower() != "[unk]"
    )


def _depois_do_e(palavras, i):
    """Índice depois de um "e" opcional que liga duas partes de um número."""
    if i < len(palavras) and palavras[i] == "e":
        return i + 1
    return i


def _somar_unidade(palavras, i, valor):
    """Soma uma unidade de 1 a 9 ("vinte e três"), com ou sem o "e"."""
    j = _depois_do_e(palavras, i)
    if j < len(palavras):
        unidade = UNIDADES_FALADAS.get(palavras[j])
        if unidade:
            return valor + unidade, j + 1
    return valor, i


def _ler_numero_falado(palavras, i):
    """
    Lê um número falado a partir de palavras[i] e devolve (valor, próximo i).
    "vinte e três" -> 23, "cento e cinco" -> 105, "dez" -> 10.
    Duas unidades seguidas continuam separadas ("dois três" -> 2 e 3).
    """
    palavra = palavras[i]
    i += 1

    if palavra in CENTENAS_FALADAS:
        valor = CENTENAS_FALADAS[palavra]
        j = _depois_do_e(palavras, i)
        if j < len(palavras):
            proxima = palavras[j]
            if proxima in ESPECIAIS_FALADOS:
                return valor + ESPECIAIS_FALADOS[proxima], j + 1
            if proxima in DEZENAS_FALADAS:
                valor += DEZENAS_FALADAS[proxima]
                return _somar_unidade(palavras, j + 1, valor)
        return _somar_unidade(palavras, i, valor)

    if palavra in DEZENAS_FALADAS:
        return _somar_unidade(palavras, i, DEZENAS_FALADAS[palavra])

    if palavra in ESPECIAIS_FALADOS:
        return ESPECIAIS_FALADOS[palavra], i

    return UNIDADES_FALADAS[palavra], i


def frase_para_teclas(texto):
    """
    Converte uma frase reconhecida na lista de teclas que ela representa.
    Palavras desconhecidas e de preenchimento são descartadas sem
    quebrar as expressões ("dois por três" -> 2, espaço, 3).
    """
    palavras = [normalizar_palavra(p) for p in (texto or "").split()]
    palavras = [p for p in palavras if p]

    # "por favor" é educação, não o separador "por".
    limpas = []
    i = 0
    while i < len(palavras):
        if palavras[i] == "por" and i + 1 < len(palavras) and palavras[i + 1] in ("favor", "porfavor"):
            i += 2
            continue
        limpas.append(palavras[i])
        i += 1
    palavras = limpas

    teclas = []
    i = 0
    while i < len(palavras):
        palavra = palavras[i]

        # "mais rápido" / "mais devagar" são comandos de velocidade, não o sinal de mais.
        if palavra == "mais" and i + 1 < len(palavras) and palavras[i + 1] in ("rapido", "devagar", "lento"):
            i += 1
            continue

        if palavra in NUMEROS_FALADOS:
            valor, i = _ler_numero_falado(palavras, i)
            teclas.extend(str(valor))
            continue

        if palavra in PALAVRAS_IGNORADAS:
            i += 1
            continue

        if palavra in PALAVRA_PARA_TECLA:
            teclas.append(PALAVRA_PARA_TECLA[palavra])

        i += 1
    return teclas


def limpar_fila_teclas_voz():
    while True:
        try:
            fila_teclas_voz.get_nowait()
            fila_teclas_voz.task_done()
        except queue.Empty:
            return


def processar_texto_reconhecido(texto, barge_in=False):
    """
    Transforma uma frase reconhecida em eventos de entrada.

    Frases sem nenhum comando útil são descartadas sem cortar a fala.

    Barge-in: corta a leitura na hora e executa o comando SEM esperar
    confirmação falada (resposta imediata).

    Reconhecimento normal: confirma a frase uma vez, depois injeta teclas.
    Comandos de controle (velocidade, ajuda, letras) não são lidos de volta.
    """
    texto = limpar_texto_vosk(texto)
    if not texto:
        return

    teclas = frase_para_teclas(texto)
    if not teclas:
        print(f"[MIC] Ouvi, mas não é um comando: {texto}")
        return

    if _parece_eco_do_piper(texto):
        print(f"[MIC] Ignorado (eco do Piper): {texto}")
        return

    if not lock_processar_voz.acquire(blocking=False):
        return

    try:
        print(f"[MIC] Reconhecido: {texto}")

        # Sempre corta a fala atual
        limpar_fila()
        interromper_audio_atual()
        _definir_texto_piper("")

        so_controle = all(t in TECLAS_DE_CONTROLE for t in teclas)

        if barge_in or so_controle:
            # Executa na hora (sem ler de novo a frase)
            for tecla in teclas:
                fila_teclas_voz.put(("v", tecla))
            return

        # Fluxo normal: confirma a frase uma vez, depois teclas silenciosas
        print(f"[VOZ] {texto}")
        _definir_texto_piper(texto)
        _enfileirar_fala(texto)
        esperar_voz()

        for tecla in teclas:
            fila_teclas_voz.put(("v", tecla))
    finally:
        lock_processar_voz.release()


def trabalhador_frases_reconhecidas():
    """
    Processa frases fora do callback do sounddevice.
    Evita bloquear a captura de áudio com esperar_voz().
    """
    while True:
        item = fila_frases_reconhecidas.get()
        if item is None:
            fila_frases_reconhecidas.task_done()
            return
        try:
            if isinstance(item, tuple):
                texto, barge_in = item[0], bool(item[1]) if len(item) > 1 else False
            else:
                texto, barge_in = item, False
            processar_texto_reconhecido(texto, barge_in=barge_in)
        except Exception as erro:
            print(f"\n[MIC] erro ao processar frase: {erro}")
        finally:
            fila_frases_reconhecidas.task_done()


thread_frases = threading.Thread(
    target=trabalhador_frases_reconhecidas,
    daemon=True,
    name="FrasesVoz"
)
thread_frases.start()


def enfileirar_frase_reconhecida(texto, barge_in=False):
    """Chamado pelo callback: só enfileira, não bloqueia."""
    texto = limpar_texto_vosk(texto).strip()
    if not texto:
        return
    # Sem fone: ignora tudo no período surdo (anti-eco)
    if not barge_in and _microfone_esta_surdo():
        return
    if _parece_eco_do_piper(texto):
        print(f"[MIC] Ignorado (eco): {texto}")
        return
    if lock_processar_voz.locked():
        return
    fila_frases_reconhecidas.put((texto, barge_in))


def criar_reconhecedor(taxa):
    # Gramática com números, letras e comandos, mais "[unk]" para tudo o
    # que não for comando (veja GRAMATICA_VOSK).
    try:
        return vosk.KaldiRecognizer(
            MODELO_VOSK, taxa,
            json.dumps(GRAMATICA_VOSK, ensure_ascii=False)
        )
    except Exception:
        return vosk.KaldiRecognizer(MODELO_VOSK, taxa)


def _filtro_passa_baixa(taxa_origem, taps=63):
    """FIR passa-baixa (janela de Hamming) que corta acima de ~7,2 kHz."""
    corte = 0.45 * TAXA_VOSK / float(taxa_origem)
    n = np.arange(taps) - (taps - 1) / 2.0
    h = 2.0 * corte * np.sinc(2.0 * corte * n) * np.hamming(taps)
    return (h / np.sum(h)).astype(np.float32)


class Reamostrador16k:
    """
    Converte blocos de áudio mono da taxa do microfone para 16 kHz.

    Antes de reduzir a taxa, aplica um filtro passa-baixa; sem ele, ruído
    agudo (acima de 8 kHz) se dobra para dentro da faixa da voz e atrapalha
    o Vosk. Guarda o estado entre blocos, então não há emendas a cada 100 ms.
    """

    def __init__(self, taxa_origem):
        self.taxa = int(taxa_origem)
        self.filtro = _filtro_passa_baixa(self.taxa) if self.taxa > TAXA_VOSK else None
        self.reiniciar()

    def reiniciar(self):
        tamanho = 0 if self.filtro is None else len(self.filtro) - 1
        self.cauda = np.zeros(tamanho, dtype=np.float32)
        self.ultimo = 0.0
        self.pos = 0.0

    def processar(self, bloco):
        x = np.asarray(bloco, dtype=np.float32).reshape(-1)
        if self.taxa == TAXA_VOSK or len(x) == 0:
            return x

        if self.filtro is not None:
            ext = np.concatenate([self.cauda, x])
            y = np.convolve(ext, self.filtro, mode="valid")
            self.cauda = ext[len(ext) - len(self.cauda):]
        else:
            y = x

        passo = self.taxa / float(TAXA_VOSK)
        limite = len(y) - 1 - self.pos
        if limite < 0:
            self.pos -= len(y)
            self.ultimo = float(y[-1])
            return np.array([], dtype=np.float32)

        n = int(limite // passo) + 1
        posicoes = self.pos + passo * np.arange(n)
        com_anterior = np.concatenate([[self.ultimo], y])
        saida = np.interp(posicoes + 1.0, np.arange(len(com_anterior)), com_anterior)

        self.pos = self.pos + passo * n - len(y)
        self.ultimo = float(y[-1])
        return saida.astype(np.float32)


def float32_para_pcm16(audio_float):
    """Converte float32 [-1, 1] para PCM int16 bytes."""
    audio_float = np.clip(audio_float, -1.0, 1.0)
    pcm = (audio_float * 32767.0).astype(np.int16)
    return pcm.tobytes()


def encontrar_microfone():
    """
    Seleciona o dispositivo de entrada adequado.
    - Linux: preferência por alsa_input, nunca .monitor
    - Windows: qualquer dispositivo com max_input_channels > 0
               (preferência pela entrada padrão)
    """
    if sd is None:
        return None, "sounddevice não disponível"

    try:
        dispositivos = sd.query_devices()
    except Exception as erro:
        return None, f"Não foi possível listar dispositivos: {erro}"

    candidatos = []
    for i, dev in enumerate(dispositivos):
        nome = str(dev.get("name", ""))
        max_in = int(dev.get("max_input_channels", 0) or 0)
        if max_in <= 0:
            continue
        # Nunca selecionar monitor de saída
        if ".monitor" in nome.lower():
            continue
        candidatos.append((i, nome, max_in, dev))

    if not candidatos:
        return None, "Nenhum dispositivo de entrada válido encontrado."

    # Preferência Linux: alsa_input
    if LINUX:
        for i, nome, max_in, dev in candidatos:
            if "alsa_input" in nome.lower():
                return i, None
        # Se não houver alsa_input explícito, usa o default de entrada
        try:
            default_in = sd.default.device[0]
            if default_in is not None and default_in >= 0:
                for i, nome, max_in, dev in candidatos:
                    if i == default_in:
                        return i, None
        except Exception:
            pass
        return candidatos[0][0], None

    # Windows: preferir dispositivo padrão de entrada
    try:
        default_in = sd.default.device[0]
        if default_in is not None and default_in >= 0:
            for i, nome, max_in, dev in candidatos:
                if i == default_in:
                    return i, None
    except Exception:
        pass

    return candidatos[0][0], None


def trabalhador_microfone_sounddevice():
    """
    Captura o microfone via sounddevice (Windows e Ubuntu).
    Abre na taxa nativa, reamostra para 16 kHz mono e entrega ao Vosk.

    Enquanto o Piper fala (e um instante depois) o microfone fica mudo:
    nada é reconhecido, o que evita que o eco vire comando.
    """
    global MICROFONE_ATIVO, ERRO_MICROFONE

    try:
        indice, erro = encontrar_microfone()
        if indice is None:
            raise RuntimeError(erro or "Dispositivo de microfone não encontrado.")

        info = sd.query_devices(indice, "input")
        nome = str(info.get("name", f"dispositivo {indice}"))
        taxa_nativa = int(float(info.get("default_samplerate", 48000)))
        max_canais = int(info.get("max_input_channels", 1) or 1)
        canais = 1 if max_canais < 1 else min(2, max_canais)

        # ~100 ms de áudio por bloco → reconhecimento mais responsivo
        blocksize = max(256, int(taxa_nativa * 0.1))

        with lock_modo_fone:
            fone = modo_fone
        print(f"[MIC] Sistema: {SISTEMA}")
        print(f"[MIC] Dispositivo escolhido: {nome}")
        print(f"[MIC] Índice: {indice}")
        print(f"[MIC] Canais: {canais}")
        print(f"[MIC] Taxa nativa: {taxa_nativa} Hz")
        print(f"[MIC] Taxa Vosk: {TAXA_VOSK} Hz")
        print("[MIC] Durante a voz do Piper: microfone mudo (sem eco)")
        if fone:
            print("[MIC] Modo fone: ATIVADO — sem filtro de eco residual; fale nas pausas")
        else:
            print("[MIC] Modo fone: DESATIVADO — anti-eco de alto-falante ativo")
        print("      Pressione F no menu para alternar modo fone.")
        print("[MIC] Abrindo captura...")

        reconhecedor = criar_reconhecedor(TAXA_VOSK)
        reamostrador = Reamostrador16k(taxa_nativa)
        def _flush_vosk():
            try:
                if hasattr(reconhecedor, "Reset"):
                    reconhecedor.Reset()
                else:
                    reconhecedor.FinalResult()
            except Exception:
                pass

        def callback(indata, frames, tempo, status):
            if status:
                print(f"\n[MIC] status: {status}")

            try:
                audio = np.asarray(indata, dtype=np.float32)
                if audio.ndim > 1:
                    mono_nativo = np.mean(audio, axis=1)
                else:
                    mono_nativo = audio

                # ----- Enquanto o Piper fala: NUNCA reconhece (zero eco) -----
                # Vale para alto-falante e para modo fone.
                if audio_piper_falando.is_set():
                    _flush_vosk()
                    reamostrador.reiniciar()
                    return

                # ----- Piper parado -----
                # Período surdo após a fala (eco residual / ring do ambiente)
                if _microfone_esta_surdo():
                    _flush_vosk()
                    reamostrador.reiniciar()
                    return

                audio_16k = reamostrador.processar(mono_nativo)
                if len(audio_16k) == 0:
                    return
                pcm = float32_para_pcm16(audio_16k)

                if reconhecedor.AcceptWaveform(pcm):
                    texto = limpar_texto_vosk(
                        json.loads(reconhecedor.Result()).get("text", "")
                    ).strip()
                    if not texto:
                        return
                    if _parece_eco_do_piper(texto):
                        print(f"[MIC] Ignorado (eco residual): {texto}")
                        return
                    enfileirar_frase_reconhecida(texto, barge_in=False)
            except Exception as erro_cb:
                print(f"\n[MIC] erro no callback: {erro_cb}")

        with sd.InputStream(
            device=indice,
            samplerate=taxa_nativa,
            channels=canais,
            dtype="float32",
            blocksize=blocksize,
            callback=callback,
        ):
            MICROFONE_ATIVO = True
            print("[MIC] CAPTURA ABERTA COM SUCESSO.")
            print("[MIC] Microfone ouvindo (inclusive durante a voz).")
            parar_microfone_evento.wait()

            try:
                final = json.loads(reconhecedor.FinalResult()).get("text", "").strip()
                if final and not _parece_eco_do_piper(final):
                    enfileirar_frase_reconhecida(final, barge_in=False)
            except Exception:
                pass

    except Exception as erro:
        ERRO_MICROFONE = str(erro)
        print(f"\nERRO REAL DO MICROFONE: {erro}")
    finally:
        MICROFONE_ATIVO = False


def trabalhador_microfone():
    """Ponto de entrada único — sempre sounddevice."""
    global ERRO_MICROFONE
    if sd is None:
        ERRO_MICROFONE = "sounddevice não está disponível."
        return
    trabalhador_microfone_sounddevice()


def alternar_modo_fone():
    """
    Alterna o modo fone.
    Em ambos: microfone mudo enquanto o Piper fala.
    Com fone: sem filtro de 'eco residual' (não rejeita sua fala real)
              e pausa curta após a voz.
    Sem fone: filtro de eco do alto-falante + pausa maior.
    """
    global modo_fone
    with lock_modo_fone:
        modo_fone = not modo_fone
        ativo = modo_fone
    if ativo:
        print("[MIC] Modo fone: sem filtro de eco residual; fale nas pausas após a voz.")
        falar_interrompendo("Modo fone ativado.")
    else:
        print("[MIC] Modo fone desativado: anti-eco de alto-falante ativo.")
        falar_interrompendo("Modo fone desativado.")


def alternar_microfone():
    global MICROFONE_ATIVO, thread_microfone, ERRO_MICROFONE
    if not MICROFONE_DISPONIVEL:
        falar_interrompendo("Microfone indisponível. " + ERRO_MICROFONE, imprimir=True)
        return

    if MICROFONE_ATIVO:
        parar_microfone_evento.set()
        MICROFONE_ATIVO = False
        # Espera o stream fechar, para não haver dois abertos ao reativar.
        if thread_microfone is not None and thread_microfone.is_alive():
            thread_microfone.join(timeout=1.0)
        limpar_fila_teclas_voz()
        falar_interrompendo("Microfone desativado.")
        return

    limpar_fila_teclas_voz()
    ERRO_MICROFONE = ""
    parar_microfone_evento.clear()
    thread_microfone = threading.Thread(
        target=trabalhador_microfone,
        daemon=True,
        name="MicrofoneVosk"
    )
    thread_microfone.start()

    limite = time.monotonic() + 3.0
    while time.monotonic() < limite:
        if MICROFONE_ATIVO:
            break
        if not thread_microfone.is_alive():
            break
        time.sleep(0.03)

    if MICROFONE_ATIVO:
        print("[MIC] Fale depois que a voz terminar.")
        falar_interrompendo("Microfone ativado.")
    else:
        parar_microfone_evento.set()
        mensagem = ERRO_MICROFONE or "não foi possível abrir o dispositivo de entrada."
        falar_interrompendo("Falha ao ativar o microfone. " + mensagem, imprimir=True)


def testar_microfone():
    if not MICROFONE_DISPONIVEL:
        falar_interrompendo("Microfone indisponível. " + ERRO_MICROFONE, imprimir=True)
        esperar_voz()
        return

    estava_ativo = MICROFONE_ATIVO
    if not estava_ativo:
        alternar_microfone()
        esperar_voz()
    if not MICROFONE_ATIVO:
        return

    limpar_fila_teclas_voz()
    falar_interrompendo("Teste. Diga um, dois ou três. Depois faça uma pausa.")
    esperar_voz()

    fim = time.monotonic() + 8
    reconhecido = None
    while time.monotonic() < fim:
        try:
            reconhecido = fila_teclas_voz.get(timeout=0.2)
            fila_teclas_voz.task_done()
            break
        except queue.Empty:
            pass

    if reconhecido is None:
        falar_interrompendo(
            "Não reconheci sua voz. O microfone está aberto, "
            "mas o Vosk não recebeu uma palavra válida."
        )
    else:
        if isinstance(reconhecido, tuple) and len(reconhecido) == 2:
            reconhecido = reconhecido[1]
        falar_interrompendo(f"Reconheci {DIGITOS.get(reconhecido, reconhecido)}.")
    esperar_voz()

    if not estava_ativo:
        alternar_microfone()


def texto_status_microfone():
    if not MICROFONE_DISPONIVEL:
        return "INDISPONÍVEL"
    return "ATIVADO" if MICROFONE_ATIVO else "DESATIVADO"


def texto_status_microfone_falado():
    if not MICROFONE_DISPONIVEL:
        return "indisponível"
    return "ativado" if MICROFONE_ATIVO else "desativado"


# ============================================================
# TECLADO MULTIPLATAFORMA
# ============================================================

# True quando a última tecla veio do reconhecimento de voz.
# Nesse caso o feedback falado por dígito NÃO deve ser repetido
# (a frase inteira já foi lida pelo Piper em processar_texto_reconhecido).
ultima_tecla_silenciosa = False


def _normalizar_item_fila_voz(item):
    """
    Converte item da fila de voz em (caractere, silencioso).
    Teclas da voz vêm como ("v", tecla); teclado físico é str.
    """
    global ultima_tecla_silenciosa
    if isinstance(item, tuple) and len(item) == 2 and item[0] == "v":
        ultima_tecla_silenciosa = True
        return item[1]
    # Item antigo sem marcador (compatibilidade)
    if isinstance(item, str):
        ultima_tecla_silenciosa = True
        return item
    ultima_tecla_silenciosa = False
    return item


# Teclas já lidas e ainda não consumidas: (tecla, veio_da_voz).
teclas_devolvidas = collections.deque()

_buffer_teclado = collections.deque()
_decodificador_utf8 = codecs.getincrementaldecoder("utf-8")(errors="ignore")
_termios_original = None


def ligar_terminal_imediato():
    """
    Linux: mantém o terminal em modo cbreak durante todo o programa
    (sem eco e sem esperar Enter). O que o usuário digita enquanto a voz
    fala fica guardado e é lido em seguida, em vez de aparecer na tela
    e ser descartado.
    """
    global _termios_original
    if WINDOWS or _termios_original is not None or not sys.stdin.isatty():
        return
    fd = sys.stdin.fileno()
    _termios_original = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSANOW)


def desligar_terminal_imediato():
    global _termios_original
    if WINDOWS or _termios_original is None:
        return
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _termios_original)
    except Exception:
        pass
    _termios_original = None


atexit.register(desligar_terminal_imediato)


def _ler_texto_stdin(espera):
    """Lê o que estiver disponível no teclado (Linux) sem usar o buffer do sys.stdin."""
    fd = sys.stdin.fileno()
    prontos, _, _ = select.select([fd], [], [], espera)
    if not prontos:
        return ""
    dados = os.read(fd, 256)
    if not dados:
        time.sleep(espera)
        return ""
    return _decodificador_utf8.decode(dados)


def _tecla_fisica_linux(espera):
    """
    Devolve um caractere, "" para sequências ignoradas (setas, Home...)
    ou None se nada foi digitado dentro do tempo de espera.
    """
    if not _buffer_teclado:
        _buffer_teclado.extend(_ler_texto_stdin(espera))
    if not _buffer_teclado:
        return None

    tecla = _buffer_teclado.popleft()
    if tecla != "\x1b":
        return tecla

    # Esc sozinho corta a fala; Esc seguido de [ ou O é uma tecla especial.
    if not _buffer_teclado:
        _buffer_teclado.extend(_ler_texto_stdin(0.03))
    if _buffer_teclado and _buffer_teclado[0] in "[O":
        _buffer_teclado.popleft()
        while True:
            if not _buffer_teclado:
                _buffer_teclado.extend(_ler_texto_stdin(0.03))
                if not _buffer_teclado:
                    break
            final = _buffer_teclado.popleft()
            if "@" <= final <= "~":
                break
        return ""
    return "\x1b"


def _tecla_fisica_windows(espera):
    fim = time.monotonic() + espera
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            # Teclas especiais (setas etc.) geram dois caracteres
            if ch in ("\x00", "\xe0"):
                msvcrt.getwch()
                return ""
            return ch
        if time.monotonic() >= fim:
            return None
        time.sleep(0.01)


def _tecla_fisica(espera):
    if WINDOWS:
        return _tecla_fisica_windows(espera)
    return _tecla_fisica_linux(espera)


def proxima_tecla(espera=None):
    """
    Próxima tecla, na ordem: devolvidas, voz (tecla virtual) e teclado.
    Sem espera, bloqueia até chegar uma tecla; com espera, devolve None
    se nada chegar a tempo.
    """
    global ultima_tecla_silenciosa
    limite = None if espera is None else time.monotonic() + espera
    while True:
        if teclas_devolvidas:
            tecla, silenciosa = teclas_devolvidas.popleft()
            ultima_tecla_silenciosa = silenciosa
            return tecla

        try:
            item = fila_teclas_voz.get_nowait()
            return _normalizar_item_fila_voz(item)
        except queue.Empty:
            pass

        tecla = _tecla_fisica(0.05)
        if tecla:
            ultima_tecla_silenciosa = False
            return tecla

        if limite is not None and time.monotonic() >= limite:
            return None


class LeitorTeclado:
    def __init__(self):
        self.ativo = False

    def iniciar(self):
        ligar_terminal_imediato()
        self.ativo = True

    def restaurar(self):
        # O terminal só volta ao normal quando o programa termina.
        self.ativo = False

    def ler_tecla(self):
        """
        Aguarda uma tecla do teclado OU uma "tecla virtual" vinda
        do reconhecimento de voz (quando o microfone está ativo),
        o que chegar primeiro.
        """
        return proxima_tecla()


AJUDA_TECLAS = (
    "Teclas disponíveis a qualquer momento. "
    "Escape corta a fala. "
    "Tecla A aumenta a velocidade da voz. Tecla D diminui. "
    "Tecla M liga ou desliga o microfone. "
    "Tecla F liga ou desliga o modo fone. "
    "Tecla H repete esta ajuda."
)


def ajustar_velocidade(direcao):
    """direcao > 0 acelera a voz; direcao < 0 deixa a voz mais lenta."""
    global velocidade_voz
    if SynthesisConfig is None:
        falar_interrompendo(
            "Esta versão do Piper não permite mudar a velocidade.", imprimir=True
        )
        return

    with lock_velocidade:
        antiga = velocidade_voz
        nova = antiga + direcao * PASSO_VELOCIDADE
        nova = round(min(VELOCIDADE_MAX, max(VELOCIDADE_MIN, nova)), 2)
        velocidade_voz = nova

    if nova != antiga:
        mensagem = "Mais rápido." if direcao > 0 else "Mais devagar."
    else:
        mensagem = "Velocidade máxima." if direcao > 0 else "Velocidade mínima."
    print(f"\n[VOZ] Velocidade: {nova:.2f}x")
    falar_interrompendo(mensagem)


def falar_ajuda():
    with lock_modo_fone:
        fone = "ativado" if modo_fone else "desativado"
    print()
    print("Teclas: [Esc] corta a fala | [A] voz mais rápida | [D] voz mais lenta | "
          "[M] microfone | [F] modo fone | [H] esta ajuda")
    falar_interrompendo(
        AJUDA_TECLAS
        + f" Microfone {texto_status_microfone_falado()}. Modo fone {fone}."
    )


def tratar_tecla_global(tecla):
    """
    Teclas que valem em qualquer tela (menus e digitação).
    Retorna True quando a tecla foi tratada aqui.
    """
    if tecla in ("m", "M"):
        alternar_microfone()
    elif tecla in ("f", "F"):
        alternar_modo_fone()
    elif tecla in ("a", "A"):
        ajustar_velocidade(+1)
    elif tecla in ("d", "D"):
        ajustar_velocidade(-1)
    elif tecla in ("h", "H"):
        falar_ajuda()
    elif tecla == "\x1b":
        cortar_fala()
    else:
        return False
    return True


def ler_tecla_menu():
    leitor = LeitorTeclado()
    try:
        leitor.iniciar()
        while True:
            tecla = leitor.ler_tecla()
            if tecla == "\x03":
                raise KeyboardInterrupt
            if tratar_tecla_global(tecla):
                continue
            return tecla
    finally:
        leitor.restaurar()


def validar_token_numero(token):
    token = token.replace(",", ".")
    if token in ("", "-", "."):
        return None
    try:
        valor = float(token)
    except ValueError:
        return None
    # Mais de 308 dígitos vira infinito, que não dá para analisar.
    return valor if np.isfinite(valor) else None


def aplicar_tecla(texto, tecla, em_linha):
    """
    Aplica uma tecla de edição ao texto que está sendo digitado.
    em_linha=True: linha da matriz (vários elementos separados por espaço).
    em_linha=False: um único número.

    Devolve (novo_texto, tela, fala):
      tela = o que escrever no terminal ("\b \b" apaga um caractere);
      fala = o que dizer (None se nada). Teclas vindas da voz não falam.
    """
    if tecla in ("\x7f", "\b"):
        if texto:
            return texto[:-1], "\b \b", "apagado"
        return texto, "", "Não há nada para apagar."

    if tecla == " " and em_linha:
        if texto and not texto.endswith(" "):
            return texto + " ", " ", "espaço"
        return texto, "", ("Já há um espaço." if texto else "Digite primeiro um número.")

    if tecla in DIGITOS:
        return texto + tecla, tecla, DIGITOS[tecla]

    # Elemento em edição (a linha inteira, no modo de um número só).
    atual = texto.split(" ")[-1] if em_linha else texto

    if tecla == "-":
        if atual == "":
            return texto + "-", "-", "menos"
        if em_linha:
            return texto, "", "O sinal de menos deve estar no início do elemento."
        return texto, "", "Tecla não permitida."

    if tecla in (".", ","):
        tem_digito = any(c in DIGITOS for c in atual)
        tem_separador = "." in atual or "," in atual
        if tem_digito and not tem_separador:
            return texto + tecla, tecla, "vírgula"
        if em_linha:
            if not tem_digito:
                return texto, "", "Digite primeiro um número."
            return texto, "", "Este elemento já possui separador decimal."
        if tem_separador:
            return texto, "", "O número já possui separador decimal."

    return texto, "", "Tecla não permitida."


def escrever_na_tela(trecho):
    if trecho:
        sys.stdout.write(trecho)
        sys.stdout.flush()


def ler_linha_matriz(numero_linha, quantidade_colunas):
    while True:
        print()
        print(f"Linha {numero_linha} de {quantidade_colunas} elementos.")
        print("Digite os elementos separados por espaços:")
        print(f"(Microfone: {texto_status_microfone()} — pressione M para alternar)")
        print("> ", end="", flush=True)

        # Não espera a fala terminar: o teclado já está sendo lido e a
        # primeira tecla digitada corta o aviso.
        falar_somente(f"Linha {numero_linha}.")

        leitor = LeitorTeclado()
        texto = ""

        try:
            leitor.iniciar()
            while True:
                tecla = leitor.ler_tecla()

                if tecla == "\x03":
                    raise KeyboardInterrupt

                if tratar_tecla_global(tecla):
                    continue

                if tecla in ("\r", "\n"):
                    print()
                    tokens = texto.strip().split()

                    if len(tokens) != quantidade_colunas:
                        if len(tokens) < quantidade_colunas:
                            diferenca = quantidade_colunas - len(tokens)
                            if diferenca == 1:
                                mensagem = "Falta 1 elemento."
                            else:
                                mensagem = f"Faltam {diferenca} elementos."
                        else:
                            diferenca = len(tokens) - quantidade_colunas
                            if diferenca == 1:
                                mensagem = "Há 1 elemento a mais."
                            else:
                                mensagem = f"Há {diferenca} elementos a mais."
                        falar_interrompendo(mensagem, imprimir=True)
                        break

                    valores = []
                    invalido = False
                    for token in tokens:
                        valor = validar_token_numero(token)
                        if valor is None:
                            falar_interrompendo(
                                f"O valor {token} não é um número válido."
                            )
                            print(f"O valor {token} não é um número válido.")
                            invalido = True
                            break
                        valores.append(valor)

                    if invalido:
                        break

                    return valores

                texto, tela, fala = aplicar_tecla(texto, tecla, em_linha=True)
                escrever_na_tela(tela)
                if fala and not ultima_tecla_silenciosa:
                    falar_interrompendo(fala)
        finally:
            leitor.restaurar()


def ler_numero_tempo_real(mensagem, falado=None):
    while True:
        leitor = LeitorTeclado()
        valor_digitado = ""
        print()
        print(mensagem)
        print(f"(Microfone: {texto_status_microfone()} — pressione M para alternar)")
        print("> ", end="", flush=True)
        leitor.iniciar()
        falar_interrompendo(falado or mensagem)
        try:
            while True:
                tecla = leitor.ler_tecla()

                if tecla == "\x03":
                    raise KeyboardInterrupt

                if tratar_tecla_global(tecla):
                    continue

                if tecla in ("\r", "\n"):
                    valor = validar_token_numero(valor_digitado)
                    if valor is None:
                        if not ultima_tecla_silenciosa:
                            falar_interrompendo("Digite um número válido.")
                        continue
                    print()
                    return valor

                valor_digitado, tela, fala = aplicar_tecla(valor_digitado, tecla, em_linha=False)
                escrever_na_tela(tela)
                if fala and not ultima_tecla_silenciosa:
                    falar_interrompendo(fala)
        finally:
            leitor.restaurar()


def ler_inteiro_positivo(mensagem):
    falado = mensagem
    while True:
        valor = ler_numero_tempo_real(mensagem, falado)
        if valor > 0 and float(valor).is_integer():
            return int(valor)
        falado = "Digite um número inteiro maior que zero."


def informar_matriz():
    """
    Pergunta linhas, colunas e cada linha da matriz.
    Atualiza ULTIMA_MATRIZ com o resultado, para que outras
    partes do programa possam reaproveitar a transposta dela.
    """
    global ULTIMA_MATRIZ, INSTRUCOES_MATRIZ_FALADAS

    linhas = ler_inteiro_positivo("Digite o número de linhas.")
    colunas = ler_inteiro_positivo("Digite o número de colunas.")

    print()
    print(f"A matriz possui {linhas} linhas e {colunas} colunas.")
    print("Digite uma linha inteira por vez.")
    print("Use espaços para separar os elementos.")
    print("Exemplo: 1 2 3")

    # A explicação completa só é falada na primeira matriz da sessão.
    if not INSTRUCOES_MATRIZ_FALADAS:
        INSTRUCOES_MATRIZ_FALADAS = True
        falar_interrompendo(
            "Digite uma linha por vez, separando os elementos com espaço. "
            "Por exemplo: um, espaço, dois, espaço, três."
        )

    matriz = []
    for i in range(linhas):
        matriz.append(ler_linha_matriz(i + 1, colunas))

    resultado = np.array(matriz, dtype=float)
    print()
    print("Matriz preenchida.")

    ULTIMA_MATRIZ = resultado
    return resultado


# Tolerância das comparações. Os elementos são números digitados e as
# comparações estruturais (simetria, diagonal...) não fazem contas, então a
# tolerância relativa é minúscula: com a padrão do NumPy (1e-5), 100000 e
# 100000,5 seriam considerados iguais.
TOL_ABS = 1e-8
TOL_REL = 1e-12


def _iguais(a, b):
    # Diferenças enormes podem estourar o float (vira infinito = "diferente").
    with np.errstate(over="ignore", invalid="ignore"):
        return bool(np.allclose(a, b, rtol=TOL_REL, atol=TOL_ABS))


def eh_quadrada(matriz):
    return matriz.shape[0] == matriz.shape[1]


def eh_retangular(matriz):
    return matriz.shape[0] != matriz.shape[1]


def eh_nula(matriz):
    return _iguais(matriz, 0)


def eh_coluna(matriz):
    return matriz.shape[1] == 1


def eh_linha(matriz):
    return matriz.shape[0] == 1


def eh_diagonal(matriz):
    return eh_quadrada(matriz) and _iguais(matriz, np.diag(np.diag(matriz)))


def eh_escalar(matriz):
    if not eh_diagonal(matriz):
        return False
    diagonal = np.diag(matriz)
    return _iguais(diagonal, diagonal[0])


def eh_identidade(matriz):
    return eh_quadrada(matriz) and _iguais(matriz, np.eye(matriz.shape[0]))


def eh_triangular_superior(matriz):
    return eh_quadrada(matriz) and _iguais(matriz, np.triu(matriz))


def eh_triangular_inferior(matriz):
    return eh_quadrada(matriz) and _iguais(matriz, np.tril(matriz))


def eh_simetrica(matriz):
    return eh_quadrada(matriz) and _iguais(matriz, matriz.T)


def eh_antissimetrica(matriz):
    return eh_quadrada(matriz) and _iguais(matriz.T, -matriz)


def eh_normal(matriz):
    """
    Matriz normal (real): A @ A.T == A.T @ A.

    Com elementos inteiros a conta é feita em inteiros do Python, sem erro
    de arredondamento. Com decimais, a tolerância acompanha a precisão do
    ponto flutuante e o tamanho dos elementos (uma tolerância fixa aceitaria
    como normal, por exemplo, [[1000, 1], [0, 1000]]).
    """
    if not eh_quadrada(matriz) or not np.all(np.isfinite(matriz)):
        return False

    if np.array_equal(matriz, np.round(matriz)):
        inteira = np.array([[int(v) for v in linha] for linha in matriz], dtype=object)
        return bool(np.all(inteira @ inteira.T == inteira.T @ inteira))

    n = matriz.shape[0]
    maior = float(np.max(np.abs(matriz)))
    tolerancia = TOL_ABS + 64 * np.finfo(float).eps * n * maior * maior
    with np.errstate(over="ignore", invalid="ignore"):
        produto_1 = matriz @ matriz.T
        produto_2 = matriz.T @ matriz
    return bool(np.allclose(produto_1, produto_2, rtol=0, atol=tolerancia))


def matriz_para_fala(matriz):
    linhas = []
    for linha in matriz:
        linhas.append(", ".join(numero_para_fala(valor) for valor in linha))
    return ". ".join(linhas)


def mostrar_matriz(matriz, titulo, falar_matriz=True):
    print()
    print("=" * LARGURA)
    print(titulo)
    print("=" * LARGURA)
    for linha in matriz:
        print(" ".join(numero_para_texto(valor) for valor in linha))
    if falar_matriz:
        falar_somente(f"{titulo}. {matriz_para_fala(matriz)}.")


def imprimir_classificacao(numero, nome, resultado, explicacao):
    """
    Imprime o número, o nome da classificação, o resultado (SIM/NÃO)
    e a explicação escrita completa. Também fala o mesmo conteúdo.
    """
    print(f"{numero:02d}. {nome}: {resultado}")
    print(f"    {explicacao}")

    resultado_falado = "sim" if resultado == "SIM" else "não"
    falar(f"{numero}. {nome}: {resultado_falado}. {explicacao}")


# ============================================================
# ANÁLISE PRINCIPAL — ITENS 1 A 11
# ============================================================

# (número, nome, teste, explicação se SIM, explicação se NÃO)
EXPLICACAO_UNIDADE = (
    "Neste programa, matriz unidade é tratada como sinônimo de matriz identidade."
)
CLASSIFICACOES_ANALISE = [
    (1, "Matriz quadrada", eh_quadrada,
     "O número de linhas é igual ao número de colunas.",
     "O número de linhas é diferente do número de colunas."),
    (2, "Matriz retangular", eh_retangular,
     "O número de linhas é diferente do número de colunas.",
     "A matriz é quadrada."),
    (3, "Matriz nula ou zero", eh_nula,
     "Todos os elementos são iguais a zero.",
     "Existe pelo menos um elemento diferente de zero."),
    (4, "Matriz coluna", eh_coluna,
     "A matriz possui exatamente uma coluna.",
     "A matriz possui mais de uma coluna."),
    (5, "Matriz linha", eh_linha,
     "A matriz possui exatamente uma linha.",
     "A matriz possui mais de uma linha."),
    (6, "Matriz diagonal", eh_diagonal,
     "A matriz é quadrada e todos os elementos fora da diagonal principal são zero.",
     "Existe pelo menos um elemento fora da diagonal principal diferente de zero."),
    (7, "Matriz escalar", eh_escalar,
     "A matriz é diagonal e todos os elementos da diagonal principal são iguais.",
     "A matriz não é diagonal ou os elementos da diagonal principal não são todos iguais."),
    (8, "Matriz identidade", eh_identidade,
     "A diagonal principal contém somente um e os demais elementos são zero.",
     "A matriz não possui a forma da identidade."),
    (9, "Matriz unidade", eh_identidade,
     EXPLICACAO_UNIDADE, EXPLICACAO_UNIDADE),
    (10, "Matriz triangular superior", eh_triangular_superior,
     "Todos os elementos abaixo da diagonal principal são zero.",
     "Existe elemento diferente de zero abaixo da diagonal principal."),
    (11, "Matriz triangular inferior", eh_triangular_inferior,
     "Todos os elementos acima da diagonal principal são zero.",
     "Existe elemento diferente de zero acima da diagonal principal."),
]

CLASSIFICACOES_TRANSPOSTA = [
    (13, "Matriz simétrica", eh_simetrica,
     "A matriz é igual à sua transposta.",
     "A matriz é diferente da sua transposta."),
    (14, "Matriz antissimétrica", eh_antissimetrica,
     "A transposta da matriz é igual ao negativo da matriz.",
     "A transposta da matriz não é igual ao seu negativo."),
]

CLASSIFICACAO_NORMAL = (
    15, "Matriz normal", eh_normal,
    "A matriz vezes sua transposta é igual à transposta vezes a matriz.",
    "Os dois produtos, M vezes M transposta e M transposta vezes M, são diferentes.",
)


def aplicar_classificacoes(matriz, tabela):
    """
    Roda cada teste da tabela, imprime e fala o resultado e devolve
    os nomes das classificações que deram SIM.
    """
    encontradas = []
    for numero, nome, teste, se_sim, se_nao in tabela:
        if teste(matriz):
            encontradas.append(nome)
            imprimir_classificacao(numero, nome, "SIM", se_sim)
        else:
            imprimir_classificacao(numero, nome, "NÃO", se_nao)
    return encontradas


def mostrar_resumo(classificacoes, titulo, texto_vazio):
    print()
    print("=" * LARGURA)
    print(titulo)
    print("=" * LARGURA)

    if classificacoes:
        for i, nome in enumerate(classificacoes, 1):
            print(f"{i}. {nome}")
        falar_somente(
            "Classificações encontradas: " + ", ".join(classificacoes) + "."
        )
    else:
        print(texto_vazio)
        falar_somente(texto_vazio)


def analisar_matriz(matriz):
    iniciar_captura_audio()

    linhas, colunas = matriz.shape

    print()
    print("=" * LARGURA)
    print("ANÁLISE DA MATRIZ (classificações 1 a 11)")
    print("=" * LARGURA)

    falar_somente(f"A matriz possui {linhas} linhas e {colunas} colunas.")
    mostrar_matriz(matriz, "Matriz informada")

    classificacoes = aplicar_classificacoes(matriz, CLASSIFICACOES_ANALISE)

    mostrar_resumo(
        classificacoes,
        "RESUMO (classificações 1 a 11)",
        "Nenhuma classificação aplicável.",
    )

    print()
    print("Dica: use o menu 'Transformar matriz' para calcular a "
          "transposta e verificar simetria, antissimetria e normalidade.")

    parar_captura_audio()

    oferecer_repeticao_audio()


# ============================================================
# TRANSFORMAÇÃO — ITENS 12, 13, 14, 15
# ============================================================

def transformar_transposta(matriz):
    """
    Calcula a transposta (12) e, a partir dela, verifica
    simetria (13), antissimetria (14) e normalidade (15).
    """
    iniciar_captura_audio()

    print()
    print("=" * LARGURA)
    print("TRANSFORMAÇÃO: TRANSPOSTA E CLASSIFICAÇÕES RELACIONADAS")
    print("=" * LARGURA)

    mostrar_matriz(matriz, "Matriz original")

    transposta = matriz.T
    mostrar_matriz(transposta, "12. Matriz transposta")
    print("    A transposta não é uma classificação da matriz original.")
    print("    Ela é obtida trocando as linhas pelas colunas.")
    falar_somente(
        "A transposta não é uma classificação da matriz original. "
        "Ela é obtida trocando as linhas pelas colunas."
    )

    classificacoes = aplicar_classificacoes(matriz, CLASSIFICACOES_TRANSPOSTA)

    if eh_quadrada(matriz):
        with np.errstate(over="ignore", invalid="ignore"):
            produto_1 = matriz @ matriz.T
            produto_2 = matriz.T @ matriz
        mostrar_matriz(produto_1, "M vezes M transposta")
        mostrar_matriz(produto_2, "M transposta vezes M")
        classificacoes += aplicar_classificacoes(matriz, [CLASSIFICACAO_NORMAL])
    else:
        print("15. Matriz normal: NÃO SE APLICA")
        print("    A verificação de normalidade exige uma matriz quadrada.")
        falar_somente(
            "15. Matriz normal: não se aplica. "
            "A verificação de normalidade exige uma matriz quadrada."
        )

    mostrar_resumo(
        classificacoes,
        "RESUMO (classificações relacionadas à transposta)",
        "Nenhuma classificação adicional aplicável.",
    )

    parar_captura_audio()

    oferecer_repeticao_audio()


# ============================================================
# LAYOUT
# ============================================================

def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def caixa_titulo(titulo):
    print()
    print("┌" + "─" * (LARGURA - 2) + "┐")
    print("│" + titulo.center(LARGURA - 2) + "│")
    print("└" + "─" * (LARGURA - 2) + "┘")


def item_menu(tecla, texto):
    print(f"  [{tecla}]  {texto}")


def linha_fina():
    print("-" * LARGURA)


# ============================================================
# MENUS
# ============================================================

def menu_transformar():
    anunciar = True
    while True:
        if anunciar:
            limpar_tela()
            caixa_titulo("TRANSFORMAR MATRIZ")
            item_menu("1", "Calcular transposta (inclui simetria, antissimetria e normalidade)")
            item_menu("2", "Voltar")
            linha_fina()
            falar_interrompendo(
                "Um, transposta e classificações relacionadas. Dois, voltar."
            )
        anunciar = True

        tecla = ler_tecla_menu()

        if tecla == "1":
            transformar_transposta(informar_matriz())
        elif tecla == "2":
            return
        else:
            falar_interrompendo("Opção inválida. Escolha um ou dois.", imprimir=True)
            anunciar = False


def menu_informar_analisar():
    """
    Se já existir uma matriz informada anteriormente (ULTIMA_MATRIZ),
    oferece a opção de reaproveitar a transposta dela em vez de
    digitar uma matriz nova do zero.
    """
    global ULTIMA_MATRIZ

    if ULTIMA_MATRIZ is None:
        matriz = informar_matriz()
        analisar_matriz(matriz)
        return

    anunciar = True
    while True:
        if anunciar:
            limpar_tela()
            caixa_titulo("INFORMAR MATRIZ")
            item_menu("1", "Informar nova matriz")
            item_menu("2", "Usar a transposta da última matriz informada")
            item_menu("3", "Voltar")
            falar_interrompendo(
                "Um, nova matriz. Dois, transposta da última matriz. Três, voltar."
            )
        anunciar = True

        tecla = ler_tecla_menu()

        if tecla == "1":
            matriz = informar_matriz()
            analisar_matriz(matriz)
            return

        elif tecla == "2":
            matriz = ULTIMA_MATRIZ.T
            mostrar_matriz(
                matriz, "Matriz transposta utilizada como nova matriz",
                falar_matriz=False
            )
            ULTIMA_MATRIZ = matriz
            falar_somente("Usando a transposta.")
            analisar_matriz(matriz)
            return

        elif tecla == "3":
            return

        else:
            falar_interrompendo(
                "Opção inválida. Escolha um, dois ou três.", imprimir=True
            )
            anunciar = False


def menu():
    anunciar = True
    while True:
        if anunciar:
            limpar_tela()
            caixa_titulo("CLASSIFICADOR AUTOMÁTICO DE MATRIZES")
            item_menu("1", "Informar matriz e analisar (classificações 1 a 11)")
            item_menu("2", "Transformar matriz (transposta, simetria, normalidade)")
            item_menu("3", "Sair")
            with lock_modo_fone:
                fone_txt = "ATIVADO" if modo_fone else "DESATIVADO"
            with lock_velocidade:
                velocidade_txt = velocidade_voz
            print(f"  Microfone: {texto_status_microfone()}   [M] alternar")
            print(f"  Modo fone: {fone_txt}   aperte [F] ou [Fale 'Fone'] para alternar (sem eco durante a voz)")
            print(f"  Velocidade da voz: {velocidade_txt:.2f}x   [A] aumentar   [D] diminuir")
            print("  [Esc] corta a fala   [H] ajuda com as teclas")
            linha_fina()

            falar_interrompendo(
                "Menu principal. "
                "Um, informar e analisar matriz. "
                "Dois, transformar matriz. "
                "Três, sair. "
                "H para ajuda."
            )
        anunciar = True

        tecla = ler_tecla_menu()

        if tecla == "1":
            menu_informar_analisar()
        elif tecla == "2":
            menu_transformar()
        elif tecla == "3":
            falar_interrompendo("Até logo.", imprimir=True)
            esperar_voz_cortavel()
            return
        else:
            falar_interrompendo(
                "Opção inválida. Pressione um, dois ou três.", imprimir=True
            )
            anunciar = False


def encerrar_voz():
    global MICROFONE_ATIVO
    MICROFONE_ATIVO = False
    parar_microfone_evento.set()
    limpar_fila_teclas_voz()
    if thread_microfone is not None and thread_microfone.is_alive():
        thread_microfone.join(timeout=1.0)
    limpar_fila()
    interromper_audio_atual()
    try:
        fila_voz.put_nowait(None)
    except Exception:
        pass


def _encerrar_por_sinal(numero, quadro):
    # Vira SystemExit para o finally de main() devolver o terminal ao normal.
    sys.exit(0)


def main():
    if not WINDOWS:
        signal.signal(signal.SIGTERM, _encerrar_por_sinal)
    ligar_terminal_imediato()
    try:
        caixa_titulo("CLASSIFICADOR DE MATRIZES")
        falar("Bem-vindo ao classificador de matrizes.")
        esperar_voz_cortavel()
        if MICROFONE_DISPONIVEL:
            alternar_microfone()
            esperar_voz_cortavel()
        else:
            falar_interrompendo(
                "Microfone indisponível. O teclado continua funcionando."
            )
            esperar_voz_cortavel()
        menu()
    except KeyboardInterrupt:
        print("\n")
        falar("Programa interrompido.")
        esperar_voz()
    finally:
        encerrar_voz()
        desligar_terminal_imediato()


if __name__ == "__main__":
    main()

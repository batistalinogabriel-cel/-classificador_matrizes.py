import os
import sys
import wave
import queue
import tempfile
import shutil
import threading
import json
import time
import unicodedata
import platform
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
    from piper import PiperVoice, SynthesisConfig
except ImportError:
    from piper import PiperVoice
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


def localizar_modelo_voz():
    for caminho in _candidatos_modelo_voz():
        if caminho and os.path.isfile(caminho):
            return caminho

    # Último recurso: procura qualquer voz Piper em português dentro da HOME.
    try:
        for raiz, diretorios, arquivos in os.walk(os.path.expanduser("~")):
            diretorios[:] = [d for d in diretorios if d not in {".cache", ".config", ".local"}]
            for arquivo in arquivos:
                if arquivo.startswith("pt_BR") and arquivo.endswith(".onnx"):
                    return os.path.join(raiz, arquivo)
    except Exception:
        pass

    return None


MODELO_VOZ = localizar_modelo_voz()

# Velocidade da voz (quanto maior, mais rápida a fala)
VELOCIDADE_VOZ = 1.25
LENGTH_SCALE_VOZ = 1.0 / VELOCIDADE_VOZ

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

if SynthesisConfig is not None:
    CONFIG_VOZ = SynthesisConfig(
        volume=VOLUME_VOZ,
        length_scale=LENGTH_SCALE_VOZ
    )
else:
    CONFIG_VOZ = None

fila_voz = queue.Queue()
processo_atual = None
lock_processo = threading.Lock()
stream_reproducao = None  # usado com sounddevice

# Guarda a última matriz digitada pelo usuário (para reaproveitar a transposta)
ULTIMA_MATRIZ = None

# Controle de gravação/repetição de áudio de uma operação
GRAVANDO_FALA = False
BUFFER_FALA = []
ULTIMO_AUDIO = []


def gerar_audio(texto):
    arquivo = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    caminho = arquivo.name
    arquivo.close()
    try:
        with wave.open(caminho, "wb") as wav_file:
            if CONFIG_VOZ is None:
                VOZ.synthesize_wav(texto, wav_file)
            else:
                VOZ.synthesize_wav(texto, wav_file, syn_config=CONFIG_VOZ)
        return caminho
    except Exception:
        if os.path.exists(caminho):
            os.remove(caminho)
        raise


def reproduzir_audio(caminho):
    """
    Reproduz um arquivo WAV usando sounddevice + soundfile (multiplataforma).
    Fallback para programas externos apenas se sounddevice/soundfile não
    estiverem disponíveis.
    """
    global processo_atual, stream_reproducao
    try:
        audio_piper_falando.set()

        if sd is not None and sf is not None:
            try:
                dados, taxa = sf.read(caminho, dtype="float32")
                sd.play(dados, taxa)
                with lock_processo:
                    stream_reproducao = True
                sd.wait()
            finally:
                with lock_processo:
                    stream_reproducao = None
        else:
            # Fallback: programas externos (apenas Linux, em geral)
            comando = _detectar_comando_reproducao()
            if comando is None:
                print("\nERRO: nenhum método de reprodução de áudio disponível.")
                return
            processo = None
            try:
                import subprocess
                processo = subprocess.Popen(
                    comando + [caminho],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                with lock_processo:
                    processo_atual = processo
                processo.wait()
            finally:
                with lock_processo:
                    if processo_atual is processo:
                        processo_atual = None
    finally:
        audio_piper_falando.clear()
        if os.path.exists(caminho):
            try:
                os.remove(caminho)
            except Exception:
                pass


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
    global processo_atual, stream_reproducao
    with lock_processo:
        if stream_reproducao is not None and sd is not None:
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


def limpar_fila():
    while True:
        try:
            fila_voz.get_nowait()
            fila_voz.task_done()
        except queue.Empty:
            return


def trabalhador_voz():
    while True:
        texto = fila_voz.get()
        if texto is None:
            fila_voz.task_done()
            return
        caminho = None
        try:
            caminho = gerar_audio(texto)
            reproduzir_audio(caminho)
        except Exception as erro:
            print(f"\nErro na síntese de voz: {erro}")
            if caminho and os.path.exists(caminho):
                os.remove(caminho)
        finally:
            fila_voz.task_done()


thread_voz = threading.Thread(target=trabalhador_voz, daemon=True)
thread_voz.start()


def falar(texto, imprimir=False):
    if imprimir:
        print(texto)
    if GRAVANDO_FALA:
        BUFFER_FALA.append(texto)
    fila_voz.put(texto)


def falar_somente(texto):
    if GRAVANDO_FALA:
        BUFFER_FALA.append(texto)
    fila_voz.put(texto)


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
    fila_voz.put(texto)


def esperar_voz():
    fila_voz.join()


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
        esperar_voz()
        return

    limpar_fila()
    interromper_audio_atual()

    for texto in ULTIMO_AUDIO:
        fila_voz.put(texto)

    esperar_voz()


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

        falar_interrompendo(
            "Pressione R para repetir o áudio, "
            "ou qualquer outra tecla para voltar ao menu."
        )

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
    if np.isclose(valor, round(valor)):
        return str(int(round(valor)))
    return f"{float(valor):.4f}".rstrip("0").rstrip(".").replace(".", ",")


def numero_para_fala(valor):
    texto = numero_para_texto(valor)
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
MICROFONE_DISPOSITIVO = None
MICROFONE_TAXA_REAL = TAXA_VOSK
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

# Último recurso: procura diretórios vosk-model* diretamente na HOME.
if MODELO_MICROFONE is None:
    try:
        for raiz, diretorios, _ in os.walk(os.path.expanduser("~")):
            diretorios[:] = [d for d in diretorios if d not in {".cache", ".config", ".local"}]
            for d in list(diretorios):
                if d.startswith("vosk-model") and os.path.isfile(os.path.join(raiz, d, "am", "final.mdl")):
                    MODELO_MICROFONE = os.path.join(raiz, d)
                    break
            if MODELO_MICROFONE:
                break
    except Exception:
        pass

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
thread_microfone = None
parar_microfone_evento = threading.Event()
parar_microfone_evento.set()
audio_piper_falando = threading.Event()

PALAVRA_PARA_TECLA = {
    "zero": "0", "um": "1", "uma": "1", "dois": "2", "duas": "2",
    "tres": "3", "três": "3", "quatro": "4", "cinco": "5", "seis": "6",
    "sete": "7", "oito": "8", "nove": "9", "menos": "-",
    "virgula": ",", "vírgula": ",", "ponto": ",",
    "espaco": " ", "espaço": " ",
    "apaga": "\x7f", "apagar": "\x7f", "apague": "\x7f", "voltar": "\x7f",
    "excluir": "\x7f",
    "confirma": "\r", "confirmar": "\r", "confirme": "\r",
    "enter": "\r", "pronto": "\r", "terminar": "\r", "terminado": "\r",
    "finalizar": "\r", "finaliza": "\r", "por": " ",
}

PALAVRAS_IGNORADAS = {
    "digite", "digitar", "número", "numero", "números", "numeros",
    "elemento", "elementos", "linha", "linhas", "coluna", "colunas",
    "matriz", "vez", "vezes", "o", "a", "e", "de", "da", "do",
}


def normalizar_palavra(palavra):
    forma_decomposta = unicodedata.normalize("NFKD", palavra)
    return "".join(c for c in forma_decomposta if not unicodedata.combining(c)).lower()


def limpar_fila_teclas_voz():
    while True:
        try:
            fila_teclas_voz.get_nowait()
            fila_teclas_voz.task_done()
        except queue.Empty:
            return


def processar_texto_reconhecido(texto):
    """
    Transforma uma frase reconhecida em eventos de entrada.
    Primeiro o Piper lê a frase completa; depois os comandos
    são enviados à fila de teclas virtuais.
    """
    texto = texto.strip()
    if not texto:
        return
    print(f"[MIC] Reconhecido: {texto}")
    print(f"[VOZ] {texto}")

    # Piper lê a frase completa antes de processar os comandos
    falar_interrompendo(texto)
    esperar_voz()

    for palavra in texto.split():
        chave = normalizar_palavra(palavra)
        if chave in PALAVRAS_IGNORADAS:
            continue
        if chave in PALAVRA_PARA_TECLA:
            fila_teclas_voz.put(PALAVRA_PARA_TECLA[chave])


def criar_reconhecedor(taxa):
    # Gramática apenas com palavras do dicionário de comandos
    # (evita WARNING de palavras ausentes no vocabulário do modelo)
    palavras = sorted(set(PALAVRA_PARA_TECLA.keys()))
    try:
        return vosk.KaldiRecognizer(
            MODELO_VOSK, taxa,
            json.dumps(palavras, ensure_ascii=False)
        )
    except Exception:
        return vosk.KaldiRecognizer(MODELO_VOSK, taxa)


def reamostrar_para_16k(audio, taxa_origem):
    """
    Recebe áudio float32 (mono ou multi-canal), converte para mono
    e reamostra para 16000 Hz se necessário. Retorna float32 mono.
    """
    audio = np.asarray(audio, dtype=np.float32)

    # Estéreo / multi-canal → mono
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    taxa_origem = int(taxa_origem)
    if taxa_origem == TAXA_VOSK:
        return audio

    if taxa_origem <= 0 or len(audio) == 0:
        return np.array([], dtype=np.float32)

    # Reamostragem linear simples com numpy
    n_destino = int(round(len(audio) * TAXA_VOSK / taxa_origem))
    if n_destino <= 0:
        return np.array([], dtype=np.float32)

    indices = np.linspace(0, len(audio) - 1, n_destino)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


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
    Abre na taxa nativa do dispositivo, converte para mono,
    reamostra para 16 kHz e envia ao Vosk.
    Descarta áudio enquanto o Piper estiver falando.
    """
    global MICROFONE_ATIVO, MICROFONE_TAXA_REAL, ERRO_MICROFONE, MICROFONE_DISPOSITIVO

    try:
        indice, erro = encontrar_microfone()
        if indice is None:
            raise RuntimeError(erro or "Dispositivo de microfone não encontrado.")

        info = sd.query_devices(indice, "input")
        nome = str(info.get("name", f"dispositivo {indice}"))
        taxa_nativa = int(float(info.get("default_samplerate", 48000)))
        max_canais = int(info.get("max_input_channels", 1) or 1)
        canais = 1 if max_canais < 1 else min(2, max_canais)

        MICROFONE_DISPOSITIVO = indice
        MICROFONE_TAXA_REAL = taxa_nativa

        print(f"[MIC] Sistema: {SISTEMA}")
        print(f"[MIC] Dispositivo escolhido: {nome}")
        print(f"[MIC] Índice: {indice}")
        print(f"[MIC] Canais: {canais}")
        print(f"[MIC] Taxa nativa: {taxa_nativa} Hz")
        print(f"[MIC] Taxa Vosk: {TAXA_VOSK} Hz")
        print("[MIC] Abrindo captura...")

        reconhecedor = criar_reconhecedor(TAXA_VOSK)

        def callback(indata, frames, tempo, status):
            if status:
                print(f"\n[MIC] status: {status}")
            # Descartar áudio enquanto o Piper fala (não acumular)
            if audio_piper_falando.is_set():
                return
            try:
                audio = np.asarray(indata, dtype=np.float32)
                audio_16k = reamostrar_para_16k(audio, taxa_nativa)
                if len(audio_16k) == 0:
                    return
                pcm = float32_para_pcm16(audio_16k)
                if reconhecedor.AcceptWaveform(pcm):
                    resultado = json.loads(reconhecedor.Result())
                    texto = resultado.get("text", "").strip()
                    if texto:
                        processar_texto_reconhecido(texto)
            except Exception as erro_cb:
                print(f"\n[MIC] erro no callback: {erro_cb}")

        with sd.InputStream(
            device=indice,
            samplerate=taxa_nativa,
            channels=canais,
            dtype="float32",
            blocksize=0,
            callback=callback,
        ):
            MICROFONE_ATIVO = True
            print("[MIC] CAPTURA ABERTA COM SUCESSO.")
            print("[MIC] Microfone ouvindo.")
            parar_microfone_evento.wait()

            # Resultado final pendente
            try:
                if not audio_piper_falando.is_set():
                    final = json.loads(reconhecedor.FinalResult()).get("text", "").strip()
                    if final:
                        processar_texto_reconhecido(final)
            except Exception:
                pass

    except Exception as erro:
        ERRO_MICROFONE = str(erro)
        print(f"\nERRO REAL DO MICROFONE: {erro}")
    finally:
        MICROFONE_ATIVO = False
        MICROFONE_DISPOSITIVO = None


def trabalhador_microfone():
    """Ponto de entrada único — sempre sounddevice."""
    global ERRO_MICROFONE
    if sd is None:
        ERRO_MICROFONE = "sounddevice não está disponível."
        return
    trabalhador_microfone_sounddevice()


def alternar_microfone():
    global MICROFONE_ATIVO, thread_microfone, ERRO_MICROFONE
    if not MICROFONE_DISPONIVEL:
        falar_interrompendo("Microfone indisponível. " + ERRO_MICROFONE, imprimir=True)
        return

    if MICROFONE_ATIVO:
        parar_microfone_evento.set()
        MICROFONE_ATIVO = False
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
        falar_interrompendo("Microfone ativado. Fale depois que eu terminar de falar.")
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

class LeitorTeclado:
    def __init__(self):
        self.ativo = False
        if not WINDOWS:
            self.fd = sys.stdin.fileno()
            self.original = termios.tcgetattr(self.fd)

    def iniciar(self):
        if WINDOWS:
            self.ativo = True
            return
        if not self.ativo:
            tty.setraw(self.fd)
            self.ativo = True

    def restaurar(self):
        if WINDOWS:
            self.ativo = False
            return
        if self.ativo:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original)
            self.ativo = False

    def _ler_tecla_windows(self):
        """Lê uma tecla no Windows via msvcrt (não bloqueia indefinidamente)."""
        while True:
            # Prioridade: teclas virtuais vindas da voz
            try:
                return fila_teclas_voz.get_nowait()
            except queue.Empty:
                pass

            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                # Teclas especiais (setas etc.) geram dois caracteres
                if ch in ("\x00", "\xe0"):
                    msvcrt.getwch()  # descarta o segundo byte
                    continue
                return ch
            time.sleep(0.05)

    def _ler_tecla_linux(self):
        """Lê uma tecla no Linux via termios/tty/select."""
        while True:
            try:
                return fila_teclas_voz.get_nowait()
            except queue.Empty:
                pass

            prontos, _, _ = select.select([sys.stdin], [], [], 0.1)
            if prontos:
                return sys.stdin.read(1)

    def ler_tecla(self):
        """
        Aguarda uma tecla do teclado OU uma "tecla virtual" vinda
        do reconhecimento de voz (quando o microfone está ativo),
        o que chegar primeiro.
        """
        if WINDOWS:
            return self._ler_tecla_windows()
        return self._ler_tecla_linux()


def ler_tecla_menu():
    leitor = LeitorTeclado()
    try:
        leitor.iniciar()
        while True:
            tecla = leitor.ler_tecla()
            if tecla in ("m", "M"):
                alternar_microfone()
                continue
            return tecla
    finally:
        leitor.restaurar()


def validar_token_numero(token):
    token = token.replace(",", ".")
    if token in ("", "-", "."):
        return None
    try:
        return float(token)
    except ValueError:
        return None


def ler_linha_matriz(numero_linha, quantidade_colunas):
    while True:
        print()
        print(f"Linha {numero_linha} de {quantidade_colunas} elementos.")
        print("Digite os elementos separados por espaços:")
        print(f"(Microfone: {texto_status_microfone()} — pressione M para alternar)")
        print("> ", end="", flush=True)

        falar_interrompendo(
            f"Linha {numero_linha}. Digite os elementos separados por espaços."
        )
        esperar_voz()

        leitor = LeitorTeclado()
        texto = ""

        try:
            leitor.iniciar()
            while True:
                tecla = leitor.ler_tecla()

                if tecla == "\x03":
                    raise KeyboardInterrupt

                if tecla in ("m", "M"):
                    alternar_microfone()
                    continue

                if tecla in ("\r", "\n"):
                    print()
                    tokens = texto.strip().split()

                    if len(tokens) != quantidade_colunas:
                        if len(tokens) < quantidade_colunas:
                            diferenca = quantidade_colunas - len(tokens)
                            falar_interrompendo(
                                f"Você informou {len(tokens)} elementos. "
                                f"Faltam {diferenca}."
                            )
                        else:
                            diferenca = len(tokens) - quantidade_colunas
                            falar_interrompendo(
                                f"Você informou {len(tokens)} elementos. "
                                f"Há {diferenca} elementos a mais."
                            )
                        break

                    valores = []
                    invalido = False
                    for token in tokens:
                        valor = validar_token_numero(token)
                        if valor is None:
                            falar_interrompendo(
                                f"O valor {token} não é um número válido."
                            )
                            invalido = True
                            break
                        valores.append(valor)

                    if invalido:
                        break

                    return valores

                if tecla in ("\x7f", "\b"):
                    if texto:
                        texto = texto[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                        falar_interrompendo("apagado")
                    else:
                        falar_interrompendo("Não há nada para apagar.")
                    continue

                if tecla == " ":
                    if texto and not texto.endswith(" "):
                        texto += " "
                        print(" ", end="", flush=True)
                    continue

                if tecla.isdigit():
                    texto += tecla
                    print(tecla, end="", flush=True)
                    falar_interrompendo(DIGITOS[tecla])
                    continue

                if tecla == "-":
                    inicio_elemento = not texto or texto.endswith(" ")
                    if inicio_elemento:
                        texto += tecla
                        print("-", end="", flush=True)
                        falar_interrompendo("menos")
                    else:
                        falar_interrompendo(
                            "O sinal de menos deve estar no início do elemento."
                        )
                    continue

                if tecla in ".,":
                    tokens = texto.split()
                    atual = tokens[-1] if tokens else ""
                    if atual and "." not in atual and "," not in atual:
                        texto += tecla
                        print(tecla, end="", flush=True)
                        falar_interrompendo("vírgula")
                    elif not atual:
                        falar_interrompendo("Digite primeiro um número.")
                    else:
                        falar_interrompendo(
                            "Este elemento já possui separador decimal."
                        )
                    continue

                falar_interrompendo("Tecla não permitida.")
        finally:
            leitor.restaurar()


def ler_numero_tempo_real(mensagem):
    while True:
        leitor = LeitorTeclado()
        valor_digitado = ""
        print()
        print(mensagem)
        print(f"(Microfone: {texto_status_microfone()} — pressione M para alternar)")
        print("> ", end="", flush=True)
        falar_interrompendo(mensagem)
        try:
            leitor.iniciar()
            while True:
                tecla = leitor.ler_tecla()

                if tecla == "\x03":
                    raise KeyboardInterrupt

                if tecla in ("m", "M"):
                    alternar_microfone()
                    continue

                if tecla in ("\r", "\n"):
                    valor = validar_token_numero(valor_digitado)
                    if valor is None:
                        falar_interrompendo("Digite um número válido.")
                        continue
                    print()
                    return valor

                if tecla in ("\x7f", "\b"):
                    if valor_digitado:
                        valor_digitado = valor_digitado[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                        falar_interrompendo("apagado")
                    else:
                        falar_interrompendo("Não há nada para apagar.")
                    continue

                if tecla.isdigit():
                    valor_digitado += tecla
                    print(tecla, end="", flush=True)
                    falar_interrompendo(DIGITOS[tecla])
                    continue

                if tecla == "-" and valor_digitado == "":
                    valor_digitado += tecla
                    print("-", end="", flush=True)
                    falar_interrompendo("menos")
                    continue

                if tecla in ".," and valor_digitado not in ("", "-"):
                    if "." not in valor_digitado and "," not in valor_digitado:
                        valor_digitado += tecla
                        print(tecla, end="", flush=True)
                        falar_interrompendo("vírgula")
                    else:
                        falar_interrompendo(
                            "O número já possui separador decimal."
                        )
                    continue

                falar_interrompendo("Tecla não permitida.")
        finally:
            leitor.restaurar()


def ler_inteiro_positivo(mensagem):
    while True:
        valor = ler_numero_tempo_real(mensagem)
        if valor > 0 and float(valor).is_integer():
            return int(valor)
        falar_interrompendo("Digite um número inteiro maior que zero.")


def informar_matriz(anunciar=True):
    """
    Pergunta linhas, colunas e cada linha da matriz.
    Atualiza ULTIMA_MATRIZ com o resultado, para que outras
    partes do programa possam reaproveitar a transposta dela.
    """
    global ULTIMA_MATRIZ

    if anunciar:
        falar("Vamos informar uma nova matriz.")

    linhas = ler_inteiro_positivo("Digite o número de linhas.")
    colunas = ler_inteiro_positivo("Digite o número de colunas.")

    falar_somente(
        f"A matriz possui {linhas} linhas e {colunas} colunas."
    )

    print()
    print("Digite uma linha inteira por vez.")
    print("Use espaços para separar os elementos.")
    print("Exemplo: 1 2 3")

    falar_somente(
        "Digite uma linha inteira por vez. "
        "Use espaços para separar os elementos. "
        "Por exemplo: um, espaço, dois, espaço, três."
    )
    esperar_voz()

    matriz = []
    for i in range(linhas):
        matriz.append(ler_linha_matriz(i + 1, colunas))

    resultado = np.array(matriz, dtype=float)
    print()
    print("Matriz preenchida.")
    falar("Matriz preenchida.")

    ULTIMA_MATRIZ = resultado
    return resultado


def eh_quadrada(matriz):
    return matriz.shape[0] == matriz.shape[1]


def eh_retangular(matriz):
    return matriz.shape[0] != matriz.shape[1]


def eh_nula(matriz):
    return np.allclose(matriz, 0)


def eh_coluna(matriz):
    return matriz.shape[1] == 1


def eh_linha(matriz):
    return matriz.shape[0] == 1


def eh_diagonal(matriz):
    return eh_quadrada(matriz) and np.allclose(matriz, np.diag(np.diag(matriz)))


def eh_escalar(matriz):
    if not eh_diagonal(matriz):
        return False
    diagonal = np.diag(matriz)
    return np.allclose(diagonal, diagonal[0])


def eh_identidade(matriz):
    return eh_quadrada(matriz) and np.allclose(matriz, np.eye(matriz.shape[0]))


def eh_triangular_superior(matriz):
    return eh_quadrada(matriz) and np.allclose(matriz, np.triu(matriz))


def eh_triangular_inferior(matriz):
    return eh_quadrada(matriz) and np.allclose(matriz, np.tril(matriz))


def eh_simetrica(matriz):
    return eh_quadrada(matriz) and np.allclose(matriz, matriz.T)


def eh_antissimetrica(matriz):
    return eh_quadrada(matriz) and np.allclose(matriz.T, -matriz)


def eh_normal(matriz):
    return eh_quadrada(matriz) and np.allclose(matriz @ matriz.T, matriz.T @ matriz)


def matriz_para_fala(matriz):
    linhas = []
    for linha in matriz:
        linhas.append(", ".join(numero_para_fala(valor) for valor in linha))
    return ". ".join(linhas)


def mostrar_matriz(matriz, titulo):
    print()
    print("=" * LARGURA)
    print(titulo)
    print("=" * LARGURA)
    for linha in matriz:
        print(" ".join(numero_para_texto(valor) for valor in linha))
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

def analisar_matriz(matriz):
    iniciar_captura_audio()

    classificacoes = []
    linhas, colunas = matriz.shape

    print()
    print("=" * LARGURA)
    print("ANÁLISE DA MATRIZ (classificações 1 a 11)")
    print("=" * LARGURA)

    falar("A análise da matriz começou.")
    falar_somente(f"A matriz possui {linhas} linhas e {colunas} colunas.")
    mostrar_matriz(matriz, "Matriz informada")

    if eh_quadrada(matriz):
        classificacoes.append("Matriz quadrada")
        imprimir_classificacao(1, "Matriz quadrada", "SIM",
            "O número de linhas é igual ao número de colunas.")
    else:
        imprimir_classificacao(1, "Matriz quadrada", "NÃO",
            "O número de linhas é diferente do número de colunas.")

    if eh_retangular(matriz):
        classificacoes.append("Matriz retangular")
        imprimir_classificacao(2, "Matriz retangular", "SIM",
            "O número de linhas é diferente do número de colunas.")
    else:
        imprimir_classificacao(2, "Matriz retangular", "NÃO",
            "A matriz é quadrada.")

    if eh_nula(matriz):
        classificacoes.append("Matriz nula ou zero")
        imprimir_classificacao(3, "Matriz nula ou zero", "SIM",
            "Todos os elementos são iguais a zero.")
    else:
        imprimir_classificacao(3, "Matriz nula ou zero", "NÃO",
            "Existe pelo menos um elemento diferente de zero.")

    if eh_coluna(matriz):
        classificacoes.append("Matriz coluna")
        imprimir_classificacao(4, "Matriz coluna", "SIM",
            "A matriz possui exatamente uma coluna.")
    else:
        imprimir_classificacao(4, "Matriz coluna", "NÃO",
            "A matriz possui mais de uma coluna.")

    if eh_linha(matriz):
        classificacoes.append("Matriz linha")
        imprimir_classificacao(5, "Matriz linha", "SIM",
            "A matriz possui exatamente uma linha.")
    else:
        imprimir_classificacao(5, "Matriz linha", "NÃO",
            "A matriz possui mais de uma linha.")

    if eh_diagonal(matriz):
        classificacoes.append("Matriz diagonal")
        imprimir_classificacao(6, "Matriz diagonal", "SIM",
            "A matriz é quadrada e todos os elementos fora da diagonal principal são zero.")
    else:
        imprimir_classificacao(6, "Matriz diagonal", "NÃO",
            "Existe pelo menos um elemento fora da diagonal principal diferente de zero.")

    if eh_escalar(matriz):
        classificacoes.append("Matriz escalar")
        imprimir_classificacao(7, "Matriz escalar", "SIM",
            "A matriz é diagonal e todos os elementos da diagonal principal são iguais.")
    else:
        imprimir_classificacao(7, "Matriz escalar", "NÃO",
            "A matriz não é diagonal ou os elementos da diagonal principal não são todos iguais.")

    matriz_e_identidade = eh_identidade(matriz)

    if matriz_e_identidade:
        classificacoes.append("Matriz identidade")
        imprimir_classificacao(8, "Matriz identidade", "SIM",
            "A diagonal principal contém somente um e os demais elementos são zero.")
    else:
        imprimir_classificacao(8, "Matriz identidade", "NÃO",
            "A matriz não possui a forma da identidade.")

    if matriz_e_identidade:
        classificacoes.append("Matriz unidade")
        imprimir_classificacao(9, "Matriz unidade", "SIM",
            "Neste programa, matriz unidade é tratada como sinônimo de matriz identidade.")
    else:
        imprimir_classificacao(9, "Matriz unidade", "NÃO",
            "Neste programa, matriz unidade é tratada como sinônimo de matriz identidade.")

    if eh_triangular_superior(matriz):
        classificacoes.append("Matriz triangular superior")
        imprimir_classificacao(10, "Matriz triangular superior", "SIM",
            "Todos os elementos abaixo da diagonal principal são zero.")
    else:
        imprimir_classificacao(10, "Matriz triangular superior", "NÃO",
            "Existe elemento diferente de zero abaixo da diagonal principal.")

    if eh_triangular_inferior(matriz):
        classificacoes.append("Matriz triangular inferior")
        imprimir_classificacao(11, "Matriz triangular inferior", "SIM",
            "Todos os elementos acima da diagonal principal são zero.")
    else:
        imprimir_classificacao(11, "Matriz triangular inferior", "NÃO",
            "Existe elemento diferente de zero acima da diagonal principal.")

    print()
    print("=" * LARGURA)
    print("RESUMO (classificações 1 a 11)")
    print("=" * LARGURA)

    if classificacoes:
        for i, nome in enumerate(classificacoes, 1):
            print(f"{i}. {nome}")
    else:
        print("Nenhuma classificação aplicável.")

    falar_somente(
        f"Foram encontradas {len(classificacoes)} classificações aplicáveis."
    )

    if classificacoes:
        falar_somente(
            "As classificações encontradas foram: "
            + ", ".join(classificacoes)
            + "."
        )

    print()
    print("Dica: use o menu 'Transformar matriz' para calcular a "
          "transposta e verificar simetria, antissimetria e normalidade.")

    falar(
        "Dica: use o menu Transformar matriz para calcular a transposta "
        "e verificar simetria, antissimetria e normalidade."
    )
    esperar_voz()

    falar("Análise concluída.")

    parar_captura_audio()
    esperar_voz()

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

    falar("Calculando a transposta e as classificações relacionadas.")

    mostrar_matriz(matriz, "Matriz original")

    transposta = matriz.T
    mostrar_matriz(transposta, "12. Matriz transposta")
    print("    A transposta não é uma classificação da matriz original.")
    print("    Ela é obtida trocando as linhas pelas colunas.")
    falar_somente(
        "A transposta não é uma classificação da matriz original. "
        "Ela é obtida trocando as linhas pelas colunas."
    )

    classificacoes = []

    if eh_simetrica(matriz):
        classificacoes.append("Matriz simétrica")
        imprimir_classificacao(13, "Matriz simétrica", "SIM",
            "A matriz é igual à sua transposta.")
    else:
        imprimir_classificacao(13, "Matriz simétrica", "NÃO",
            "A matriz é diferente da sua transposta.")

    if eh_antissimetrica(matriz):
        classificacoes.append("Matriz antissimétrica")
        imprimir_classificacao(14, "Matriz antissimétrica", "SIM",
            "A transposta da matriz é igual ao negativo da matriz.")
    else:
        imprimir_classificacao(14, "Matriz antissimétrica", "NÃO",
            "A transposta da matriz não é igual ao seu negativo.")

    if eh_quadrada(matriz):
        produto_1 = matriz @ matriz.T
        produto_2 = matriz.T @ matriz

        mostrar_matriz(produto_1, "M vezes M transposta")
        mostrar_matriz(produto_2, "M transposta vezes M")

        if eh_normal(matriz):
            classificacoes.append("Matriz normal")
            imprimir_classificacao(15, "Matriz normal", "SIM",
                "A matriz vezes sua transposta é igual à transposta vezes a matriz.")
        else:
            imprimir_classificacao(15, "Matriz normal", "NÃO",
                "Os dois produtos, M vezes M transposta e M transposta vezes M, são diferentes.")
    else:
        print("15. Matriz normal: NÃO SE APLICA")
        print("    A verificação de normalidade exige uma matriz quadrada.")
        falar_somente(
            "15. Matriz normal: não se aplica. "
            "A verificação de normalidade exige uma matriz quadrada."
        )

    print()
    print("=" * LARGURA)
    print("RESUMO (classificações relacionadas à transposta)")
    print("=" * LARGURA)

    if classificacoes:
        for i, nome in enumerate(classificacoes, 1):
            print(f"{i}. {nome}")
        falar_somente(
            "As classificações encontradas foram: "
            + ", ".join(classificacoes)
            + "."
        )
    else:
        print("Nenhuma classificação adicional aplicável.")
        falar_somente("Nenhuma classificação adicional aplicável.")

    falar("Cálculo da transposta concluído.")

    parar_captura_audio()
    esperar_voz()

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
    while True:
        limpar_tela()
        caixa_titulo("TRANSFORMAR MATRIZ")
        item_menu("1", "Calcular transposta (inclui simetria, antissimetria e normalidade)")
        item_menu("2", "Voltar")
        linha_fina()

        falar_interrompendo(
            "Menu de transformações. "
            "Um para calcular a transposta e verificar simetria, "
            "antissimetria e normalidade. "
            "Dois para voltar."
        )

        tecla = ler_tecla_menu()

        if tecla == "1":
            falar_interrompendo("Você escolheu calcular a transposta.", imprimir=True)
            esperar_voz()
            transformar_transposta(informar_matriz())
        elif tecla == "2":
            falar_interrompendo("Voltando ao menu principal.", imprimir=True)
            return
        else:
            falar_interrompendo("Opção inválida. Escolha um ou dois.", imprimir=True)


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

    while True:
        limpar_tela()
        caixa_titulo("INFORMAR MATRIZ")
        item_menu("1", "Informar nova matriz")
        item_menu("2", "Usar a transposta da última matriz informada")
        item_menu("3", "Voltar")

        falar_interrompendo(
            "Um para informar uma nova matriz. "
            "Dois para usar a transposta da última matriz informada. "
            "Três para voltar."
        )

        tecla = ler_tecla_menu()

        if tecla == "1":
            falar_interrompendo("Você escolheu informar uma nova matriz.", imprimir=True)
            esperar_voz()
            matriz = informar_matriz()
            analisar_matriz(matriz)
            return

        elif tecla == "2":
            falar_interrompendo(
                "Você escolheu usar a transposta da última matriz informada.",
                imprimir=True
            )
            esperar_voz()
            matriz = ULTIMA_MATRIZ.T
            mostrar_matriz(matriz, "Matriz transposta utilizada como nova matriz")
            ULTIMA_MATRIZ = matriz
            analisar_matriz(matriz)
            return

        elif tecla == "3":
            falar_interrompendo("Voltando ao menu principal.", imprimir=True)
            return

        else:
            falar_interrompendo(
                "Opção inválida. Escolha um, dois ou três.", imprimir=True
            )


def menu():
    while True:
        limpar_tela()
        caixa_titulo("CLASSIFICADOR AUTOMÁTICO DE MATRIZES")
        item_menu("1", "Informar matriz e analisar (classificações 1 a 11)")
        item_menu("2", "Transformar matriz (transposta, simetria, normalidade)")
        item_menu("3", "Sair")
        print(f"  Microfone: {texto_status_microfone()}   [M] para alternar")
        linha_fina()

        falar_interrompendo(
            "Menu principal. "
            "Um para informar e analisar uma matriz. "
            "Dois para transformar uma matriz. "
            "Três para sair. "
            f"Microfone {texto_status_microfone_falado()}. "
            "Pressione M a qualquer momento para ativar ou desativar o microfone."
        )

        tecla = ler_tecla_menu()

        if tecla == "1":
            falar_interrompendo(
                "Você escolheu informar e analisar uma matriz.", imprimir=True
            )
            esperar_voz()
            menu_informar_analisar()
        elif tecla == "2":
            falar_interrompendo(
                "Você escolheu transformar uma matriz.", imprimir=True
            )
            esperar_voz()
            menu_transformar()
        elif tecla == "3":
            falar_interrompendo("Programa encerrado. Até logo.", imprimir=True)
            esperar_voz()
            return
        else:
            falar_interrompendo(
                "Opção inválida. Pressione um, dois ou três.", imprimir=True
            )


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


def main():
    try:
        caixa_titulo("CLASSIFICADOR DE MATRIZES")
        falar("Bem-vindo ao programa de classificação automática de matrizes.")
        esperar_voz()
        if MICROFONE_DISPONIVEL:
            alternar_microfone()
            esperar_voz()
        else:
            falar_interrompendo(
                "O reconhecimento por microfone está indisponível. "
                "O teclado continua funcionando normalmente."
            )
            esperar_voz()
        menu()
    except KeyboardInterrupt:
        print("\n")
        falar("Programa interrompido pelo usuário.")
        esperar_voz()
    finally:
        encerrar_voz()


if __name__ == "__main__":
    main()

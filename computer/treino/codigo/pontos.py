"""
O banco de pontos: os numeros que o treino tira de cada gravacao.

Por que existe: os videos sao grandes e mostram rosto, entao nao vao pro git
-- ficam so no computador que gravou. Antes, era o video a fonte do treino, e
um treino num computador sem os videos fazia o app ESQUECER o que ja sabia.
Agora cada gravacao e lida uma vez pelo MediaPipe, e os pontos (mao, corpo)
ficam guardados num arquivo pequeno que VAI pro git:

    gravacoes/letras/H/20261023_141500.mp4     (so neste PC)
        -> pontos/letras/H/20261023_141500.npz (no git, poucos KB)

O treino usa SEMPRE o banco inteiro: o que todo mundo ja gravou + o que voce
acabou de gravar. Gravar mais so acrescenta; nada comeca do zero.

Um arquivo por gravacao, e nao um arquivo grande, de proposito: gravacao nova
so ACRESCENTA arquivos, entao o git nunca reescreve o banco inteiro.

Tirar uma gravacao do treino: apague o .npz dela em pontos/ (e o video em
gravacoes/, senao ele e lido de novo no proximo treino).

O que cada .npz guarda (sempre os pontos CRUS, sem normalizar -- a conta de
normalizacao fica no treino, entao mudar a conta nao exige reler video):
    tipo="sequencia"  maos [quadros, 21, 2]   letra com movimento ou NADA
    tipo="fotos"      maos [fotos, 21, 2]     letra parada
    tipo="corpo"      corpo [quadros, 75, 3]  palavra: 33 pontos do corpo,
                                              21 da mao esquerda, 21 da direita
x da mao ja vem multiplicado pelo aspectX do app (0.75 * largura / altura).
NaN = nao detectado naquele quadro. float16: sobra precisao (~0.0005 num
quadro de 0 a 1, abaixo do tremor do proprio MediaPipe) e o banco fica com
metade do tamanho.

Uso, dentro de computer/:
    python treino/codigo/pontos.py             # le o que ainda nao foi lido
    python treino/codigo/pontos.py --reler     # rele tudo que tem video
"""
import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

# Suba quando a LEITURA mudar (detector, resolucao, o que e guardado): as
# gravacoes com video sao relidas sozinhas no proximo treino.
VERSAO = 1

LADO_MENOR = 480              # INPUT_SHORT_SIDE do app
TAMANHO_CORPO = (320, 240)    # 4:3, onde o aspectX do app vale 1.0
FOTO_A_CADA = 5               # letra parada gravada em video: 1 foto a cada 5 quadros
EXT_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".webm"}
EXT_FOTO = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

N_POSE, N_MAO = 33, 21

# Janelas das letras com movimento. De quantos em quantos quadros do video a
# janela e montada: a webcam grava a 30 quadros/s, mas o app classifica a
# ~13-15. Com 1, 2 e 3 o modelo ve o gesto a 30, 15 e 10 quadros/s. Video de
# celular a 60 quadros/s usa o dobro (ver passo_base), senao o gesto
# entraria no treino duas vezes mais rapido do que foi feito.
JANELA = 10
PULO = 3
PASSOS = (1, 2, 3)
QUADROS_POR_SEGUNDO = 30


# ── a conta que o app faz (LibrasMath.normalizeLandmarks) ───────────────
def normalize_landmarks(pontos):
    """Translada pro pulso (ponto 0) e divide pelo maior valor absoluto.

    Gemea de LibrasMath.normalizeLandmarks; o contrato em
    computer/tests/fixtures/landmark_contract.json prende as duas.
    """
    base_x, base_y = pontos[0]
    norm = []
    for x, y in pontos:
        norm.append(x - base_x)
        norm.append(y - base_y)
    max_v = max(abs(v) for v in norm) or 1.0
    return [v / max_v for v in norm]


def _normaliza_mao(mao):
    """[21, 2] cru -> 42 floats normalizados."""
    return np.array(normalize_landmarks(mao.astype(np.float64).tolist()), dtype=np.float32)


# ── onde estao as gravacoes ─────────────────────────────────────────────
# A rajada do gravador antigo: AAAAMMDD_HHMMSS_NN.jpg. So este formato e
# rajada -- uma foto de celular chamada 20261023_095931.jpg e uma foto so.
_RAJADA = re.compile(r"^(\d{8}_\d{6})_\d{2}$")


def id_da_gravacao(arquivo):
    """O nome que a gravacao tem no banco. As ~18 fotos de uma rajada do
    gravador antigo sao UMA gravacao; qualquer outro arquivo e uma so."""
    arquivo = Path(arquivo)
    if arquivo.suffix.lower() in EXT_FOTO:
        rajada = _RAJADA.match(arquivo.stem)
        if rajada:
            return rajada.group(1)
    return arquivo.stem


def lista_gravacoes(tipo):
    """{(rotulo, id): [arquivos]} de tudo que esta em gravacoes/<tipo>."""
    achadas = {}
    base = comum.GRAVACOES / tipo
    if not base.is_dir():
        return achadas
    for pasta in sorted(p for p in base.iterdir() if p.is_dir()):
        for arquivo in sorted(pasta.iterdir()):
            ext = arquivo.suffix.lower()
            if ext in EXT_VIDEO or (ext in EXT_FOTO and tipo == "letras"):
                achadas.setdefault((pasta.name, id_da_gravacao(arquivo)), []).append(arquivo)
    return achadas


def caminho_pontos(tipo, rotulo, ident):
    return comum.PONTOS / tipo / rotulo / (ident + ".npz")


def _versao(caminho):
    try:
        with np.load(caminho) as dados:
            return int(dados["versao"])
    except (OSError, KeyError, ValueError):
        return -1


# ── leitura com o MediaPipe ─────────────────────────────────────────────
def _reduz(imagem, interpolacao=None):
    import cv2

    altura, largura = imagem.shape[:2]
    escala = min(1.0, LADO_MENOR / min(altura, largura))
    if escala < 1.0:
        tamanho = (round(largura * escala), round(altura * escala))
        imagem = (cv2.resize(imagem, tamanho, interpolation=interpolacao)
                  if interpolacao is not None else cv2.resize(imagem, tamanho))
    return imagem


def _mao(resultado, aspecto):
    """A primeira mao detectada, [21, 2] com x corrigido; NaN se nenhuma."""
    saida = np.full((N_MAO, 2), np.nan, dtype=np.float32)
    if resultado.multi_hand_landmarks:
        marcas = resultado.multi_hand_landmarks[0].landmark
        saida[:] = [(p.x * aspecto, p.y) for p in marcas[:N_MAO]]
    return saida


def _le_sequencia(video):
    """Letra com movimento / NADA: a mao em todos os quadros, com rastreio
    entre quadros (como o app faz com a camera)."""
    import cv2
    import mediapipe as mp

    maos = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=1,
                                    model_complexity=0, min_detection_confidence=0.5,
                                    min_tracking_confidence=0.5)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    quadros = []
    try:
        while True:
            ok, imagem = cap.read()
            if not ok:
                break
            imagem = _reduz(imagem)
            altura, largura = imagem.shape[:2]
            resultado = maos.process(cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB))
            quadros.append(_mao(resultado, 0.75 * largura / altura))
    finally:
        cap.release()
        maos.close()
    return {"tipo": "sequencia", "maos": np.array(quadros).reshape(-1, N_MAO, 2), "fps": fps}


def _le_fotos(arquivos):
    """Letra parada: cada foto (ou 1 quadro a cada FOTO_A_CADA de um video)
    lida sozinha, sem rastreio -- como fotos independentes."""
    import cv2
    import mediapipe as mp

    imagens = []
    for arquivo in arquivos:
        if arquivo.suffix.lower() in EXT_FOTO:
            imagens.append(cv2.imread(str(arquivo)))
            continue
        cap = cv2.VideoCapture(str(arquivo))
        i = 0
        while True:
            ok, imagem = cap.read()
            if not ok:
                break
            if i % FOTO_A_CADA == 0:
                imagens.append(imagem)
            i += 1
        cap.release()

    maos = mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=1,
                                    model_complexity=0, min_detection_confidence=0.5)
    fotos = []
    try:
        for imagem in imagens:
            if imagem is None:
                continue
            # Foto de celular tem 12 MP; o app manda pro MediaPipe um quadro
            # com lado menor de 480. Mesma resolucao, mesmos pontos.
            imagem = _reduz(imagem, cv2.INTER_AREA)
            altura, largura = imagem.shape[:2]
            resultado = maos.process(cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB))
            fotos.append(_mao(resultado, 0.75 * largura / altura))
    finally:
        maos.close()
    return {"tipo": "fotos", "maos": np.array(fotos).reshape(-1, N_MAO, 2)}


def _le_corpo(video):
    """Palavra: corpo + as duas maos em todos os quadros, do jeito que o app
    monta os 75 pontos (BodyGestureEngine.extractFrame)."""
    import cv2
    import mediapipe as mp

    pose = mp.solutions.pose.Pose(static_image_mode=False, model_complexity=0,
                                  min_detection_confidence=0.5, min_tracking_confidence=0.5)
    maos = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=2,
                                    model_complexity=0, min_detection_confidence=0.5,
                                    min_tracking_confidence=0.5)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    largura = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640
    altura = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480
    quadros = []
    try:
        while True:
            ok, imagem = cap.read()
            if not ok:
                break
            # 4:3: o fator aspectX do app vale 1.0 nesta proporcao
            rgb = cv2.cvtColor(cv2.resize(imagem, TAMANHO_CORPO), cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            r_pose, r_maos = pose.process(rgb), maos.process(rgb)

            quadro = np.full((N_POSE + 2 * N_MAO, 3), np.nan, dtype=np.float32)
            if r_pose.pose_landmarks:
                quadro[:N_POSE] = [(p.x, p.y, p.z) for p in r_pose.pose_landmarks.landmark[:N_POSE]]
            for k, marcas in enumerate(r_maos.multi_hand_landmarks or []):
                # Mesmo criterio do Kotlin: o rotulo do MediaPipe e, sem ele,
                # o lado da tela (media de x < 0.5 = esquerda).
                lado = ""
                if r_maos.multi_handedness and k < len(r_maos.multi_handedness):
                    lado = r_maos.multi_handedness[k].classification[0].label.lower()
                if lado not in ("left", "right"):
                    lado = "left" if np.mean([p.x for p in marcas.landmark]) < 0.5 else "right"
                inicio = N_POSE if lado == "left" else N_POSE + N_MAO
                quadro[inicio:inicio + N_MAO] = [(p.x, p.y, p.z) for p in marcas.landmark[:N_MAO]]
            quadros.append(quadro)
    finally:
        cap.release()
        pose.close()
        maos.close()
    return {"tipo": "corpo", "corpo": np.array(quadros).reshape(-1, N_POSE + 2 * N_MAO, 3),
            "fps": fps, "aspecto": 0.75 * largura / altura}


def _le_e_salva(tarefa):
    """Le uma gravacao e grava o .npz dela. Roda num processo separado, entao
    recebe tudo pronto (o que ler, como, e onde salvar)."""
    rotulo, ident, arquivos, como, destino = tarefa
    videos = [a for a in arquivos if a.suffix.lower() in EXT_VIDEO]
    if como == "corpo":
        dados = _le_corpo(videos[0])
    elif como == "sequencia" and videos:
        dados = _le_sequencia(videos[0])
    else:
        dados = _le_fotos(arquivos)

    destino.parent.mkdir(parents=True, exist_ok=True)
    # Escreve noutro nome e so depois troca: um treino interrompido no meio
    # nunca deixa um .npz pela metade no banco.
    temporario = destino.with_name(ident + ".parcial.npz")
    salvar = {chave: (valor.astype(np.float16) if isinstance(valor, np.ndarray) else valor)
              for chave, valor in dados.items()}
    np.savez_compressed(temporario, versao=VERSAO,
                        origem=np.array([a.name for a in arquivos]), **salvar)
    os.replace(temporario, destino)
    return rotulo, ident, _utilizavel(dados)


def _utilizavel(dados):
    """Quantos quadros/fotos tem o que o treino precisa (mao, ou corpo)."""
    if dados["tipo"] == "corpo":
        return int(np.sum(~np.isnan(dados["corpo"][:, 0, 0])))
    return int(np.sum(~np.isnan(dados["maos"][:, 0, 0])))


def _silencia_mediapipe():
    # Os avisos do TensorFlow Lite/glog enchem a tela de linhas que nao dizem
    # nada pra quem esta treinando.
    os.environ.setdefault("GLOG_minloglevel", "2")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


def _memoria_livre_gb():
    """Memoria que ainda da pra pedir ao sistema (no Windows, o limite real
    e o de "commit", que nao cresce sem arquivo de paginacao)."""
    try:
        if sys.platform == "win32":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = Status()
            status.dwLength = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return min(status.ullAvailPhys, status.ullAvailPageFile) / 2 ** 30
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2 ** 30
    except (OSError, ValueError, AttributeError):
        return 4.0


# Memoria que cada processo de leitura usa, no pico (medido: corpo + 2 maos
# passa de 1 GB). Com processos demais o Windows recusa memoria e o processo
# morre no meio ("VirtualAlloc failed").
GB_POR_PROCESSO = {"palavras": 1.5, "letras": 0.8}


def _le_em_paralelo(pendentes, processos):
    """Le as gravacoes em `processos` processos. Devolve (rotulo, id, uteis)
    de cada uma. Se um processo morrer (falta de memoria), continua de onde
    parou com metade dos processos."""
    resultados = []
    while pendentes:
        try:
            # Sem max_tasks_per_child de proposito: no Python 3.11/3.12 ele
            # trava o pool quando um processo e trocado.
            with ProcessPoolExecutor(max_workers=processos, initializer=_silencia_mediapipe) as pool:
                for resultado in pool.map(_le_e_salva, pendentes):
                    resultados.append(resultado)
                    feitos = len(resultados)
                    if feitos % 25 == 0:
                        print("     %d lidas" % feitos, flush=True)
            return resultados
        except BrokenProcessPool:
            if processos == 1:
                raise
            prontos = {(r, i) for r, i, _ in resultados}
            pendentes = [t for t in pendentes
                         if (t[0], t[1]) not in prontos and _versao(t[4]) < VERSAO]
            processos = max(1, processos // 2)
            print("  um processo de leitura parou (memoria cheia?). Continuando com %d..."
                  % processos, flush=True)
    return resultados


def atualiza(tipo, reler=False):
    """Le as gravacoes que ainda nao estao no banco. Devolve quantas leu."""
    pendentes = []
    for (rotulo, ident), arquivos in lista_gravacoes(tipo).items():
        destino = caminho_pontos(tipo, rotulo, ident)
        if reler or _versao(destino) < VERSAO:
            como = ("corpo" if tipo == "palavras" else
                    "sequencia" if comum.eh_dinamica(rotulo) else "fotos")
            pendentes.append((rotulo, ident, arquivos, como, destino))
    if not pendentes:
        print("  nenhuma gravacao nova de %s: o banco de pontos ja esta em dia." % tipo)
        return 0

    print("  lendo %d gravacao(oes) nova(s) de %s com o MediaPipe..." % (len(pendentes), tipo),
          flush=True)
    _silencia_mediapipe()
    # Cada gravacao e independente: varios processos leem ao mesmo tempo,
    # quantos a memoria livre e os nucleos deixarem.
    processos = max(1, min(len(pendentes), (os.cpu_count() or 2) // 2, 6,
                           int(_memoria_livre_gb() / GB_POR_PROCESSO[tipo])))
    resultados = _le_em_paralelo(pendentes, processos)
    print("     %d de %d lidas" % (len(resultados), len(pendentes)), flush=True)
    vazias = ["%s/%s" % (r, i) for r, i, uteis in resultados if uteis == 0]
    if vazias:
        print("  ATENCAO: nada detectado em %d gravacao(oes): %s"
              % (len(vazias), " ".join(vazias[:8]) + (" ..." if len(vazias) > 8 else "")))
        print("  Elas nao ensinam nada. Regrave com a mao (ou o tronco) bem visivel.")
    return len(resultados)


# ── o banco, do jeito que o treino usa ──────────────────────────────────
def carrega(tipo):
    """Todas as gravacoes do banco: lista de (rotulo, id, dados)."""
    saida = []
    base = comum.PONTOS / tipo
    if not base.is_dir():
        return saida
    for arquivo in sorted(base.glob("*/*.npz")):
        if arquivo.name.endswith(".parcial.npz"):
            continue
        with np.load(arquivo, allow_pickle=False) as dados:
            conteudo = {chave: dados[chave] for chave in dados.files}
        for chave in ("maos", "corpo"):
            if chave in conteudo:
                conteudo[chave] = conteudo[chave].astype(np.float32)
        conteudo["tipo"] = str(conteudo["tipo"])
        saida.append((arquivo.parent.name, arquivo.stem, conteudo))
    return saida


def amostras_paradas(maos, a_cada=1):
    """Cada quadro/foto com mao vira uma amostra de 42 numeros."""
    return [_normaliza_mao(m) for m in maos[::a_cada] if not np.isnan(m).any()]


def trechos(maos):
    """Pedacos de quadros SEGUIDOS com mao, ja normalizados. Quando a mao some
    o trecho fecha, como no app (que recomeca a janela)."""
    saida, atual = [], []
    for m in maos:
        if np.isnan(m).any():
            if atual:
                saida.append(atual)
            atual = []
        else:
            atual.append(_normaliza_mao(m))
    if atual:
        saida.append(atual)
    return saida


def passo_base(fps):
    """Quantos quadros do video valem 1 quadro a 30/s (1 na webcam, 2 a 60/s)."""
    return max(1, int(round(float(fps) / QUADROS_POR_SEGUNDO))) if fps else 1


def janelas(lista_de_trechos, fps=QUADROS_POR_SEGUNDO):
    """Janelas de JANELA quadros (420 numeros), em cada taxa de PASSOS."""
    base = passo_base(fps)
    saida = []
    for trecho in lista_de_trechos:
        for passo in PASSOS:
            sub = trecho[::passo * base]
            pulo = max(1, PULO // passo)   # PULO e contado em quadros a 30/s
            i = 0
            while i + JANELA <= len(sub):
                saida.append(np.concatenate(sub[i:i + JANELA]))
                i += pulo
    return saida


def maos_do_corpo(dados):
    """As duas maos de uma gravacao de palavra, no formato das letras
    ([quadros, 21, 2], x corrigido). Sao maos se mexendo de verdade sem fazer
    letra -- os melhores exemplos de NADA que existem."""
    corpo = dados["corpo"]
    saida = []
    for inicio in (N_POSE, N_POSE + N_MAO):
        mao = corpo[:, inicio:inicio + N_MAO, :2].copy()
        mao[:, :, 0] *= float(dados.get("aspecto", 1.0))
        saida.append(mao)
    return saida


def main():
    ap = argparse.ArgumentParser(description="Le as gravacoes novas pro banco de pontos.")
    ap.add_argument("--reler", action="store_true",
                    help="le de novo todas as gravacoes que tem video neste PC")
    ap.add_argument("tipos", nargs="*", default=["letras", "palavras"],
                    help="letras, palavras ou os dois (padrao)")
    args = ap.parse_args()
    for tipo in args.tipos:
        if tipo not in ("letras", "palavras"):
            ap.error("tipo desconhecido: %s" % tipo)
        atualiza(tipo, reler=args.reler)
    return 0


if __name__ == "__main__":
    sys.exit(main())

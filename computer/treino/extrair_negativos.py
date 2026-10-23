"""
Extrai os clipes de "Nada" (data/raw_negativos/NADA/) em dois datasets de
exemplos NEGATIVOS -- mao a mostra que nao esta fazendo letra nenhuma.

Pra que servem: os modelos individuais sao perguntas de sim/nao ("isto e um
E?"). Se os unicos exemplos de "nao" que eles virem forem OUTRAS LETRAS, eles
nunca aprendem como e uma mao que nao esta sinalizando nada -- e no app
respondem "sim!" pra qualquer gesto solto. Estes clipes sao justamente esses
exemplos que faltavam. O modelo geral das letras com movimento tambem passa a
ter uma classe NADA com eles (ver exportar_onnx.py).

Entrada:  data/raw_negativos/NADA/*.mp4
          data/raw_body_videos/<GESTO>/*.mp4   (so pro dataset dinamico)
Saida:    data/dataset_negativos_static.npz    X [N, 42]
          data/dataset_negativos_dynamic.npz   X [M, 420], grupo [M]

Os videos de gesto de corpo entram como "nada" das letras com movimento: sao
maos se mexendo de verdade (AJUDAR, PESSOA, SURDO...) sem fazer H, J, K, X
nem Z -- exatamente o que o app confundia com letra. Nao entram no estatico:
uma mao parada no meio de um sinal pode ter o formato de uma letra. Ler esses
videos demora; o resultado fica em data/cache_negativos_corpo.npz e so e
refeito quando algum deles muda.

Usa exatamente a mesma normalizacao dos outros extractors (e do app), a mesma
correcao de proporcao (aspectX) e as mesmas taxas de quadros (PASSOS) do
extract_from_videos.py.

Uso:
    python treino/extrair_negativos.py
    python treino/extrair_negativos.py --sem-corpo   # so os clipes de Nada
"""
import argparse
import sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "data" / "raw_negativos"
PASTA_CORPO = RAIZ / "data" / "raw_body_videos"
SAIDA_ESTATICO = RAIZ / "data" / "dataset_negativos_static.npz"
SAIDA_DINAMICO = RAIZ / "data" / "dataset_negativos_dynamic.npz"
CACHE_CORPO = RAIZ / "data" / "cache_negativos_corpo.npz"

JANELA = 10      # igual ao extract_from_videos.py
PULO = 3
PASSOS = (1, 2, 3)
LADO_MENOR = 480
STRIDE_FRAME = 3  # 1 quadro a cada 3, pro dataset estatico nao ficar repetitivo


def normalize_landmarks(pontos):
    """Cópia fiel de extract_from_videos.py / LibrasMath.normalizeLandmarks."""
    base_x, base_y = pontos[0]
    norm = []
    for x, y in pontos:
        norm.append(x - base_x)
        norm.append(y - base_y)
    max_v = max(abs(v) for v in norm) or 1.0
    return [v / max_v for v in norm]


def janelas_dos_trechos(trechos):
    """Mesma montagem de janelas do extract_from_videos.py."""
    janelas = []
    for trecho in trechos:
        for passo in PASSOS:
            sub = trecho[::passo]
            pulo = max(1, PULO // passo)
            j = 0
            while j + JANELA <= len(sub):
                janelas.append(np.array(sub[j:j + JANELA]).flatten())
                j += pulo
    return janelas


def le_video(caminho, hands, maos):
    """Devolve, por mao (esquerda/direita do MediaPipe), os trechos de quadros
    seguidos com aquela mao visivel, e os quadros soltos pro estatico."""
    cap = cv2.VideoCapture(str(caminho))
    trechos = {"Left": [[]], "Right": [[]]}
    soltos = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        altura, largura = frame.shape[:2]
        escala = min(1.0, LADO_MENOR / min(altura, largura))
        if escala < 1.0:
            frame = cv2.resize(frame, (round(largura * escala), round(altura * escala)))
        aspecto = 0.75 * largura / altura   # aspectX do app
        resultado = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        vistos = set()
        for k, marcas in enumerate(resultado.multi_hand_landmarks or []):
            lado = "Left"
            if resultado.multi_handedness and k < len(resultado.multi_handedness):
                lado = resultado.multi_handedness[k].classification[0].label
            if lado in vistos or lado not in trechos:
                continue
            vistos.add(lado)
            dados = normalize_landmarks([[lm.x * aspecto, lm.y] for lm in marcas.landmark])
            trechos[lado][-1].append(dados)
            if maos == 1 and i % STRIDE_FRAME == 0:
                soltos.append(dados)
        for lado, lista in trechos.items():
            if lado not in vistos and lista[-1]:
                lista.append([])   # mesma regra do extract_from_videos
        i += 1
    cap.release()
    return [t for lista in trechos.values() for t in lista if t], soltos


def maos_do_corpo(clipes):
    """Janelas das maos dos videos de corpo. Ler 200 videos com duas maos
    leva dezenas de minutos, e o Treinar.bat roda isto toda vez: o resultado
    fica em CACHE_CORPO e so e refeito quando um video muda (ou a montagem
    das janelas muda)."""
    assinatura = ["janela=%d pulo=%d passos=%s lado=%d" % (JANELA, PULO, PASSOS, LADO_MENOR)] + [
        "%s|%d|%d" % (c.relative_to(PASTA_CORPO).as_posix(), c.stat().st_size, int(c.stat().st_mtime))
        for c in clipes]
    if CACHE_CORPO.exists():
        guardado = np.load(CACHE_CORPO, allow_pickle=True)
        if list(guardado["assinatura"]) == assinatura:
            print("Maos dos videos de corpo: usando o que ja foi lido (%s)." % CACHE_CORPO.name)
            return list(guardado["X"]), list(guardado["grupo"])

    print("Lendo as maos de %d video(s) de gesto de corpo (demora; so na primeira vez)..."
          % len(clipes), flush=True)
    hands = mp.solutions.hands.Hands(
        static_image_mode=False, max_num_hands=2, model_complexity=0,
        min_detection_confidence=0.5, min_tracking_confidence=0.5,
    )
    janelas, nomes = [], []
    for caminho in clipes:
        trechos, _ = le_video(caminho, hands, maos=2)
        novas = janelas_dos_trechos(trechos)
        janelas += novas
        nomes += ["CORPO/%s/%s" % (caminho.parent.name, caminho.name)] * len(novas)
    hands.close()
    np.savez(CACHE_CORPO, X=np.array(janelas, dtype=np.float32).reshape(-1, JANELA * 42),
             grupo=np.array(nomes), assinatura=np.array(assinatura))
    return janelas, nomes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-corpo", action="store_true",
                    help="nao usa os videos de gesto de corpo como negativos")
    args = ap.parse_args()

    clipes_nada = []
    if PASTA.exists():
        for sub in sorted(PASTA.iterdir()):
            if sub.is_dir():
                clipes_nada += sorted(list(sub.glob("*.mp4")) + list(sub.glob("*.mov")))
    clipes_corpo = []
    if not args.sem_corpo and PASTA_CORPO.exists():
        for sub in sorted(PASTA_CORPO.iterdir()):
            if sub.is_dir():
                clipes_corpo += sorted(sub.glob("*.mp4"))

    if not clipes_nada:
        print("⏭  Nenhum clipe em data/raw_negativos.")
        print("   Grave alguns no modo 'nada' do Gravar.bat (mao a toa, cocando a")
        print("   cabeca, gesticulando) -- eles deixam os modelos individuais")
        print("   MUITO menos propensos a reconhecer letra onde nao tem.")
        if not clipes_corpo:
            return 0

    estaticos, dinamicos, grupos = [], [], []

    if clipes_nada:
        print("Lendo %d clipe(s) de 'Nada'..." % len(clipes_nada))
        hands = mp.solutions.hands.Hands(
            static_image_mode=False, max_num_hands=1, model_complexity=0,
            min_detection_confidence=0.5, min_tracking_confidence=0.5,
        )
        for caminho in clipes_nada:
            trechos, soltos = le_video(caminho, hands, maos=1)
            estaticos += soltos
            janelas = janelas_dos_trechos(trechos)
            dinamicos += janelas
            grupos += ["NADA/%s" % caminho.name] * len(janelas)
        hands.close()

    if clipes_corpo:
        janelas, nomes = maos_do_corpo(clipes_corpo)
        dinamicos += janelas
        grupos += nomes
        print("   %d janelas de maos de gesto de corpo" % len(janelas))

    if estaticos:
        np.savez(SAIDA_ESTATICO, X=np.array(estaticos, dtype=np.float32))
        print("✅ %d amostras negativas estaticas  -> %s"
              % (len(estaticos), SAIDA_ESTATICO.name))
    elif clipes_nada:
        print("⚠  Nenhum quadro com mao visivel nos clipes de 'Nada'.")
        print("   Lembre: a mao precisa APARECER (so que sem fazer letra).")

    if dinamicos:
        np.savez(SAIDA_DINAMICO, X=np.array(dinamicos, dtype=np.float32),
                 grupo=np.array(grupos))
        print("✅ %d amostras negativas dinamicas  -> %s"
              % (len(dinamicos), SAIDA_DINAMICO.name))

    return 0


if __name__ == "__main__":
    sys.exit(main())

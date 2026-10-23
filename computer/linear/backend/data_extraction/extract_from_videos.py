"""
Extrai landmarks dos vídeos e salva como dataset para treinar a MLP.

Estrutura esperada:
  videos/
    H/  video1.mp4  video2.mp4 ...
    J/  ...
    K/  ...
    X/  ...
    Z/  ...

Gera: computer/data/dataset_dynamic.npz
  X     [N, 420]  janelas de 10 quadros (10 * 42 valores)
  y     [N]       letra
  grupo [N]       de que vídeo saiu a janela. Janelas do mesmo vídeo são
                  quase iguais, então a avaliação honesta separa treino e
                  teste por vídeo (exportar_onnx.py usa isto).
"""
import cv2
import mediapipe as mp
import numpy as np
import os
from pathlib import Path

# Windows + console cp1252 quebra nos prints com "→"/"✅" abaixo
# (UnicodeEncodeError). Força UTF-8 na saída, sem alterar as mensagens.
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============ CONFIGURAÇÃO ============
# Caminhos ancorados no próprio arquivo, não no diretório de onde se chama o
# script: data_extraction -> backend -> linear -> computer.
RAIZ          = Path(__file__).resolve().parents[3]
PASTA_VIDEOS  = str(RAIZ / "data" / "raw_videos")   # pasta raiz com subpastas por letra
JANELA        = 10                        # quantos frames por amostra
PULO          = 3                         # pula N frames do vídeo entre janelas (evita amostras idênticas)
SAIDA         = str(RAIZ / "data" / "dataset_dynamic.npz")
# De quantos em quantos quadros do vídeo a janela é montada. O vídeo tem 30
# quadros/s, mas o app classifica a ~13-15: lá, 10 quadros cobrem ~0,7s de
# gesto, enquanto 10 quadros seguidos do vídeo cobrem só 0,33s. Treinar só
# com quadros seguidos ensinava o gesto numa velocidade que o celular nunca
# vê. Com 1, 2 e 3 o modelo vê o gesto a 30, 15 e 10 quadros/s.
PASSOS        = (1, 2, 3)
# Lado menor da imagem que vai pro MediaPipe -- o mesmo INPUT_SHORT_SIDE do
# app. Antes todo vídeo era espremido em 320x240, o que além de perder
# detalhe achatava o vídeo de celular (retrato) em paisagem.
LADO_MENOR    = 480
# ======================================

def normalize_landmarks(pontos):
    base_x, base_y = pontos[0]
    norm = []
    for x, y in pontos:
        norm.append(x - base_x)
        norm.append(y - base_y)
    max_v = max(abs(v) for v in norm) or 1.0
    return [v / max_v for v in norm]

def janelas_dos_trechos(trechos):
    """Janelas de todos os trechos com mão, em cada taxa de PASSOS."""
    janelas = []
    for trecho in trechos:
        for passo in PASSOS:
            sub = trecho[::passo]
            # PULO é contado em quadros do vídeo, não da sequência reduzida
            pulo = max(1, PULO // passo)
            i = 0
            while i + JANELA <= len(sub):
                janelas.append(np.array(sub[i:i + JANELA]).flatten())  # 10 * 42 = 420 valores
                i += pulo
    return janelas

hands = mp.solutions.hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=0,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

X_all, y_all, g_all = [], [], []
total_videos = 0
letras = sorted([d for d in os.listdir(PASTA_VIDEOS)
                 if os.path.isdir(os.path.join(PASTA_VIDEOS, d))])
print(f"Letras encontradas: {letras}\n")

for letra in letras:
    pasta = Path(PASTA_VIDEOS) / letra
    videos = list(pasta.glob("*.mp4")) + list(pasta.glob("*.mov"))
    total_videos += len(videos)
    amostras_letra = 0
    sem_janela = 0

    for video_path in videos:
        cap = cv2.VideoCapture(str(video_path))
        trechos = [[]]  # landmarks de cada frame, em trechos com a mão visível

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            altura, largura = frame.shape[:2]
            escala = min(1.0, LADO_MENOR / min(altura, largura))
            if escala < 1.0:
                frame = cv2.resize(frame, (round(largura * escala), round(altura * escala)))
            # O mesmo aspectX do app (LibrasAnalyzer): leva o x pra proporção
            # 4:3 deitada em que o modelo é ensinado. Em 640x480 vale 1.0, e
            # o vídeo de celular em pé deixa de entrar com a mão esticada.
            aspecto = 0.75 * largura / altura
            rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            if results.multi_hand_landmarks:
                pontos = [[lm.x * aspecto, lm.y] for lm in results.multi_hand_landmarks[0].landmark]
                dados  = normalize_landmarks(pontos)
                trechos[-1].append(dados)
            elif trechos[-1]:
                # frame sem mão: fecha o trecho. Antes isto jogava fora tudo
                # o que veio antes, e só o último trecho do vídeo contava.
                trechos.append([])

        cap.release()

        janelas = janelas_dos_trechos(trechos)
        if not janelas:
            sem_janela += 1
        for janela in janelas:
            X_all.append(janela)
            y_all.append(letra)
            g_all.append(f"{letra}/{video_path.name}")
        amostras_letra += len(janelas)

    aviso = f"  ({sem_janela} sem {JANELA} quadros seguidos com mão)" if sem_janela else ""
    print(f"  {letra}: {len(videos)} vídeos → {amostras_letra} amostras{aviso}")

hands.close()

# Dois casos bem diferentes que antes davam a mesma mensagem (enganosa):
# não existir vídeo NENHUM (normal — é só não ter gravado ainda) e existir
# vídeo mas nenhum servir (aí sim é problema nos clipes).
if total_videos == 0:
    print("\n⏭  Nenhum vídeo encontrado em 'raw_videos'.")
    print("   Isso é normal se você ainda não gravou letras com movimento")
    print("   (H, J, K, X, Z). Nada a fazer aqui — seguindo em frente.")
    raise SystemExit(0)

if len(X_all) == 0:
    print(f"\n❌ Achei {total_videos} vídeo(s), mas nenhuma amostra saiu deles:")
    print(f"   nenhum teve {JANELA} quadros seguidos com a mão visível.")
    print("   Regrave mantendo a mão dentro do quadro do início ao fim do clipe.")
    raise SystemExit(1)

X = np.array(X_all, dtype=np.float32)
y = np.array(y_all)

np.savez(SAIDA, X=X, y=y, grupo=np.array(g_all))
print(f"\n✅ Dataset salvo em '{SAIDA}'")
print(f"   Total de amostras: {len(X)}")
print(f"   Shape X: {X.shape}")
print(f"   Distribuição: { {l: int((y==l).sum()) for l in letras} }")

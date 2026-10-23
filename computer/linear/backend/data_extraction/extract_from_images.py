"""
Extrai landmarks de IMAGENS estáticas e salva dataset para treinar MLP estático.

Estrutura esperada:
  imagens/
    A/  foto1.jpg  foto2.png ...
    B/  ...
    C/  ...
    ...

Gera: computer/data/dataset_static.npz
  X     [N, 42]  21 pontos * x,y
  y     [N]      letra
  grupo [N]      de que gravação saiu a foto (ver grupo_da_foto)
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
PASTA_IMAGENS = str(RAIZ / "data" / "raw_images")   # pasta raiz com subpastas por letra
SAIDA         = str(RAIZ / "data" / "dataset_static.npz")
EXTENSOES     = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
LADO_MENOR    = 480   # o INPUT_SHORT_SIDE do app
# ======================================

def normalize_landmarks(pontos):
    base_x, base_y = pontos[0]
    norm = []
    for x, y in pontos:
        norm.append(x - base_x)
        norm.append(y - base_y)
    max_v = max(abs(v) for v in norm) or 1.0
    return [v / max_v for v in norm]

hands = mp.solutions.hands.Hands(
    static_image_mode=True,       # True para imagens estáticas
    max_num_hands=1,
    model_complexity=0,
    min_detection_confidence=0.5,
)

def grupo_da_foto(img_path):
    """A gravação de onde a foto saiu. O Gravar.bat tira ~18 fotos quase
    iguais por gravação (AAAAMMDD_HHMMSS_NN.jpg); a avaliação honesta separa
    treino e teste por gravação, não por foto."""
    prefixo, _, sufixo = img_path.stem.rpartition("_")
    return f"{img_path.parent.name}/{prefixo if prefixo and sufixo.isdigit() else img_path.stem}"

X_all, y_all, g_all = [], [], []
letras = sorted([d for d in os.listdir(PASTA_IMAGENS)
                 if os.path.isdir(os.path.join(PASTA_IMAGENS, d))])
print(f"Letras encontradas: {letras}\n")

for letra in letras:
    pasta = Path(PASTA_IMAGENS) / letra
    imagens = [p for p in pasta.iterdir() if p.suffix.lower() in EXTENSOES]
    amostras_letra = 0
    falhas = 0

    for img_path in imagens:
        frame = cv2.imread(str(img_path))
        if frame is None:
            falhas += 1
            continue

        altura, largura = frame.shape[:2]
        # Foto de celular tem 12 MP; o app manda pro MediaPipe um quadro com
        # lado menor de 480 (INPUT_SHORT_SIDE). Mesma resolução, mesmo ponto.
        escala = min(1.0, LADO_MENOR / min(altura, largura))
        if escala < 1.0:
            frame = cv2.resize(frame, (round(largura * escala), round(altura * escala)),
                               interpolation=cv2.INTER_AREA)
        # O aspectX do app (LibrasAnalyzer): leva o x pra proporção 4:3
        # deitada. Em 640x480 vale 1.0; sem isto uma foto de celular em pé
        # entrava com a mão deformada na horizontal em relação ao que o app
        # vê.
        aspecto = 0.75 * largura / altura
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        if results.multi_hand_landmarks:
            pontos = [[lm.x * aspecto, lm.y] for lm in results.multi_hand_landmarks[0].landmark]
            dados  = normalize_landmarks(pontos)   # 42 valores (21 pontos * x,y)
            X_all.append(dados)
            y_all.append(letra)
            g_all.append(grupo_da_foto(img_path))
            amostras_letra += 1
        else:
            falhas += 1

    print(f"  {letra}: {len(imagens)} imagens → {amostras_letra} amostras  "
          f"({falhas} sem mão detectada)")

hands.close()

if len(X_all) == 0:
    print("\n❌ Nenhuma amostra extraída! Verifique as imagens e a pasta.")
else:
    X = np.array(X_all, dtype=np.float32)
    y = np.array(y_all)

    np.savez(SAIDA, X=X, y=y, grupo=np.array(g_all))
    print(f"\n✅ Dataset salvo em '{SAIDA}'")
    print(f"   Total de amostras: {len(X)}")
    print(f"   Shape X: {X.shape}")
    print(f"   Distribuição: { {l: int((y==l).sum()) for l in letras} }")

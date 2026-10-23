"""Da pra fazer os sinais de corpo EM SEQUENCIA, sem esperar a palavra aparecer?

Hoje o app so classifica quando a mao PARA (BODY_END_MOTION por alguns
quadros). Sinalizando sem pausa, a mao nunca para: a captura so fecha no teto
de 2 s e o trecho entregue ao modelo mistura o fim de um sinal com o comeco do
outro.

Este teste monta "frases" emendando clipes de sinais diferentes SEM pausa
(cada clipe aparado ao trecho com movimento) na taxa do aparelho, e compara:

  atual     -> a maquina de captura do app (BodyGestureEngine), sem cooldown
  janela    -> janela deslizante: classifica os ultimos W quadros a cada
               quadro e confirma a palavra quando ela vence K vezes seguidas

Os clipes sao os mesmos do treino, entao os numeros absolutos sao otimistas;
o que vale e a COMPARACAO entre os dois jeitos.

Uso, dentro de computer/:  python treino/diagnostico/testa_continuo.py
"""
import sys
import time
from pathlib import Path

import numpy as np
import tensorflow as tf

sys.path.insert(0, str(Path(__file__).parent))
from experimento import CACHE, movimento  # noqa: E402

COMPUTER = Path(__file__).resolve().parents[2]
REPO = COMPUTER.parent
sys.path.insert(0, str(COMPUTER / "treino" / "codigo"))
import treinar_palavras as tc  # noqa: E402

ATIVO = REPO / "mobile/app/src/main/assets/gestos/geral"
FPS_TREINO, FPS_APP = 30.0, 13.0
CONFIANCA = 0.95   # BODY_CONFIANCA_CONTINUA (a maquina atual usa 0.85, ver atual())
N_FRASES, SINAIS_POR_FRASE = 300, 3


def taxa_do_app(quadros):
    idx = np.arange(0, len(quadros), FPS_TREINO / FPS_APP).astype(int)
    return [quadros[i] for i in idx if i < len(quadros)]


def apara(quadros):
    """Corta o repouso do comeco e do fim: sobra so o sinal."""
    movs = [movimento(quadros[max(0, i - 4):i + 1]) for i in range(len(quadros))]
    ativos = [i for i, m in enumerate(movs) if m > 0.030]
    if not ativos:
        return quadros
    return quadros[max(0, ativos[0] - 2):ativos[-1] + 1]


class Modelo:
    def __init__(self):
        self.rot = [l.strip() for l in (ATIVO / "labels.txt").read_text().splitlines()
                    if l.strip()]
        self.it = tf.lite.Interpreter(model_path=str(ATIVO / "model.tflite"))
        self.it.allocate_tensors()
        self.ent = self.it.get_input_details()[0]["index"]
        self.sai = self.it.get_output_details()[0]["index"]
        self.chamadas, self.tempo = 0, 0.0

    def __call__(self, quadros):
        x = np.array(tc.reamostra(quadros), dtype=np.float32)[None, ...]
        t0 = time.perf_counter()
        self.it.set_tensor(self.ent, x)
        self.it.invoke()
        p = self.it.get_tensor(self.sai)[0]
        self.tempo += time.perf_counter() - t0
        self.chamadas += 1
        return self.rot[int(p.argmax())], float(p.max())


def atual(stream, modelo):
    """BodyGestureEngine.processarFrame, com teto de 2 s e sem cooldown."""
    teto = int(2.0 * FPS_APP)
    buf, capt, gesto, ini, fim = [], False, [], 0, 0
    saida, ultima = [], ""
    for t, q in enumerate(stream):
        buf.append(q)
        if len(buf) > 5:
            buf.pop(0)
        mov = movimento(buf)
        if not capt:
            if len(buf) >= 5 and mov > 0.050:
                ini += 1
                if ini >= 3:
                    capt, gesto, fim = True, list(buf), 0
            else:
                ini = 0
        else:
            gesto.append(q)
            fim = fim + 1 if mov < 0.030 else 0
            if fim >= 5 or len(gesto) >= teto:
                capt, ini = False, 0
                if len(gesto) >= 10:
                    p, c = modelo(gesto)
                    if c >= 0.85 and p != "NEUTRO" and p != ultima:
                        saida.append((p, t))
                        ultima = p
    return saida


def janela(stream, modelo, w, k):
    """BodyGestureEngine.processarContinuo: classifica os ultimos w quadros a
    cada quadro e confirma com k votos. A mesma palavra nunca entra duas vezes
    seguidas (compara com a ultima escrita)."""
    saida = []
    candidato, votos = "", 0
    for t in range(w, len(stream) + 1):
        p, c = modelo(stream[t - w:t])
        if c >= CONFIANCA and p != "NEUTRO":
            votos = votos + 1 if p == candidato else 1
            candidato = p
            if votos >= k and (not saida or saida[-1][0] != p):
                saida.append((p, t - 1))
        else:
            candidato, votos = "", 0
    return saida


def lcs(a, b):
    m = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a)):
        for j in range(len(b)):
            m[i + 1][j + 1] = m[i][j] + 1 if a[i] == b[j] else max(m[i][j + 1], m[i + 1][j])
    return m[-1][-1]


def main():
    d = np.load(CACHE, allow_pickle=True)
    seqs, rotulos = d["seqs"], d["rotulos"]
    clipes = {}
    for s, r in zip(seqs, rotulos):
        if r != "NEUTRO":
            clipes.setdefault(r, []).append(apara(taxa_do_app(list(s))))
    gestos = sorted(clipes)
    print("sinais: %s | %d frases de %d sinais emendados, %.0f quadros/s"
          % (" ".join(gestos), N_FRASES, SINAIS_POR_FRASE, FPS_APP))

    rs = np.random.RandomState(0)
    frases = []
    for _ in range(N_FRASES):
        seq = []
        while len(seq) < SINAIS_POR_FRASE:
            g = gestos[rs.randint(len(gestos))]
            if not seq or seq[-1] != g:
                seq.append(g)
        partes = [clipes[g][rs.randint(len(clipes[g]))] for g in seq]
        fins = list(np.cumsum([len(p) for p in partes]) - 1)
        frases.append((seq, [q for p in partes for q in p], fins))

    modelo = Modelo()
    jeitos = [("atual (para e classifica)", lambda s: atual(s, modelo))]
    # Os valores do app (BODY_JANELA_CONTINUA, BODY_VOTOS_CONTINUO,
    # BODY_CONFIANCA_CONTINUA): a varredura que os escolheu esta no
    # comentario deles em LibrasAnalyzer.kt.
    jeitos.append(("continuo (10 quadros, 5 votos)", lambda s: janela(s, modelo, 10, 5)))

    print("\n%-28s %8s %9s %7s %12s" % ("", "frase ok", "palavras", "extras", "atraso med."))
    for nome, fn in jeitos:
        exatas = acertos = extras = total = 0
        atrasos = []
        for seq, stream, fins in frases:
            saida = fn(stream)
            ditas = [p for p, _ in saida]
            exatas += ditas == seq
            comuns = lcs(seq, ditas)
            acertos += comuns
            extras += len(ditas) - comuns
            total += len(seq)
            # atraso: do fim do sinal ate a palavra certa aparecer
            for g, fim in zip(seq, fins):
                ts = [t for p, t in saida if p == g and t >= fim - 15]
                if ts:
                    atrasos.append((ts[0] - fim) / FPS_APP)
        print("%-28s %7.0f%% %8.0f%% %7d %10.2f s" % (
            nome, 100.0 * exatas / len(frases), 100.0 * acertos / total, extras,
            float(np.median(atrasos)) if atrasos else float("nan")))

    print("\ncusto: %.1f ms por classificacao no PC" % (1000 * modelo.tempo / modelo.chamadas))


if __name__ == "__main__":
    main()

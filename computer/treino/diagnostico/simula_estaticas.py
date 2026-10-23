"""O que o app responde em cada foto de letra parada -- de perto e de longe?

Passa as fotos de computer/data/raw_images pelo detector do app
(hand_landmarker.task) e pela mesma decisao do LetraEngine
(classificarEstaticoOrientado: individuais prioritarios -> modelo geral ->
reforcos restritos, com a regra de concordancia do U, e o espelho quando a
orientacao direta nao responde). Os limiares sao lidos do LibrasAnalyzer.kt.

"Longe" e simulado encolhendo a foto dentro de um quadro do mesmo tamanho: a
mao fica menor, como fica quando a pessoa se afasta. Foi assim que apareceu o
D que so saia de perto -- a 60% do tamanho ele ja virava L.

Rode de dentro de computer/:

    python treino\\diagnostico\\simula_estaticas.py          # todas as letras
    python treino\\diagnostico\\simula_estaticas.py C D V    # so estas

Atencao: se o modelo de uma letra foi treinado com estas mesmas fotos, o
acerto de perto sai otimista. O que esta tabela mostra bem e o que acontece
de longe e com a outra mao.
"""
import collections
import re
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMPUTER = Path(__file__).resolve().parents[2]
REPO = COMPUTER.parent
FOTOS = COMPUTER / "data" / "raw_images"
APP = REPO / "mobile" / "app" / "src" / "main"
ASSETS = APP / "assets"
ESTATICAS = ASSETS / "letras_estaticas"
KOTLIN = APP / "java" / "com" / "visuall" / "app" / "libras" / "LibrasAnalyzer.kt"

ESCALAS = (1.0, 0.75, 0.55, 0.4)


def constantes_do_app():
    texto = KOTLIN.read_text(encoding="utf-8")
    return {nome: float(valor.replace("_", "")) for nome, valor in
            re.findall(r"const val (\w+)\s*=\s*([0-9][0-9_.]*)[fL]?\b", texto)}


C = constantes_do_app()


class Decisao:
    """LetraEngine.classificarEstatico, sem Android."""

    def __init__(self):
        import onnxruntime as ort

        sessao = lambda p: ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
        self.geral = sessao(ESTATICAS / "geral" / "model.onnx")
        self.labels = (ESTATICAS / "geral" / "labels.txt").read_text(encoding="utf-8").split()
        arq = ESTATICAS / "reforcos_restritos.txt"
        self.restritos = set(arq.read_text().split()) if arq.exists() else set()
        self.ind = {l: sessao(ESTATICAS / l / "model.onnx") for l in self.labels
                    if (ESTATICAS / l / "model.onnx").exists()}
        self.prioritarios = [k for k in self.ind if k not in self.restritos]
        self.de_grupo = [k for k in self.ind if k in self.restritos]

    @staticmethod
    def _p(sessao, x):
        return np.asarray(sessao.run(None, {"landmarks_input": x[None].astype(np.float32)})[1])[0]

    def _individuais(self, x, nomes):
        """LetterDecision.deModelosIndividuais."""
        v = sorted(((self._p(self.ind[k], x)[1], k) for k in nomes), reverse=True)
        if not v:
            return "-"
        if len(v) == 1:
            return v[0][1] if v[0][0] >= C["CONFIANCA_INDIVIDUAL_SEM_RIVAL"] else "-"
        ok = v[0][0] >= C["CONFIANCA_INDIVIDUAL"] and v[0][0] - v[1][0] >= C["MARGEM_ESTATICA_MINIMA"]
        return v[0][1] if ok else "-"

    def orientado(self, x):
        l = self._individuais(x, self.prioritarios)
        if l != "-":
            return l
        g = self._p(self.geral, x)
        o = np.argsort(g)
        ok = g[o[-1]] >= C["CONFIANCA_MINIMA"] and g[o[-1]] - g[o[-2]] >= C["MARGEM_ESTATICA_MINIMA"]
        base = self.labels[o[-1]] if ok else "-"
        if not self.de_grupo or base == "-" or base not in self.restritos:
            return base
        reforco = self._individuais(x, self.de_grupo)
        # LetterDecision.combinarComReforcoRestrito com concordancia exigida no U
        if base == "U":
            return "U" if reforco == "U" else "-"
        if reforco == "U":
            return base
        return reforco if reforco != "-" else base

    def letra(self, x):
        d = self.orientado(x)
        if d != "-":
            return d
        xm = x.copy()
        xm[0::2] *= -1
        return self.orientado(xm)


def normaliza(p):
    n = (p - p[0]).reshape(-1)
    return n / max(np.abs(n).max(), 1e-9)


def main():
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision

    det = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(ASSETS / "hand_landmarker.task")),
        running_mode=vision.RunningMode.IMAGE, num_hands=1,
        min_hand_detection_confidence=0.4, min_hand_presence_confidence=0.4))
    D = Decisao()
    print("individuais prioritarios: %s | so dentro do grupo: %s"
          % (" ".join(D.prioritarios) or "nenhum", " ".join(D.de_grupo) or "nenhum"))

    pedidas = [a.upper() for a in sys.argv[1:]]
    letras = sorted(p.name for p in FOTOS.iterdir() if p.is_dir() and any(p.glob("*.jpg")))
    if pedidas:
        letras = [l for l in letras if l in pedidas]
    print("\nPor letra: quantas fotos o app acertaria, com a mao como gravada e a outra")
    print("mao (espelho), e o que ele responde no lugar quando erra. 'altura' = quanto")
    print("do quadro a mao ocupa (perto ~0.35, braco esticado ~0.20, um passo atras ~0.14).")
    for letra in letras:
        fotos = sorted((FOTOS / letra).glob("*.jpg"))
        gravacoes = len({f.stem.rpartition("_")[0] or f.stem for f in fotos})
        print("\n%s  (%d fotos de %d gravacoes)" % (letra, len(fotos), gravacoes))
        for escala in ESCALAS:
            certo = [0, 0]
            trocas = collections.Counter()
            alturas, sem_mao = [], 0
            for f in fotos:
                img = cv2.imread(str(f))
                h, w = img.shape[:2]
                if escala < 1.0:
                    peq = cv2.resize(img, (int(w * escala), int(h * escala)), interpolation=cv2.INTER_AREA)
                    tela = np.zeros_like(img)
                    y0, x0 = (h - peq.shape[0]) // 2, (w - peq.shape[1]) // 2
                    tela[y0:y0 + peq.shape[0], x0:x0 + peq.shape[1]] = peq
                    img = tela
                r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                        data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
                if not r.hand_landmarks:
                    sem_mao += 1
                    continue
                p = np.array([(q.x * 0.75 * w / h, q.y) for q in r.hand_landmarks[0]], dtype=np.float32)
                alturas.append(p[:, 1].max() - p[:, 1].min())
                for k, pp in enumerate((p, p * np.array([-1, 1], dtype=np.float32))):
                    resposta = D.letra(normaliza(pp))
                    certo[k] += resposta == letra
                    if resposta != letra:
                        trocas[resposta] += 1
            n = len(fotos) - sem_mao
            print("  altura %.2f  gravada %2d/%2d  outra mao %2d/%2d  sem mao detectada %2d  no lugar: %s"
                  % (np.median(alturas) if alturas else 0, certo[0], n, certo[1], n, sem_mao,
                     " ".join("%s=%d" % kv for kv in trocas.most_common(4)) or "-"))
    det.close()


if __name__ == "__main__":
    main()

"""As letras com movimento saem quando devem -- e SO quando devem?

Passa os videos gravados pelo mesmo caminho que o app percorre, quadro a
quadro: o detector de mao do app (hand_landmarker.task), a medida de
movimento, o MovementGate, os modelos .onnx que estao em
mobile/app/src/main/assets/letras_dinamicas (geral + individuais, com a mesma
politica de reforcos do LetraEngine), o filtro de trajeto do J, o
DynamicLetterConsensus e o LetterCommitGate. Os limiares sao lidos do proprio
LibrasAnalyzer.kt, entao nao saem de sincronia com o app.

Mede duas coisas:
  acerto ....... em quantos videos de H/J/K/X/Z a letra certa entra na frase
                 (e em quantos entra uma letra errada). A 15 quadros/s, que e
                 a taxa do celular, com o video como gravado e espelhado (o
                 app espelha a camera frontal).
  falso ........ quantas letras entram na frase com a mao se mexendo SEM
                 fazer letra: clipes de 'nada', maos dos videos de gesto de
                 corpo e trocas entre duas letras paradas (fotos).

Nao treina nem altera nada. Rode de dentro de computer/:

    python treino\\diagnostico\\simula_dinamicas.py

Na primeira vez ele le todos os videos com o detector do app (demora; fica
guardado em diagnostico/cache_simula_dinamicas.npz e so video novo e lido de
novo). Atencao: se um modelo foi treinado com estes mesmos videos, a nota de
acerto sai otimista -- o que vale de verdade e o teste no celular com gente
que nao gravou. O numero de falsos e o mais confiavel dos dois.
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
DATA = COMPUTER / "data"
APP = REPO / "mobile" / "app" / "src" / "main"
ASSETS = APP / "assets"
DINAMICAS = ASSETS / "letras_dinamicas"
KOTLIN = APP / "java" / "com" / "visuall" / "app" / "libras" / "LibrasAnalyzer.kt"
CACHE = Path(__file__).parent / "cache_simula_dinamicas.npz"

LETRAS = ["H", "J", "K", "X", "Z"]
QUADROS_POR_SEGUNDO = 15     # taxa aproximada do celular no modo alfabeto
JANELA = 10
NO_HAND_TOLERANCE = 3


def constantes_do_app():
    """Le os `const val` numericos do LibrasAnalyzer.kt."""
    texto = KOTLIN.read_text(encoding="utf-8")
    valores = {}
    for nome, valor in re.findall(r"const val (\w+)\s*=\s*([0-9][0-9_.]*)[fL]?\b", texto):
        valores[nome] = float(valor.replace("_", ""))
    return valores


C = constantes_do_app()


# ── extracao (com cache por arquivo) ────────────────────────────────────
def detector(modo, maos):
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision

    opcoes = vision.HandLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=str(ASSETS / "hand_landmarker.task")),
        running_mode=modo, num_hands=maos,
        min_hand_detection_confidence=0.4, min_hand_presence_confidence=0.4,
        min_tracking_confidence=0.4)
    return vision.HandLandmarker.create_from_options(opcoes)


def le_video(caminho, maos):
    """[quadros, maos, 21, 2] com x ja corrigido pelo aspectX do app; NaN = sem mao."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision

    det = detector(vision.RunningMode.VIDEO, maos)
    cap = cv2.VideoCapture(str(caminho))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    quadros, i = [], 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        h, w = img.shape[:2]
        escala = min(1.0, 480 / min(h, w))   # INPUT_SHORT_SIDE
        if escala < 1.0:
            img = cv2.resize(img, (round(w * escala), round(h * escala)))
        aspecto = 0.75 * w / h
        res = det.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)),
            int(i * 1000 / fps))
        q = np.full((maos, 21, 2), np.nan, dtype=np.float32)
        for k, marcas in enumerate(res.hand_landmarks[:maos]):
            q[k] = [(p.x * aspecto, p.y) for p in marcas]
        quadros.append(q)
        i += 1
    cap.release()
    det.close()
    return np.array(quadros), fps


def le_foto(det, caminho):
    import cv2
    import mediapipe as mp

    img = cv2.imread(str(caminho))
    if img is None:
        return None
    h, w = img.shape[:2]
    escala = min(1.0, 480 / min(h, w))
    if escala < 1.0:
        img = cv2.resize(img, (round(w * escala), round(h * escala)), interpolation=cv2.INTER_AREA)
    res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
    if not res.hand_landmarks:
        return None
    return np.array([(p.x * 0.75 * w / h, p.y) for p in res.hand_landmarks[0]], dtype=np.float32)


def carrega_tudo():
    """Le (ou recupera do cache) os videos e fotos. Devolve dict chave -> item."""
    antigo = {}
    if CACHE.exists():
        dados = np.load(CACHE, allow_pickle=True)
        antigo = dados["itens"].item()
    itens = {}
    fontes = []
    for letra in LETRAS:
        fontes += [("letra", letra, v, 1) for v in sorted((DATA / "raw_videos" / letra).glob("*.mp4"))]
    for sub in sorted((DATA / "raw_negativos").glob("*")):
        fontes += [("nada", sub.name, v, 1) for v in sorted(sub.glob("*.mp4"))]
    for sub in sorted((DATA / "raw_body_videos").glob("*")):
        fontes += [("corpo", sub.name, v, 2) for v in sorted(sub.glob("*.mp4"))]
    novos = 0
    for tipo, rotulo, caminho, maos in fontes:
        chave = "%s|%d|%d" % (caminho.relative_to(DATA).as_posix(), caminho.stat().st_size,
                              int(caminho.stat().st_mtime))
        if chave in antigo:
            itens[chave] = antigo[chave]
            continue
        if novos == 0:
            print("Lendo os videos com o detector do app (so na primeira vez)...", flush=True)
        q, fps = le_video(caminho, maos)
        itens[chave] = {"tipo": tipo, "rotulo": rotulo, "nome": caminho.name, "q": q, "fps": fps}
        novos += 1
        if novos % 20 == 0:
            print("   %d videos lidos" % novos, flush=True)
    det = None
    for f in sorted((DATA / "raw_images").glob("*/*.jpg")):
        chave = "foto|%s|%d|%d" % (f.relative_to(DATA).as_posix(), f.stat().st_size, int(f.stat().st_mtime))
        if chave in antigo:
            itens[chave] = antigo[chave]
            continue
        if det is None:
            from mediapipe.tasks.python import vision
            det = detector(vision.RunningMode.IMAGE, 1)
        p = le_foto(det, f)
        itens[chave] = {"tipo": "foto", "rotulo": f.parent.name, "p": p}
    if det is not None:
        det.close()
    np.savez_compressed(CACHE, itens=np.array(itens, dtype=object))
    return {k: v for k, v in itens.items() if v.get("p", 0) is not None}


# ── o caminho do app ─────────────────────────────────────────────────────
class Modelos:
    def __init__(self):
        import onnxruntime as ort

        sessao = lambda p: ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
        self.geral = sessao(DINAMICAS / "geral" / "model.onnx")
        self.labels = [l.strip() for l in (DINAMICAS / "geral" / "labels.txt")
                       .read_text(encoding="utf-8").splitlines() if l.strip()]
        arq = DINAMICAS / "reforcos_restritos.txt"
        restritos = ({l.strip().upper() for l in arq.read_text().splitlines() if l.strip()}
                     if arq.exists() else set())
        letras = [l for l in self.labels if l.upper() != "NADA"]
        self.ind = {l: sessao(DINAMICAS / l / "model.onnx") for l in letras
                    if (DINAMICAS / l / "model.onnx").exists()}
        self.prioritarios = [k for k in self.ind if k not in restritos]
        self.restritos = [k for k in self.ind if k in restritos]
        # AjusteDinamico: os portoes dependem de o modelo ter NADA ou nao.
        self.tem_nada = len(letras) < len(self.labels)
        sufixo = "_COM_NADA" if self.tem_nada else ""
        self.limiar = C["LIMIAR_MOVIMENTO" + sufixo]
        self.cons_janelas = C["CONSENSO_DINAMICO_JANELAS" + sufixo]
        self.cons_ms = C["CONSENSO_DINAMICO_MS" + sufixo]

    def probs(self, X):
        X = X.astype(np.float32)
        out = {"geral": np.asarray(self.geral.run(None, {"landmarks_input": X})[1])}
        for k, s in self.ind.items():
            p = np.asarray(s.run(None, {"landmarks_input": X})[1])
            out[k] = p[:, 1] if p.shape[1] >= 2 else p[:, 0]
        return out


def normaliza(p):
    n = (p - p[0]).reshape(-1)
    m = np.abs(n).max()
    return (n / (m if m > 0 else 1.0)).astype(np.float32)


def std(a):
    return float(np.sqrt(np.mean((a - a.mean()) ** 2)))


def j_tem_trajeto(crua):
    """DynamicLetterMotion.jTemTrajetoSuficiente."""
    esc = [np.hypot(*(f[9] - f[0])) for f in crua]
    esc = [e for e in esc if e > 1e-4]
    if not esc:
        return False
    e = float(np.mean(esc))
    pts = np.array([f[20] for f in crua])
    sx = (pts[:, 0].max() - pts[:, 0].min()) / e
    sy = (pts[:, 1].max() - pts[:, 1].min()) / e
    tot = float(np.sum(np.hypot(*np.diff(pts, axis=0).T))) / e
    return sx >= C["J_TRAJETO_X_MIN"] and sy >= C["J_TRAJETO_Y_MIN"] and tot >= C["J_TRAJETO_TOTAL_MIN"]


def movimento(norm, crus, k, n):
    """LetraEngine.calcularMovimento sobre os n quadros que terminam em k."""
    r = np.array(norm[k - n + 1:k + 1])
    forma = std(r[:, 2]) + std(r[:, 3]) + std(r[:, 16]) + std(r[:, 17])
    rp = crus[k - n + 1:k + 1]
    escs = [e for e in (np.hypot(*(p[9] - p[0])) for p in rp) if e > 1e-4]
    cru = 0.0
    if escs:
        e = float(np.mean(escs))
        cru = max((std(np.array([p[j][0] for p in rp])) + std(np.array([p[j][1] for p in rp]))) / e
                  for j in (0, 8, 20))
    return max(forma, cru)


def prepara(quadros, ts, M):
    """Probabilidades de cada janela possivel, de uma vez (o lote e muito mais
    rapido que uma janela por vez). O movimento e calculado na simulacao,
    porque depende de quantos quadros o buffer tem desde a ultima limpeza."""
    idx = [i for i, f in enumerate(quadros) if f is not None]
    norm = [normaliza(quadros[i]) for i in idx]
    crus = [quadros[i] for i in idx]
    ks = list(range(JANELA - 1, len(idx)))
    P = {"idx": idx, "norm": norm, "crus": crus, "t": [ts[i] for i in idx],
         "row": {}, "j": {}, "mov": {}}
    if ks:
        X = np.array([np.concatenate(norm[k - JANELA + 1:k + 1]) for k in ks])
        Xe = X.copy()
        Xe[:, 0::2] *= -1
        P["pd"], P["pe"] = M.probs(X), M.probs(Xe)
        P["row"] = {k: r for r, k in enumerate(ks)}
        P["j"] = {k: j_tem_trajeto(crus[k - JANELA + 1:k + 1]) for k in ks}
    return P


def movimento_no_buffer(P, k, buf):
    """LibrasMath.quadrosNaJanela + calcularMovimento: os quadros dos ultimos
    MOVIMENTO_JANELA_MS que ainda estao no buffer, pelo menos o minimo."""
    minimo = int(C["MOVIMENTO_QUADROS_MINIMOS"])
    if buf < minimo:
        return 0.0
    t = P["t"]
    n = 0
    while n < buf and t[k] - t[k - n] <= C["MOVIMENTO_JANELA_MS"]:
        n += 1
    n = max(n, minimo)
    chave = (k, n)
    if chave not in P["mov"]:
        P["mov"][chave] = movimento(P["norm"], P["crus"], k, n)
    return P["mov"][chave]


def individuais(pont, conf_min, por_label):
    """LetterDecision.deModelosIndividuais."""
    if not pont:
        return "-"
    if len(pont) == 1:
        lab, v = pont[0]
        return lab if v >= por_label.get(lab, C["CONFIANCA_INDIVIDUAL_SEM_RIVAL"]) else "-"
    ordem = sorted(pont, key=lambda x: -x[1])
    (lab, melhor), (_, segundo) = ordem[0], ordem[1]
    lim = por_label.get(lab, conf_min)
    return lab if melhor >= lim and melhor - segundo >= C["MARGEM_DINAMICA_MINIMA"] else "-"


def orientado(pr, r, M):
    """LetraEngine.classificarDinamicoOrientado. Devolve (letra, foi_nada)."""
    if M.prioritarios:
        l = individuais([(k, float(pr[k][r])) for k in M.prioritarios], C["CONFIANCA_INDIVIDUAL"], {})
        if l != "-":
            return l, False
    g = pr["geral"][r]
    i = int(np.argmax(g))
    seg = float(np.max(np.delete(g, i))) if len(g) > 1 else 0.0
    ok = g[i] >= C["CONFIANCA_DINAMICA"] and g[i] - seg >= C["MARGEM_DINAMICA_MINIMA"]
    base = M.labels[i] if ok else "-"
    if base.upper() == "NADA":
        return "-", True
    if not M.restritos:
        return base, False
    por_label = {k: (C["CONFIANCA_REFORCO_DINAMICO_X"] if k == "X" else C["CONFIANCA_REFORCO_DINAMICO_HK"])
                 for k in M.restritos}
    reforco = individuais([(k, float(pr[k][r])) for k in M.restritos], C["CONFIANCA_INDIVIDUAL"], por_label)
    if base == "-":
        return (reforco if reforco in ("H", "K", "X") else "-"), False
    if base not in M.restritos:
        return base, False
    return reforco, False


def classifica(P, k, M):
    """LetraEngine.classificarDinamico: direto, e espelhado se o direto nao soube."""
    r = P["row"][k]
    letra, nada = orientado(P["pd"], r, M)
    if letra == "J" and not P["j"][k]:
        letra = "-"
    if letra != "-" or nada:
        return letra
    letra, _ = orientado(P["pe"], r, M)
    if letra == "J" and not P["j"][k]:
        letra = "-"
    return letra


def simula(quadros, ts, P, M):
    """Devolve as letras dinamicas que entrariam na frase."""
    pos = {i: k for k, i in enumerate(P["idx"])}
    buf = sem_mao = 0
    sust_desde = enc_desde = None
    aberto = False
    c_letra, c_desde, c_jan, c_pred, c_jan_gesto = "-", None, 0, None, 0
    em_curso = False
    ult_pred, estab_desde, ult_add, ult_t = "", None, "", None
    commits = []
    for i, t in enumerate(ts):
        if quadros[i] is None:
            sem_mao += 1
            if sem_mao >= NO_HAND_TOLERANCE:
                ult_pred, estab_desde, ult_add = "", None, ""
                sust_desde, aberto, enc_desde = None, False, None
                buf = 0
                c_letra, c_desde, c_jan, c_pred, c_jan_gesto = "-", None, 0, None, 0
                em_curso = False
            continue
        sem_mao = 0
        k = pos[i]
        buf = min(buf + 1, JANELA + 5)
        mov = movimento_no_buffer(P, k, buf)
        # MovementGate
        estado = None
        if mov > M.limiar:
            sust_desde = t if sust_desde is None else sust_desde
            if t - sust_desde >= C["MOVIMENTO_SUSTENTADO_MS"]:
                aberto, enc_desde, estado = True, None, "SUSTENTADO"
        else:
            sust_desde = None
        if estado is None:
            if not aberto:
                estado = "PARADO"
            else:
                enc_desde = t if enc_desde is None else enc_desde
                if t - enc_desde >= C["MOVIMENTO_ENCERRAMENTO_MS"]:
                    aberto, enc_desde, estado = False, None, "PARADO"
                else:
                    estado = "ENCERRANDO"
        letra, dinamico = "-", False
        if estado == "SUSTENTADO" and buf >= JANELA:
            dinamico, em_curso = True, True
            l = classifica(P, k, M)
            # DynamicLetterConsensus
            if l == "-":
                c_letra, c_desde, c_jan = "-", None, 0
            else:
                if l != c_letra:
                    c_letra, c_desde, c_jan = l, t, 0
                c_jan += 1
                if c_jan >= M.cons_janelas and t - c_desde >= M.cons_ms:
                    if c_jan > c_jan_gesto:
                        c_pred, c_jan_gesto = l, c_jan
                    letra = l
        elif estado == "ENCERRANDO":
            dinamico = True
            if em_curso:
                letra = c_pred or "-"
        elif estado == "PARADO" and em_curso:
            em_curso = False
            c_letra, c_desde, c_jan, c_pred, c_jan_gesto = "-", None, 0, None, 0
            buf = 0
        # LetterCommitGate (so o lado dinamico interessa aqui)
        if letra != "-":
            if letra != ult_pred or estab_desde is None:
                estab_desde = t
            ult_pred = letra
        else:
            estab_desde, ult_pred = None, ""
        estab = C["ESTAB_MIN_DINAMICO_MS"] if dinamico else C["ESTAB_MIN_ESTATICO_MS"]
        cool = C["COOLDOWN_DINAMICO"] if dinamico else C["COOLDOWN_ESTATICO"]
        if (estab_desde is not None and t - estab_desde >= estab and letra != "-"
                and letra != ult_add and (ult_t is None or t - ult_t > cool)):
            commits.append(letra)
            ult_add, ult_t, estab_desde = letra, t, None
    return commits


# ── streams de teste ─────────────────────────────────────────────────────
def em_quadros(arr):
    return [None if np.isnan(f).any() else f for f in arr]


def reduz(item):
    passo = max(1, round(item["fps"] / QUADROS_POR_SEGUNDO))
    return passo, 1000.0 * passo / item["fps"]


def maos_do_corpo(q):
    """Separa as duas maos de um video de corpo em dois streams, seguindo o
    pulso de quadro a quadro (o app tambem segue a mao que ja escolheu)."""
    a, b = [], []
    ant = None
    for maos in q:
        vistas = [m for m in maos if not np.isnan(m).any()]
        if not vistas:
            a.append(None); b.append(None); ant = None
            continue
        if ant is not None and len(vistas) == 2:
            if np.hypot(*(vistas[1][0] - ant)) < np.hypot(*(vistas[0][0] - ant)):
                vistas = vistas[::-1]
        a.append(vistas[0]); ant = vistas[0][0]
        b.append(vistas[1] if len(vistas) > 1 else None)
    return [s for s in (a, b) if sum(x is not None for x in s) > 10]


def trocas(fotos, n=300, semente=7):
    """Troca entre duas letras paradas: segura, transita, segura."""
    rs = np.random.RandomState(semente)
    rot = np.array([f["rotulo"] for f in fotos])
    pts = np.array([f["p"] for f in fotos])
    letras = sorted(set(rot))
    if len(letras) < 2:
        return []
    dt = 1000.0 / QUADROS_POR_SEGUNDO
    saida = []
    for _ in range(n):
        a, b = rs.choice(letras, 2, replace=False)
        fa = pts[rs.choice(np.where(rot == a)[0])]
        fb = pts[rs.choice(np.where(rot == b)[0])]
        fb = fb - fb[0] + fa[0] + rs.uniform(-0.15, 0.15, 2).astype(np.float32)
        segura, dur = int(0.6 * QUADROS_POR_SEGUNDO), int(rs.uniform(0.25, 0.7) * QUADROS_POR_SEGUNDO)
        seq = [fa + rs.normal(0, 0.002, fa.shape) for _ in range(segura)]
        for i in range(1, dur + 1):
            s = 0.5 - 0.5 * np.cos(np.pi * i / dur)
            seq.append((1 - s) * fa + s * fb + rs.normal(0, 0.002, fa.shape))
        seq += [fb + rs.normal(0, 0.002, fb.shape) for _ in range(segura)]
        seq = [x.astype(np.float32) for x in seq]
        saida.append((seq, np.arange(len(seq)) * dt))
    return saida


def main():
    print("Modelos em %s" % DINAMICAS.relative_to(REPO))
    M = Modelos()
    print("  geral: %s | individuais: %s | restritos: %s"
          % (" ".join(M.labels), " ".join(M.ind) or "nenhum", " ".join(M.restritos) or "nenhum"))
    print("  portoes (AjusteDinamico): movimento > %.2f, consenso %d janelas em %dms"
          % (M.limiar, M.cons_janelas, M.cons_ms))
    itens = carrega_tudo()

    print("\nACERTO (a letra certa entrou na frase; 'errada' = entrou outra letra tambem)")
    print("  %-6s %-22s %-22s" % ("letra", "como gravado", "espelhado (cam. frontal)"))
    total = np.zeros(4, dtype=int)
    for letra in LETRAS:
        linha = []
        for espelhar in (False, True):
            certo = errado = n = 0
            for it in itens.values():
                if it["tipo"] != "letra" or it["rotulo"] != letra:
                    continue
                passo, dt = reduz(it)
                arr = it["q"][::passo, 0].copy()
                if espelhar:
                    arr[..., 0] *= -1
                fr = em_quadros(arr)
                ts = np.arange(len(fr)) * dt
                cm = simula(fr, ts, prepara(fr, ts, M), M)
                n += 1; certo += letra in cm; errado += any(c != letra for c in cm)
            linha.append("%2d/%2d  errada %2d" % (certo, n, errado))
            total += [certo, n, 0, 0] if not espelhar else [0, 0, certo, n]
        print("  %-6s %-22s %-22s" % (letra, linha[0], linha[1]))
    print("  %-6s %2d/%2d                  %2d/%2d" % ("total", total[0], total[1], total[2], total[3]))

    print("\nFALSOS (letra com movimento entrando na frase sem ninguem fazer letra)")
    grupos = collections.defaultdict(lambda: [0, 0.0, collections.Counter()])
    for it in itens.values():
        if it["tipo"] not in ("nada", "corpo"):
            continue
        passo, dt = reduz(it)
        q = it["q"][::passo]
        streams = [em_quadros(q[:, 0])] if it["tipo"] == "nada" else maos_do_corpo(q)
        for fr in streams:
            ts = np.arange(len(fr)) * dt
            cm = simula(fr, ts, prepara(fr, ts, M), M)
            g = grupos["clipes de nada" if it["tipo"] == "nada" else "maos dos gestos de corpo"]
            g[0] += len(cm); g[1] += sum(x is not None for x in fr) * dt / 1000.0; g[2].update(cm)
    fotos = [it for it in itens.values() if it["tipo"] == "foto"]
    tr = trocas(fotos)
    disparos = collections.Counter()
    com_falso = 0
    for seq, ts in tr:
        cm = simula(seq, ts, prepara(seq, ts, M), M)
        com_falso += bool(cm); disparos.update(cm)
    for nome, (n, seg, cont) in grupos.items():
        print("  %-26s %3d letras em %4.0fs de mao visivel = %.1f por minuto  %s"
              % (nome, n, seg, 60 * n / max(seg, 1), dict(cont)))
    if tr:
        print("  %-26s %3d de %d trocas viraram letra (%.0f%%)  %s"
              % ("trocas entre letras paradas", com_falso, len(tr), 100 * com_falso / len(tr), dict(disparos)))
    if not grupos:
        print("  (sem clipes de nada nem videos de corpo para medir)")


if __name__ == "__main__":
    main()

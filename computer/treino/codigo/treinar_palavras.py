"""
Retreina o modelo de PALAVRAS do app (modo corpo) a partir do banco de pontos.

Entrada:  computer/treino/pontos/palavras/<PALAVRA>/*.npz
          (o banco inteiro: tudo que ja foi gravado + o que voce acabou de
           gravar; as gravacoes novas sao lidas pro banco antes)
Saida:    mobile/app/src/main/assets/gestos/geral/model.tflite
          mobile/app/src/main/assets/gestos/geral/labels.txt

Palavra nova nao precisa de mudanca nenhuma no app: ele le a lista do
labels.txt. A unica palavra especial e NEUTRO ("parado, sem sinal"), que o
app nunca escreve na frase -- e que precisa existir pro modelo saber quando
NAO ha sinal.

CONTRATO com o app (BodyGestureEngine.kt) -- nada disto pode mudar:

  1. entrada .......... [1, 30, 225] float32: 30 quadros x 225 numeros
  2. os 225 numeros ... 75 pontos x (x, y, z), nesta ordem exata:
                          pontos  0..32  -> corpo/pose   (33 pontos)
                          pontos 33..53  -> mao ESQUERDA (21 pontos)
                          pontos 54..74  -> mao DIREITA  (21 pontos)
                        (BodyGestureEngine.extractFrame + writeBodyPoint)
  3. saida ............ [1, n_palavras], uma probabilidade por linha do labels.txt
  4. Select TF Ops .... o LSTM nao tem kernel nativo no TFLite; o app registra
                        um FlexDelegate justamente pra isso, entao a conversao
                        PRECISA habilitar SELECT_TF_OPS.

Duas contas tem que bater exatamente com o Kotlin, senao o modelo aprende num
formato e e usado em outro -- sem dar erro, so errando mais:

  normaliza_corpo() <-> LibrasMath.normalizeBodyFrame
  reamostra()       <-> LibrasMath.resample / resampleIndex

Uso, dentro de computer/ (os .bat 1 e 2 fazem isto):
    python treino/codigo/treinar_palavras.py
    python treino/codigo/treinar_palavras.py --epocas 120
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import pontos  # noqa: E402

ASSETS = comum.ASSETS_PALAVRAS

N_POSE, N_MAO = 33, 21
N_PONTOS = N_POSE + 2 * N_MAO          # 75
N_FEATURES = N_PONTOS * 3              # 225
JANELA = 30
ESCALA_MINIMA_OMBROS = 0.0001          # LibrasMath.ESCALA_MINIMA_OMBROS
OMBRO_ESQ, OMBRO_DIR = 11, 12          # BODY_POINT_LEFT/RIGHT_SHOULDER
QUADROS_MINIMOS = 10                   # BODY_MIN_FRAMES
GRAVACOES_MINIMAS = 5                  # por palavra; o ideal e 20 ou mais

# Recortes temporais de cada gravacao: o mesmo sinal comecando/terminando um
# pouco antes ou depois -- a variacao que o corte do app introduz.
RECORTES = [(0.0, 1.0), (0.0, 0.9), (0.1, 1.0), (0.05, 0.95),
            (0.0, 0.8), (0.2, 1.0), (0.1, 0.9)]


def normaliza_corpo(frame):
    """Gemeo de LibrasMath.normalizeBodyFrame.

    Centraliza x,y no meio dos ombros e divide pela distancia 3D entre eles
    (o dz ENTRA na conta). O z fica cru, como sai do MediaPipe.
    """
    # float32 em TODA operacao, de proposito. O Kotlin faz esta conta inteira
    # em Float, entao e assim que o gemeo tem que calcular. E nao e so
    # fidelidade: com um float comum do Python no lugar (2.0, ou float(...)),
    # o resultado passa a depender da VERSAO do numpy -- no numpy 1.x um
    # escalar np.float32 dividido por float do Python sobe pra float64, e no
    # numpy 2 (NEP 50) fica em float32. As duas contas diferem por alguns ULP,
    # o bastante pra mudar a 6a casa decimal e quebrar o contrato em
    # computer/tests/fixtures/landmark_contract.json dependendo da maquina.
    saida = np.asarray(frame, dtype=np.float32).copy()
    le, ld = OMBRO_ESQ * 3, OMBRO_DIR * 3
    dois = np.float32(2.0)
    centro_x = (saida[le] + saida[ld]) / dois
    centro_y = (saida[le + 1] + saida[ld + 1]) / dois
    dx = saida[le] - saida[ld]
    dy = saida[le + 1] - saida[ld + 1]
    dz = saida[le + 2] - saida[ld + 2]
    escala = np.float32(np.sqrt(dx * dx + dy * dy + dz * dz))
    # Pose degenerada (pessoa de lado, ombro fora do quadro) daria uma escala
    # quase zero e explodiria as features -- aí não normaliza.
    if escala <= ESCALA_MINIMA_OMBROS:
        escala = np.float32(1.0)
    for ponto in range(N_PONTOS):
        base = ponto * 3
        saida[base] = (saida[base] - centro_x) / escala
        saida[base + 1] = (saida[base + 1] - centro_y) / escala
    return saida


def reamostra(frames, quantidade=JANELA):
    """Gemeo de LibrasMath.resample: escolhe quadros por indice, nao interpola."""
    if len(frames) == quantidade:
        return list(frames)
    return [frames[int((len(frames) - 1) * i / (quantidade - 1))]
            for i in range(quantidade)]


def quadros_da_gravacao(dados):
    """Os quadros de uma gravacao do banco, ja normalizados (225 cada).

    Quadro sem corpo e descartado: a escala vem dos ombros. Mao nao vista
    entra como zeros, como no app. Video de celular a 60 quadros/s e lido 1
    quadro sim, 1 nao: a captura do app (segmento_do_app) conta em quadros e
    foi medida com a webcam, a 30.
    """
    saida = []
    for quadro in dados["corpo"][::pontos.passo_base(dados.get("fps", 30))]:
        if np.isnan(quadro[0, 0]):
            continue
        saida.append(normaliza_corpo(np.nan_to_num(quadro, nan=0.0).reshape(-1)))
    return saida


# Limiares da maquina de captura do app (LibrasAnalyzer.kt). Precisam ser os
# MESMOS: e o trecho que o app entrega ao modelo que estamos ensinando.
MOV_WINDOW, START_MOTION, END_MOTION = 5, 0.050, 0.030
START_FRAMES, END_FRAMES, MIN_FRAMES, MAX_FRAMES = 3, 5, 10, 60


def _movimento(buffer):
    """bodyMotion() do app: desvio padrao das coordenadas x,y das MAOS."""
    if len(buffer) < 3:
        return 0.0
    total, n = 0.0, 0
    for ponto in range(N_POSE, N_PONTOS):
        for coord in (0, 1):
            total += float(np.std([q[ponto * 3 + coord] for q in buffer]))
            n += 1
    return total / n if n else 0.0


def _tem_mao(frame):
    return bool(np.any(frame[N_POSE * 3:]))


def segmento_do_app(quadros):
    """O trecho que a maquina de estado do app captura desta gravacao (ou None).

    O app nunca ve a gravacao inteira: ele comeca a capturar quando o
    movimento passa de START_MOTION e corta quando cai. Treinar so com a
    gravacao inteira derrubava o AJUDAR de 87% para 44% no celular.
    """
    buffer, capturando, gesto = [], False, []
    ini_cnt = fim_cnt = 0
    for frame in quadros:
        buffer.append(frame)
        if len(buffer) > MOV_WINDOW:
            buffer.pop(0)
        mov = _movimento(buffer)
        if not capturando:
            if _tem_mao(frame) and len(buffer) >= MOV_WINDOW and mov > START_MOTION:
                ini_cnt += 1
                if ini_cnt >= START_FRAMES:
                    capturando, gesto, fim_cnt = True, list(buffer), 0
            else:
                ini_cnt = 0
        else:
            gesto.append(frame)
            fim_cnt = fim_cnt + 1 if mov < END_MOTION else 0
            if fim_cnt >= END_FRAMES or len(gesto) >= MAX_FRAMES:
                return gesto if len(gesto) >= MIN_FRAMES else None
    return gesto if capturando and len(gesto) >= MIN_FRAMES else None


def amostras_da_gravacao(quadros, recortes):
    """A gravacao inteira, os recortes e o trecho que o app captura."""
    amostras = []
    for inicio, fim in recortes:
        a, b = int(len(quadros) * inicio), int(len(quadros) * fim)
        if b - a >= QUADROS_MINIMOS:
            amostras.append(np.array(reamostra(quadros[a:b]), dtype=np.float32))
    segmento = segmento_do_app(quadros)
    if segmento is not None:
        amostras.append(np.array(reamostra(segmento), dtype=np.float32))
    return amostras


# ── a outra mao ─────────────────────────────────────────────────────────
# Ter as DUAS maos na tela virou, sem querer, uma pista do que e a palavra.
# COMPUTADOR tem as duas maos em 94% dos quadros, AJUDAR em 82%, NEUTRO em 79%
# -- e PESSOA em 29%, SURDO em 12%. O modelo aprendeu "duas maos = COMPUTADOR/
# CONVERSAR" e "uma mao = PESSOA/SURDO", e errava assim que a pessoa fazia
# PESSOA com a outra mao a vista. Aqui as gravacoes de uma mao ganham copias
# com a mao de uma gravacao de NEUTRO no lugar da que faltava, e o NEUTRO ganha
# copias com uma mao so: a presenca da outra mao deixa de dizer qual e a palavra.
FATIA_ESQ = slice(N_POSE * 3, (N_POSE + N_MAO) * 3)
FATIA_DIR = slice((N_POSE + N_MAO) * 3, N_FEATURES)
JANELAS_POR_BLOCO = 15     # janelas coletadas pelo app que formam um "grupo" de teste
UMA_MAO_ATE = 0.45         # com as duas maos a vista em menos disto dos quadros = sinal de uma mao
VARIANTES_POR_GRAVACAO = 2


def maos_ausentes(quadros):
    """[n, 2]: verdadeiro onde a mao (esquerda, direita) nao foi vista. Depois
    da normalizacao os 21 pontos de uma mao nao vista saem todos iguais (eram
    zeros)."""
    x = np.asarray(quadros, dtype=np.float32).reshape(-1, N_PONTOS, 3)[:, :, 0]
    return np.stack([np.ptp(x[:, N_POSE:N_POSE + N_MAO], axis=1) < 1e-6,
                     np.ptp(x[:, N_POSE + N_MAO:], axis=1) < 1e-6], axis=1)


def fracao_com_as_duas(quadros):
    return float(1.0 - maos_ausentes(quadros).any(axis=1).mean())


def sem_a_mao(dados, lado):
    """A mesma gravacao como se uma das maos nunca tivesse aparecido."""
    copia = dict(dados)
    corpo = np.array(dados["corpo"], dtype=np.float32, copy=True)
    inicio = N_POSE + (0 if lado == 0 else N_MAO)
    corpo[:, inicio:inicio + N_MAO] = np.nan
    copia["corpo"] = corpo
    return copia


def com_a_mao_do_doador(quadros, doador):
    """Onde uma mao faltava, poe a do `doador` (um NEUTRO com as duas maos a
    vista), quadro a quadro na mesma altura do tempo. Ja esta normalizada pelos
    ombros, entao encaixa em qualquer pessoa. None se nao havia o que trocar."""
    q = np.array(quadros, dtype=np.float32, copy=True)
    ausente = maos_ausentes(q)
    if ausente.any(axis=1).mean() < 0.3:
        return None
    posicao = np.minimum((np.arange(len(q)) * len(doador) / len(q)).astype(int), len(doador) - 1)
    d = doador[posicao]
    d_ausente = maos_ausentes(d)
    mudou = False
    for lado, fatia in enumerate((FATIA_ESQ, FATIA_DIR)):
        trocar = ausente[:, lado] & ~d_ausente[:, lado]
        if trocar.any():
            q[trocar, fatia] = d[trocar, fatia]
            mudou = True
    return q if mudou else None


def monta_dataset(recortes):
    """X [N, 30, 225], y [N], grupo [N] (de que gravacao saiu), variante [N]
    (True nas copias com a outra mao a mais/a menos), quantas gravacoes cada
    palavra tem e quais palavras sao de uma mao."""
    lidas, gravacoes, curtas, do_app = [], {}, [], []
    for rotulo, ident, dados in pontos.carrega("palavras"):
        if dados["tipo"] == "janelas":
            # Coletadas pelo proprio app (coletar.py palavras): ja sao as janelas
            # de 30 quadros, normalizadas, como entram no modelo.
            do_app.append((rotulo, ident, np.asarray(dados["janelas"], dtype=np.float32)))
            gravacoes[rotulo] = gravacoes.get(rotulo, 0) + 1
            continue
        quadros = quadros_da_gravacao(dados)
        if len(quadros) < QUADROS_MINIMOS:
            curtas.append("%s/%s" % (rotulo, ident))
            continue
        gravacoes[rotulo] = gravacoes.get(rotulo, 0) + 1
        lidas.append((rotulo, ident, dados, quadros))
    if curtas:
        print("  ignoradas (corpo visivel em menos de %d quadros): %s"
              % (QUADROS_MINIMOS, " ".join(curtas)))

    com_duas = {}
    for rotulo, _, _, quadros in lidas:
        com_duas.setdefault(rotulo, []).append(fracao_com_as_duas(quadros))
    uma_mao = sorted(r for r, v in com_duas.items() if r != comum.NEUTRO and np.mean(v) < UMA_MAO_ATE)
    doadores = [np.array(q, dtype=np.float32) for r, _, _, q in lidas
                if r == comum.NEUTRO and fracao_com_as_duas(q) >= 0.6]
    sorteio = np.random.default_rng(42)

    X, y, grupos, variante = [], [], [], []

    def junta(rotulo, grupo, quadros, eh_variante):
        amostras = amostras_da_gravacao(quadros, recortes)
        X.extend(amostras)
        y.extend([rotulo] * len(amostras))
        grupos.extend([grupo] * len(amostras))
        variante.extend([eh_variante] * len(amostras))

    for rotulo, ident, dados, quadros in lidas:
        grupo = "%s/%s" % (rotulo, ident)
        junta(rotulo, grupo, quadros, False)
        if rotulo == comum.NEUTRO:
            presente = 1.0 - maos_ausentes(quadros).mean(axis=0)
            for lado in (0, 1):
                if presente[lado] >= 0.5:
                    sem = quadros_da_gravacao(sem_a_mao(dados, lado))
                    if len(sem) >= QUADROS_MINIMOS:
                        junta(rotulo, grupo, sem, True)
        elif rotulo in uma_mao and doadores:
            for _ in range(VARIANTES_POR_GRAVACAO):
                v = com_a_mao_do_doador(quadros, doadores[int(sorteio.integers(len(doadores)))])
                if v is not None:
                    junta(rotulo, grupo, list(v), True)
    for rotulo, ident, janelas in do_app:
        janelas = janelas.reshape(-1, JANELA, N_FEATURES)
        for i in range(0, len(janelas), JANELAS_POR_BLOCO):
            bloco = janelas[i:i + JANELAS_POR_BLOCO]
            X.extend(bloco)
            y.extend([rotulo] * len(bloco))
            # Em blocos: uma coleta tem centenas de janelas quase iguais e, num
            # grupo so, o teste cairia inteiro de um lado.
            grupos.extend(["%s/%s/%d" % (rotulo, ident, i // JANELAS_POR_BLOCO)] * len(bloco))
            variante.extend([False] * len(bloco))
    return (np.array(X, dtype=np.float32).reshape(-1, JANELA, N_FEATURES),
            np.array(y, dtype=str), np.array(grupos, dtype=str),
            np.array(variante, dtype=bool), gravacoes, uma_mao)


def confere_banco(gravacoes):
    """Para antes de treinar se o modelo novo ia sair pior que o do app."""
    problemas = []
    faltando = sorted(set(comum.palavras_do_app()) - set(gravacoes))
    if faltando:
        problemas.append("O app conhece %s, mas o banco nao tem nenhuma gravacao delas."
                         % " ".join(faltando))
        problemas.append("Treinar assim faria o app ESQUECER essas palavras.")
    if comum.NEUTRO not in gravacoes:
        problemas.append("Falta o NEUTRO (parado, sem sinal): sem ele o modelo nao sabe")
        problemas.append("quando NAO ha sinal e chuta uma palavra o tempo todo.")
    poucas = sorted(p for p, n in gravacoes.items() if n < GRAVACOES_MINIMAS)
    if poucas:
        problemas.append("Poucas gravacoes (minimo %d, ideal 20+): %s"
                         % (GRAVACOES_MINIMAS, ", ".join("%s %d" % (p, gravacoes[p]) for p in poucas)))
    if len(gravacoes) < 2:
        problemas.append("Precisa de pelo menos 2 palavras pra ter o que distinguir.")
    if problemas:
        print("\n  PAREI, nada foi alterado no app:")
        for linha in problemas:
            print("    " + linha)
        print("  Grave o que falta no '1 - Adicionar palavra nova.bat' ou no")
        print("  '2 - Retreinar palavras.bat' e rode de novo.")
    return not problemas


def separa_por_gravacao(y_idx, grupos):
    """80% das gravacoes pro treino e 20% pro teste, com toda palavra dos dois
    lados. Por gravacao, nunca por amostra: os recortes de uma mesma gravacao
    sao quase iguais, e com eles dos dois lados a nota sai inflada."""
    from sklearn.model_selection import GroupShuffleSplit

    indices = np.arange(len(y_idx))
    for semente in range(42, 142):
        tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=semente)
                      .split(indices, y_idx, grupos))
        if set(y_idx[te]) == set(y_idx) and set(y_idx[tr]) == set(y_idx):
            return tr, te
    return None, None


def com_ruido(X, y):
    """2 copias de cada amostra com perturbacao pequena: impede o modelo de
    decorar as posicoes exatas, que nunca se repetem igual no celular."""
    copias = [X] + [X + np.random.default_rng(s).normal(0, 0.02, X.shape).astype(np.float32)
                    for s in (1, 2)]
    return np.concatenate(copias), np.concatenate([y, y, y])


def novo_modelo(n_classes):
    import tensorflow as tf

    # LSTM bidirecional: le o sinal do fim pro comeco tambem. Sinais de corpo
    # se distinguem tanto pelo desfecho quanto pelo inicio (COMPUTADOR x
    # CONVERSAR), e a versao unidirecional confundia os dois.
    modelo = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(JANELA, N_FEATURES)),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(96)),
        tf.keras.layers.Dropout(0.25),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dense(n_classes, activation="softmax"),
    ])
    modelo.compile(optimizer="adam", loss="sparse_categorical_crossentropy",
                   metrics=["accuracy"])
    return modelo


def pesos(y_idx, n_classes):
    """Peso por palavra: sem isto o modelo prefere quem tem mais gravacoes."""
    contagem = np.bincount(y_idx, minlength=n_classes).astype(np.float64)
    return {i: (len(y_idx) / (n_classes * c) if c else 0.0) for i, c in enumerate(contagem)}


def exporta_tflite(modelo, destino):
    import tensorflow as tf

    conv = tf.lite.TFLiteConverter.from_keras_model(modelo)
    # O LSTM nao tem kernel nativo no TFLite. O app registra um FlexDelegate
    # exatamente por isso (BodyGestureEngine.ensureLoaded) -- sem estas duas
    # linhas o modelo nem converte, ou converte e o app nao consegue rodar.
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS,
                                      tf.lite.OpsSet.SELECT_TF_OPS]
    conv._experimental_lower_tensor_list_ops = False
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conv.convert())
    return destino


def valida(caminho, n_gestos):
    """Roda o .tflite como o app roda, antes de voce descobrir no celular."""
    import tensorflow as tf

    it = tf.lite.Interpreter(model_path=str(caminho))
    entrada = it.get_input_details()[0]
    it.resize_tensor_input(entrada["index"], [1, JANELA, N_FEATURES])
    it.allocate_tensors()
    entrada = it.get_input_details()[0]
    saida = it.get_output_details()[0]

    if list(entrada["shape"]) != [1, JANELA, N_FEATURES]:
        print("  FALHOU: entrada devia ser [1, %d, %d], veio %s"
              % (JANELA, N_FEATURES, list(entrada["shape"])))
        return False
    if list(saida["shape"]) != [1, n_gestos]:
        print("  FALHOU: saida devia ser [1, %d], veio %s"
              % (n_gestos, list(saida["shape"])))
        return False

    it.set_tensor(entrada["index"], np.zeros((1, JANELA, N_FEATURES), np.float32))
    it.invoke()
    soma = float(it.get_tensor(saida["index"]).sum())
    if not (0.98 <= soma <= 1.02):
        print("  FALHOU: as probabilidades somam %.3f (deviam somar 1)." % soma)
        return False
    print("  validado: entrada %s, saida %s, soma=%.3f"
          % (list(entrada["shape"]), list(saida["shape"]), soma))
    return True


def main():
    ap = argparse.ArgumentParser(description="Retreina o modelo de palavras do app.")
    ap.add_argument("--epocas", type=int, default=80,
                    help="maximo de epocas (para antes se parar de melhorar)")
    ap.add_argument("--sem-ruido", action="store_true", help="desliga o aumento por ruido")
    ap.add_argument("--sem-recortes", action="store_true",
                    help="usa so a gravacao inteira, sem variacao temporal")
    ap.add_argument("--sem-outra-mao", action="store_true",
                    help="(experimento) treina sem as copias com a outra mao a vista")
    ap.add_argument("--so-medir", action="store_true",
                    help="(experimento) mede a nota e para, sem tocar no app")
    args = ap.parse_args()

    print("Lendo gravacoes novas (so as que ainda nao estao no banco):")
    pontos.atualiza("palavras")
    X, y, grupos, variante, gravacoes, uma_mao = monta_dataset(
        [(0.0, 1.0)] if args.sem_recortes else RECORTES)
    print("  banco: " + "  ".join("%s %d" % kv for kv in sorted(gravacoes.items())))
    if uma_mao:
        print("  sinais de uma mao (treinam tambem com a outra mao a vista): %s" % " ".join(uma_mao))
    novas = sorted(set(gravacoes) - set(comum.palavras_do_app()))
    if novas:
        print("  palavra(s) nova(s): %s" % " ".join(novas))
    if not confere_banco(gravacoes):
        return 1

    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf

    tf.keras.utils.set_random_seed(42)
    classes = sorted(set(y))
    y_idx = np.array([classes.index(p) for p in y])

    # 1) Mede: treina com 80% das gravacoes e testa nas outras 20%. Para
    #    sozinho quando a nota no teste para de melhorar -- e esse numero de
    #    epocas que o modelo final usa.
    tr, te = separa_por_gravacao(y_idx, grupos)
    epocas = args.epocas
    if tr is None:
        print("\n  (poucas gravacoes pra separar um teste justo: pulando a medicao)")
    else:
        if args.sem_outra_mao:
            tr = tr[~variante[tr]]
        X_tr, y_tr = (X[tr], y_idx[tr]) if args.sem_ruido else com_ruido(X[tr], y_idx[tr])
        print("\n  medindo: %d gravacoes no treino, %d no teste (ate %d epocas)..."
              % (len(set(grupos[tr])), len(set(grupos[te])), args.epocas), flush=True)
        # Nota "de verdade" so nas gravacoes como foram gravadas; as copias com
        # a outra mao a mais/a menos entram no treino e numa segunda tabela.
        te_real, te_var = te[~variante[te]], te[variante[te]]
        medidor = novo_modelo(len(classes))
        # Pelo erro (val_loss), nao pelo acerto: o acerto no teste so muda de
        # gravacao em gravacao e empata cedo, e o primeiro empate parava o
        # treino antes de o modelo terminar de aprender.
        parada = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=15,
                                                  restore_best_weights=True)
        historico = medidor.fit(X_tr, y_tr, validation_data=(X[te_real], y_idx[te_real]),
                                epochs=args.epocas, batch_size=16, verbose=0,
                                class_weight=pesos(y_tr, len(classes)), callbacks=[parada])
        epocas = max(20, int(np.argmin(historico.history["val_loss"])) + 1)
        previsto = medidor.predict(X[te_real], verbose=0).argmax(axis=1)
        print("\n  Acerto em gravacoes que o treino NAO viu:")
        for i, palavra in enumerate(classes):
            alvo = y_idx[te_real] == i
            confusao = np.bincount(previsto[alvo], minlength=len(classes))
            confusao[i] = 0
            erro = (" (confunde com %s)" % classes[int(confusao.argmax())]) if confusao.any() else ""
            print("     %-14s %5.1f%%  em %d gravacoes%s"
                  % (palavra, 100 * np.mean(previsto[alvo] == i),
                     len(set(grupos[te_real][alvo])), erro))
        print("     %-14s %5.1f%%" % ("TOTAL", 100 * np.mean(previsto == y_idx[te_real])))
        if len(te_var):
            prev_var = medidor.predict(X[te_var], verbose=0).argmax(axis=1)
            print("\n  Os mesmos sinais com a OUTRA mao a vista (uma mao a mais, ou a menos no NEUTRO):")
            for i, palavra in enumerate(classes):
                alvo = y_idx[te_var] == i
                if alvo.any():
                    print("     %-14s %5.1f%%  em %d gravacoes"
                          % (palavra, 100 * np.mean(prev_var[alvo] == i),
                             len(set(grupos[te_var][alvo]))))

    if args.so_medir:
        return 0

    # 2) O modelo que vai pro app aprende com TODAS as gravacoes.
    if args.sem_outra_mao:
        X, y_idx = X[~variante], y_idx[~variante]
    print("\n  treinando o modelo final com todas as gravacoes (%d epocas)..." % epocas, flush=True)
    X_todo, y_todo = (X, y_idx) if args.sem_ruido else com_ruido(X, y_idx)
    modelo = novo_modelo(len(classes))
    modelo.fit(X_todo, y_todo, epochs=epocas, batch_size=16, verbose=0,
               class_weight=pesos(y_todo, len(classes)))

    from backup import faz_backup
    labels_path = ASSETS / "labels.txt"
    guardado = faz_backup([ASSETS / "model.tflite", labels_path], "gestos")
    if guardado:
        print("  copia do que estava no app: %s" % guardado.relative_to(comum.REPO))
    destino = exporta_tflite(modelo, ASSETS / "model.tflite")
    labels_path.write_text("\n".join(classes) + "\n", encoding="utf-8")
    print("  gerado: %s (%.0f KB) -> %s" % (destino.relative_to(comum.REPO),
                                           destino.stat().st_size / 1024, " ".join(classes)))
    if not valida(destino, len(classes)):
        return 1

    print("\nProximo passo: Android Studio -> abrir a pasta 'mobile' -> Run, e testar.")
    print("Ficou pior? Rode 'Desfazer ultimo treino.bat'.")
    print("Ficou bom? Faca commit e push de computer/treino/pontos e do modelo,")
    print("pra outros computadores treinarem a partir daqui.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

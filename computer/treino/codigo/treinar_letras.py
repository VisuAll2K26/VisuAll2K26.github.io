"""
Retreina as LETRAS do app a partir do banco de pontos (computer/treino/pontos).

Sempre o banco inteiro: tudo que ja foi gravado, por qualquer pessoa, em
qualquer computador, mais o que voce acabou de gravar. Rodar duas vezes com o
mesmo banco da o mesmo modelo.

O que acontece, nesta ordem:

  1. As gravacoes novas sao lidas pro banco (pontos.py).

  2. LETRAS COM MOVIMENTO (H J K X Z). O modelo geral delas e refeito com
     todas as gravacoes do banco e mais uma classe, NADA: "a mao se mexeu,
     mas nao fez letra". Sem ela qualquer mao se mexendo virava H, J, K, X ou
     Z. Os exemplos de NADA vem das gravacoes de NADA, das maos dos videos de
     palavras e de trocas sinteticas entre duas letras paradas. Os reforcos
     individuais antigos (letras_dinamicas/H, J, K, X) sao apagados: o app os
     consulta ANTES do geral, e eram eles que respondiam H pra quase tudo.

  3. LETRAS PARADAS. O modelo geral delas conhece 21 letras, e o banco ainda
     nao tem gravacao de todas -- refaze-lo so com as que tem faria o app
     ESQUECER as outras. Por isso cada letra parada que tem gravacao ganha
     (ou atualiza) o seu modelo individual, "isto e um D?", que o app
     consulta antes do geral. O geral so e refeito quando o banco tiver todas
     as letras dele.

Antes de substituir qualquer coisa, uma copia do que estava no app vai pra
computer/treino/modelos_anteriores/ ("Desfazer ultimo treino.bat" devolve).

CONTRATO com o app (LetraEngine.kt e computer/treino/FORMATO_DOS_MODELOS.md):
  1. nome da entrada .... "landmarks_input"
  2. shape da entrada ... [1, 42] (parada) / [1, 420] (movimento), float32
  3. saida .............. zipmap=False: out[0]=rotulo, out[1]=probabilidades
  4. labels.txt ......... um rotulo por linha, na ordem das probabilidades

Uso, dentro de computer/ (o "3 - Retreinar letras.bat" faz isto):
    python treino/codigo/treinar_letras.py
    python treino/codigo/treinar_letras.py --so movimento
    python treino/codigo/treinar_letras.py --so paradas --letras C,D,V
"""
import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import pontos  # noqa: E402

NOME_ENTRADA = "landmarks_input"
NADA = comum.NADA
MAXIMO_PARADA = 500        # amostras por classe, no maximo
MAXIMO_MOVIMENTO = 1500    # cada video rende janelas em 3 taxas de quadros
MINIMO_AMOSTRAS = 10       # menos que isso nao da modelo individual
NADA_PARADO_A_CADA = 3     # 1 quadro a cada 3 das gravacoes de NADA
# O app so aceita um reforco individual acima disto (CONFIANCA_INDIVIDUAL no
# LibrasAnalyzer.kt). Um reforco que nunca passa daqui nao serve pra nada, e um
# que passa fora da propria letra rouba a letra dos outros.
LIMIAR_REFORCO = 0.97
SERVE_MINIMO = 0.50        # fracao das proprias fotos que precisa passar do limiar
FALSO_MAXIMO = 0.01        # fracao do que NAO e a letra que pode passar do limiar
MAXIMO_QUADROS_MOVEIS = 40000
# Janelas coletadas pelo proprio app (coletar.py): sao poucas e valem muito, entao
# cada uma entra varias vezes, com um tremor pequeno diferente em cada copia.
COPIAS_DO_APP = 6
TREMOR_DO_APP = 0.02


# ── o banco, separado do jeito que cada modelo usa ──────────────────────
def copias_do_app(janelas, copias=COPIAS_DO_APP, semente=11):
    """A janela como o app a entregou, mais `copias - 1` com tremor leve."""
    janelas = np.asarray(janelas, dtype=np.float32).reshape(-1, 420)
    rs = np.random.RandomState(semente)
    saida = [janelas]
    for _ in range(copias - 1):
        f = janelas.reshape(-1, 10, 21, 2) + rs.normal(0, TREMOR_DO_APP, (len(janelas), 10, 21, 2))
        f[:, :, 0, :] = 0.0                                    # o pulso continua na origem
        m = np.abs(f).reshape(len(f), 10, -1).max(2)
        m[m == 0] = 1.0
        saida.append((f / m[:, :, None, None]).reshape(len(f), -1).astype(np.float32))
    return list(np.vstack(saida))


class Banco:
    def __init__(self):
        paradas, movimento = set(comum.letras_estaticas()), set(comum.letras_dinamicas())
        self.Xp, self.yp, self.gp = [], [], []          # letras paradas: 42
        self.Xm, self.ym, self.gm = [], [], []          # com movimento: 420
        self.nada_parado = []                           # 42
        self.Xn, self.gn = [], []                       # NADA com movimento: 420
        self.gravacoes = {}                             # rotulo -> quantas
        ignorados = set()

        for rotulo, ident, dados in pontos.carrega("letras"):
            grupo = "%s/%s" % (rotulo, ident)
            if dados["tipo"] == "janelas":
                # Vieram do celular ja prontas (coletar.py), sem passar pelo MediaPipe.
                self.gravacoes[rotulo] = self.gravacoes.get(rotulo, 0) + 1
                copias = copias_do_app(dados["janelas"])
                if rotulo == NADA:
                    self._junta(self.Xn, self.gn, None, copias, grupo)
                elif rotulo in movimento:
                    self._junta(self.Xm, self.gm, self.ym, copias, grupo, rotulo)
                continue
            maos, sequencia = dados["maos"], dados["tipo"] == "sequencia"
            fps = dados.get("fps", pontos.QUADROS_POR_SEGUNDO)
            self.gravacoes[rotulo] = self.gravacoes.get(rotulo, 0) + 1
            if rotulo == NADA:
                self.nada_parado += pontos.amostras_paradas(maos, NADA_PARADO_A_CADA if sequencia else 1)
                if sequencia:
                    self._junta(self.Xn, self.gn, None,
                                pontos.janelas(pontos.trechos(maos), fps), grupo)
            elif rotulo in movimento and sequencia:
                self._junta(self.Xm, self.gm, self.ym, pontos.janelas(pontos.trechos(maos), fps),
                            grupo, rotulo)
            elif rotulo in paradas:
                self._junta(self.Xp, self.gp, self.yp, pontos.amostras_paradas(maos), grupo, rotulo)
            else:
                ignorados.add(rotulo)

        # As maos dos videos de palavras: mao se mexendo de verdade (AJUDAR,
        # PESSOA...) sem fazer H, J, K, X nem Z -- exatamente o que o app
        # confundia com letra.
        for rotulo, ident, dados in pontos.carrega("palavras"):
            fps = dados.get("fps", pontos.QUADROS_POR_SEGUNDO)
            for mao in pontos.maos_do_corpo(dados):
                self._junta(self.Xn, self.gn, None, pontos.janelas(pontos.trechos(mao), fps),
                            "PALAVRA/%s/%s" % (rotulo, ident))

        if ignorados:
            print("  AVISO: pastas que nao sao letra do app foram ignoradas: %s"
                  % " ".join(sorted(ignorados)))

    @staticmethod
    def _junta(X, g, y, amostras, grupo, rotulo=None):
        X += amostras
        g += [grupo] * len(amostras)
        if y is not None:
            y += [rotulo] * len(amostras)

    @staticmethod
    def arrays(X, y, g, largura):
        return (np.array(X, dtype=np.float32).reshape(-1, largura),
                np.array(y, dtype=str), np.array(g, dtype=str))


# ── contas de treino ────────────────────────────────────────────────────
def balanceia(X, y, grupos, maximo):
    """Limita cada classe a `maximo` amostras (sorteio fixo, reproduzivel)."""
    indices = []
    for classe in np.unique(y):
        idx = np.where(y == classe)[0]
        if len(idx) > maximo:
            idx = np.random.RandomState(42).choice(idx, maximo, replace=False)
        indices.extend(idx)
    indices = np.array(sorted(indices), dtype=int)
    return X[indices], y[indices], grupos[indices]


def espelha(X):
    """A mesma amostra feita com a outra mao: nega os x, como
    LibrasMath.mirrorLandmarks. Na janela de 420 as posicoes pares continuam
    sendo os x de cada quadro, entao a conta e a mesma."""
    X = np.array(X, dtype=np.float32, copy=True)
    X[:, 0::2] *= -1
    return X


def com_espelho(X, y, grupos):
    """Acrescenta a copia espelhada, no MESMO grupo da original: senao a nota
    testaria um video cujo espelho estava no treino."""
    return (np.vstack([X, espelha(X)]), np.concatenate([y, y]),
            np.concatenate([grupos, grupos]))


def transicoes_sinteticas(fotos, rotulos, quantidade=2000, semente=42):
    """Janelas de 10 quadros em que a mao TROCA de uma letra parada pra outra.

    E o falso positivo relatado no app: "quando vamos comecar o sinal ou fazer
    outra letra, sai uma letra com movimento". Interpola os 21 pontos de uma
    letra ate os de outra, com a aceleracao/freada de uma mao real,
    renormaliza cada quadro como o app faz e soma um tremor pequeno.
    """
    letras = sorted(set(rotulos))
    if len(letras) < 2:
        return np.zeros((0, 420), dtype=np.float32)
    rs = np.random.RandomState(semente)
    janelas = []
    for _ in range(quantidade):
        a, b = rs.choice(letras, 2, replace=False)
        pa = fotos[rs.choice(np.where(rotulos == a)[0])].reshape(21, 2)
        pb = fotos[rs.choice(np.where(rotulos == b)[0])].reshape(21, 2)
        inicio = rs.uniform(0.0, 0.6)
        fim = min(1.0, inicio + rs.uniform(0.3, 1.0))
        quadros = []
        for s in np.linspace(inicio, fim, 10):
            s = 0.5 - 0.5 * np.cos(np.pi * s)
            p = (1 - s) * pa + s * pb + rs.normal(0, 0.01, pa.shape)
            p = (p - p[0]).reshape(-1)
            quadros.append(p / (np.abs(p).max() or 1.0))
        janelas.append(np.concatenate(quadros))
    return np.array(janelas, dtype=np.float32)


def separa_teste(y_enc, grupos):
    """Treino e teste separados por GRAVACAO: as janelas de um mesmo video
    sao quase iguais, e com elas dos dois lados a nota sai inflada."""
    from sklearn.model_selection import GroupShuffleSplit, train_test_split

    indices = np.arange(len(y_enc))
    if len(set(grupos)) >= 10:
        # Varias tentativas: com poucos videos por letra, um sorteio pode
        # deixar uma letra inteira de fora do teste.
        for semente in range(42, 92):
            tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=semente)
                          .split(indices, y_enc, grupos))
            if set(y_enc[te]) == set(y_enc):
                return tr, te, True
    minimo = int(np.bincount(y_enc).min())
    tr, te = train_test_split(indices, test_size=0.2, random_state=42,
                              stratify=y_enc if minimo >= 5 else None)
    return tr, te, False


def novo_mlp(minimo, camadas=(256, 128)):
    from sklearn.neural_network import MLPClassifier

    return MLPClassifier(hidden_layer_sizes=camadas, activation="relu", max_iter=500,
                         random_state=42, early_stopping=minimo >= 10,
                         validation_fraction=0.1)


def treina_geral(X, y, grupos):
    """Mede em gravacoes que o treino nao viu, depois treina com tudo."""
    import warnings
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.metrics import classification_report
    from sklearn.preprocessing import LabelEncoder

    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    classes = list(le.classes_)
    minimo = int(np.bincount(y_enc).min())
    print("  amostras por classe: " + "  ".join("%s %d" % (c, int((y == c).sum())) for c in classes))

    tr, te, por_grupo = separa_teste(y_enc, grupos)
    medidor = novo_mlp(minimo).fit(X[tr], y_enc[tr])
    print("\n  Nota em %s que o treino NAO viu (recall = quanto de cada letra ele acerta):"
          % ("%d gravacoes" % len(set(grupos[te])) if por_grupo else "amostras sorteadas"))
    print(classification_report(y_enc[te], medidor.predict(X[te]),
                                labels=list(range(len(classes))), target_names=classes,
                                zero_division=0))

    # O modelo que vai pro app aprende com TUDO, inclusive o que foi guardado
    # pra nota.
    print("  treinando o modelo final com todas as gravacoes...")
    return novo_mlp(minimo).fit(X, y_enc), classes


def exporta_onnx(modelo, n_features, destino):
    """Converte pro .onnx no contrato que o LetraEngine espera."""
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    # zipmap=False e o que faz a saida virar [rotulo, probabilidades] em vez
    # de uma lista de dicionarios. O Kotlin le out[1] como Array<FloatArray>.
    onx = convert_sklearn(modelo, initial_types=[(NOME_ENTRADA, FloatTensorType([None, n_features]))],
                          target_opset=12, options={id(modelo): {"zipmap": False}})
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(onx.SerializeToString())
    return destino


def valida(caminho_onnx, n_features, n_classes):
    """Roda o .onnx recem-gerado do jeito que o app roda. Falha aqui e melhor
    que descobrir com o app instalado e sem reconhecer nada."""
    try:
        import onnxruntime as ort
    except ImportError:
        print("  AVISO: onnxruntime nao instalado -- pulando a validacao.")
        return False

    sessao = ort.InferenceSession(str(caminho_onnx), providers=["CPUExecutionProvider"])
    entradas = sessao.get_inputs()
    if len(entradas) != 1 or entradas[0].name != NOME_ENTRADA:
        print("  FALHOU: entrada devia se chamar '%s', veio %s"
              % (NOME_ENTRADA, [e.name for e in entradas]))
        return False
    forma = entradas[0].shape
    if len(forma) != 2 or forma[1] != n_features:
        print("  FALHOU: shape da entrada devia ser [1, %d], veio %s" % (n_features, forma))
        return False
    if len(sessao.get_outputs()) < 2:
        print("  FALHOU: o app le a saida [1] (probabilidades), e o modelo so tem uma.")
        return False
    probs = np.asarray(sessao.run(None, {NOME_ENTRADA: np.zeros((1, n_features), np.float32)})[1])
    if probs.shape != (1, n_classes):
        print("  FALHOU: probabilidades deviam ter shape (1, %d), veio %s"
              % (n_classes, probs.shape))
        return False
    soma = float(probs.sum())
    if not (0.98 <= soma <= 1.02):
        print("  FALHOU: as probabilidades somam %.3f (deviam somar 1)." % soma)
        return False
    print("  validado: entrada '%s' %s, saida[1] %s, soma=%.3f"
          % (NOME_ENTRADA, forma, probs.shape, soma))
    return True


def guarda_copia(pasta_assets):
    """Copia do modelo geral e dos individuais antes de substituir/apagar."""
    from backup import faz_backup

    arquivos = sorted(p for p in pasta_assets.rglob("*") if p.is_file())
    pasta = faz_backup(arquivos, pasta_assets.name)
    if pasta is not None:
        print("  copia do que estava no app: %s" % pasta.relative_to(comum.REPO))


def instala_geral(modelo, classes, n_features, pasta_assets):
    destino = exporta_onnx(modelo, n_features, pasta_assets / "geral" / "model.onnx")
    (pasta_assets / "geral" / "labels.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")
    print("  gerado: %s -> %s" % (destino.relative_to(comum.REPO), " ".join(classes)))
    return valida(destino, n_features, len(classes))


def faltam_no_banco(pasta_assets, presentes):
    """Rotulos que o modelo geral do app conhece e o banco nao tem. Treinar
    sem eles faria o app esquece-los -- sem erro nenhum, so parando de
    reconhecer."""
    atuais = comum.le_labels(pasta_assets / "geral" / "labels.txt")
    return sorted(set(atuais) - set(presentes) - {NADA})


# ── os dois tipos de letra ──────────────────────────────────────────────
def treina_movimento(banco, com_nada=True, espelho=True):
    print("\n" + "=" * 64)
    print("  LETRAS COM MOVIMENTO (%s)" % " ".join(comum.letras_dinamicas()))
    print("=" * 64)
    X, y, g = Banco.arrays(banco.Xm, banco.ym, banco.gm, 420)
    if not len(X):
        print("  sem gravacoes de letra com movimento no banco -- nada a fazer.")
        return None
    faltam = faltam_no_banco(comum.ASSETS_DINAMICAS, set(y))
    if faltam:
        print("  PAREI: o banco nao tem gravacao de %s." % " ".join(faltam))
        print("  Treinar assim faria o app esquecer essas letras. Grave-as no")
        print("  '3 - Retreinar letras.bat' e rode de novo.")
        return False

    X, y, g = balanceia(X, y, g, MAXIMO_MOVIMENTO)
    if com_nada:
        Xp, yp, _ = Banco.arrays(banco.Xp, banco.yp, banco.gp, 42)
        trocas = transicoes_sinteticas(Xp, yp)
        Xn = np.vstack([np.array(banco.Xn, dtype=np.float32).reshape(-1, 420), trocas])
        gn = np.concatenate([np.array(banco.gn, dtype=str),
                             np.array(["TROCA/%d" % (i // 50) for i in range(len(trocas))], dtype=str)])
        teto = max(int((y == c).sum()) for c in set(y))
        if len(Xn) > teto:
            escolha = np.sort(np.random.RandomState(42).choice(len(Xn), teto, replace=False))
            Xn, gn = Xn[escolha], gn[escolha]
        if len(Xn):
            print("  NADA: %d exemplos de mao que nao esta fazendo letra" % len(Xn))
            X, y = np.vstack([X, Xn]), np.concatenate([y, np.full(len(Xn), NADA)])
            g = np.concatenate([g, gn])
    if espelho:
        X, y, g = com_espelho(X, y, g)

    modelo, classes = treina_geral(X, y, g)
    guarda_copia(comum.ASSETS_DINAMICAS)
    ok = instala_geral(modelo, classes, 420, comum.ASSETS_DINAMICAS)

    # O app consulta os reforcos individuais ANTES do geral: deixa-los seria
    # continuar usando os modelos velhos pras letras que eles cobrem.
    removidos = []
    for item in sorted(comum.ASSETS_DINAMICAS.iterdir()):
        if item.is_dir() and item.name != "geral":
            shutil.rmtree(item)
            removidos.append(item.name)
        elif item.name in ("individual_labels.txt", "reforcos_restritos.txt"):
            item.unlink()
    if removidos:
        print("  reforcos individuais antigos removidos: %s" % " ".join(removidos))
    return ok


def treina_paradas(banco, so_estas=None, espelho=True):
    print("\n" + "=" * 64)
    print("  LETRAS PARADAS")
    print("=" * 64)
    X, y, g = Banco.arrays(banco.Xp, banco.yp, banco.gp, 42)
    if not len(X):
        print("  sem gravacoes de letra parada no banco -- nada a fazer.")
        return None
    X, y, g = balanceia(X, y, g, MAXIMO_PARADA)
    guarda_copia(comum.ASSETS_ESTATICAS)
    resultado, feitos = True, 0

    faltam = faltam_no_banco(comum.ASSETS_ESTATICAS, set(y))
    if faltam:
        print("  O modelo geral fica como esta: o banco ainda nao tem %s." % " ".join(faltam))
        print("  (Ele so e refeito quando todas as %d letras dele tiverem gravacao.)"
              % len(comum.letras_estaticas()))
    elif so_estas is None:
        print("  O banco tem todas as letras paradas: refazendo o modelo geral.")
        Xe, ye, ge = com_espelho(X, y, g) if espelho else (X, y, g)
        modelo, classes = treina_geral(Xe, ye, ge)
        resultado = instala_geral(modelo, classes, 42, comum.ASSETS_ESTATICAS) and resultado
        feitos += 1

    # Modelos individuais: "isto e um D?". Os exemplos de "nao" sao as outras
    # letras gravadas MAIS o NADA. So com outras letras, o modelo aprende a
    # separar D de L e passa a dizer "sim" pra qualquer mao solta no ar.
    nada = np.array(banco.nada_parado, dtype=np.float32).reshape(-1, 42)
    # Quadros soltos das letras com movimento, do NADA e das maos dos videos de
    # palavras: o inicio de um H, de um Z ou de um sinal tem a forma de uma
    # letra parada. Sem eles como "nao", o reforco aprendia a separar so as
    # letras paradas entre si e disparava em tudo isso (o F de prioridade
    # roubava 1 em cada 4 quadros de X e de K).
    moveis = np.array(banco.Xm + banco.Xn, dtype=np.float32).reshape(-1, 42)
    if len(moveis) > MAXIMO_QUADROS_MOVEIS:
        moveis = moveis[np.sort(np.random.RandomState(42).choice(
            len(moveis), MAXIMO_QUADROS_MOVEIS, replace=False))]
    if espelho:
        X, y, g = com_espelho(X, y, g)
        nada = np.vstack([nada, espelha(nada)])
        moveis = np.vstack([moveis, espelha(moveis)])
    congelados = set(comum.le_labels(comum.TREINO / "reforcos_congelados.txt"))
    ja_instaladas = {p.name for p in comum.ASSETS_ESTATICAS.iterdir()
                     if p.is_dir() and p.name != "geral" and (p / "model.onnx").exists()}
    novas = []
    alvos = sorted(set(y) if so_estas is None else set(so_estas) & set(y))
    if so_estas:
        for letra in sorted(set(so_estas) - set(y)):
            print("  %s: sem gravacao no banco -- pulada" % letra)
    if not len(nada):
        print("  (sem gravacoes de NADA: os reforcos ficam mais propensos a falso")
        print("   positivo. Grave alguns NADA no '3 - Retreinar letras.bat'.)")
    print("\n  reforcos individuais (\"isto e esta letra?\"):")
    from sklearn.neural_network import MLPClassifier

    for letra in alvos:
        positivos, outras = X[y == letra], X[y != letra]
        gravacoes = banco.gravacoes.get(letra, 0)
        if letra in congelados:
            # Funciona no celular do jeito que esta: o retreino ja derrubou o U
            # uma vez (aprendeu a separar do H e deixou de aceitar o U do app).
            print("  %-4s %2d gravacoes | CONGELADO: fica o modelo que esta no app"
                  " (para refazer, tire a letra de treino\\reforcos_congelados.txt)"
                  % (letra, gravacoes))
            continue
        if len(positivos) < MINIMO_AMOSTRAS:
            print("  %-4s pulada: so %d fotos (minimo %d)." % (letra, len(positivos), MINIMO_AMOSTRAS))
            continue
        # Os dois lados do mesmo tamanho: com 20 "sim" e 2000 "nao" o modelo
        # aprende a responder sempre "nao". Outras letras e NADA sorteados
        # separados, pra nenhum dos dois sumir.
        rs = np.random.RandomState(42)
        fontes = [p for p in (outras, nada, moveis) if len(p)]
        if not fontes:
            print("  %-4s pulada: nao ha nenhum exemplo de 'nao' (grave outra letra ou NADA)." % letra)
            continue
        cota = max(len(positivos) * 3, 120) // len(fontes)
        negativos = np.vstack([p[np.sort(rs.choice(len(p), cota, replace=False))] if len(p) > cota
                               else p for p in fontes])
        X_bin = np.vstack([positivos, negativos])
        y_bin = np.concatenate([np.ones(len(positivos), int), np.zeros(len(negativos), int)])
        # SEM parada antecipada: ela parava quando o acerto de teste batia nos
        # 100%, com o modelo ainda "em duvida" (confianca ~0.6), e o app so
        # aceita reforco acima de 0.97 -- o reforco instalava e nunca disparava.
        modelo = MLPClassifier(hidden_layer_sizes=(128, 64), activation="relu", max_iter=500,
                               random_state=42).fit(X_bin, y_bin)
        aviso = "  <- poucas gravacoes, grave mais" if gravacoes < 5 else ""

        # Mede do jeito que o app decide: acima do limiar, nas proprias fotos
        # e em TUDO que nao e a letra (nao so nos exemplos sorteados acima).
        serve = float(np.mean(modelo.predict_proba(positivos)[:, 1] >= LIMIAR_REFORCO))
        fora = np.vstack([p for p in (outras, nada, moveis) if len(p)])
        falso = float(np.mean(modelo.predict_proba(fora)[:, 1] >= LIMIAR_REFORCO))
        motivo = None
        if serve < SERVE_MINIMO:
            motivo = "so passa do limiar em %.0f%% das proprias fotos (minimo %.0f%%)" % (
                100 * serve, 100 * SERVE_MINIMO)
        elif falso > FALSO_MAXIMO:
            motivo = "dispara em %.1f%% do que NAO e %s (maximo %.0f%%): roubaria outras letras" % (
                100 * falso, letra, 100 * FALSO_MAXIMO)
        if motivo:
            existe = letra in ja_instaladas
            print("  %-4s %2d gravacoes | NAO instalado: %s%s%s" % (
                letra, gravacoes, motivo, "; fica o modelo que ja estava" if existe else "", aviso))
            continue
        destino = exporta_onnx(modelo, 42, comum.ASSETS_ESTATICAS / letra / "model.onnx")
        ok = valida(destino, 42, 2)
        resultado, feitos = resultado and ok, feitos + 1
        if letra not in ja_instaladas:
            novas.append(letra)
        print("  %-4s %2d gravacoes | %d sim / %d nao | dispara em %.0f%% das proprias e %.1f%% das outras | %s%s"
              % (letra, gravacoes, len(positivos), len(negativos), 100 * serve, 100 * falso,
                 "ok" if ok else "NAO VALIDOU", aviso))
    if novas:
        restringe_novas(novas)
    return resultado if feitos else None


def restringe_novas(letras):
    """Reforco de letra que o app ainda nao tinha entra RESTRITO: so decide
    entre letras do mesmo grupo e nunca passa por cima do modelo geral. Quem
    quiser dar prioridade depois, depois de testar no celular, apaga a letra
    de reforcos_restritos.txt."""
    arquivo = comum.ASSETS_ESTATICAS / "reforcos_restritos.txt"
    atuais = comum.le_labels(arquivo) if arquivo.exists() else []
    todas = sorted(set(atuais) | set(letras))
    arquivo.write_text("\n".join(todas) + "\n", encoding="utf-8")
    print("\n  Reforco novo (%s) entrou como RESTRITO em reforcos_restritos.txt:" % " ".join(letras))
    print("  ele so ajuda a decidir dentro do grupo %s e nao passa por cima do modelo geral." % " ".join(todas))
    print("  Funcionou bem no celular e voce quer prioridade? Tire a letra desse arquivo.")


def main():
    ap = argparse.ArgumentParser(description="Retreina as letras do app com o banco de pontos.")
    ap.add_argument("--so", choices=["movimento", "paradas"],
                    help="treina so um dos dois tipos de letra")
    ap.add_argument("--letras", metavar="C,D,V",
                    help="letras paradas: refaz o reforco so destas")
    ap.add_argument("--sem-espelho", action="store_true", help="(experimento) sem a outra mao")
    ap.add_argument("--sem-nada", action="store_true", help="(experimento) sem a classe NADA")
    args = ap.parse_args()

    if not comum.ASSETS.exists():
        print("ERRO: nao achei a pasta de modelos do app em %s" % comum.ASSETS)
        return 1
    so_estas = None
    if args.letras:
        so_estas = [comum.nome_de_palavra(l) for l in args.letras.replace(";", ",").split(",")]
        so_estas = [l for l in so_estas if l]

    print("Lendo gravacoes novas (so as que ainda nao estao no banco):")
    pontos.atualiza("letras")
    pontos.atualiza("palavras")    # as maos delas sao exemplos de NADA
    banco = Banco()
    print("  banco: " + "  ".join("%s %d" % kv for kv in sorted(banco.gravacoes.items())))

    resultados = {}
    if args.so != "paradas":
        resultados["com movimento"] = treina_movimento(banco, not args.sem_nada, not args.sem_espelho)
    if args.so != "movimento":
        resultados["paradas"] = treina_paradas(banco, so_estas, not args.sem_espelho)

    print("\n" + "=" * 64)
    for nome, r in resultados.items():
        print("  letras %-14s %s" % (nome, {None: "sem gravacoes, nada mudou",
                                           False: "NAO atualizado (veja acima)",
                                           True: "atualizado no app"}[r]))
    print("=" * 64)
    if not any(r is True for r in resultados.values()):
        return 1
    print("\nProximo passo: Android Studio -> abrir a pasta 'mobile' -> Run, e testar.")
    print("Ficou pior? Rode 'Desfazer ultimo treino.bat'.")
    print("Ficou bom? Faca commit e push de computer/treino/pontos e dos modelos,")
    print("pra outros computadores treinarem a partir daqui.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

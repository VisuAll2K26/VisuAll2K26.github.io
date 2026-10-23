"""
Treina e exporta os modelos NO FORMATO QUE O APP ANDROID LE (.onnx).

Este e o passo que fecha o ciclo: videos/fotos no PC -> .onnx -> app do
celular. Nao passa por .pkl e nao tem nada a ver com o backend Python.

Entrada (gerada pelos extractors deste repo):
    data/dataset_static.npz    X [N, 42]   y [N]  grupo [N]
    data/dataset_dynamic.npz   X [N, 420]  y [N]  grupo [N]
    data/dataset_negativos_*.npz  (opcional) exemplos de "nao e letra"

`grupo` diz de que video/gravacao saiu cada amostra. Com ele a nota impressa
no fim e honesta: o teste so tem videos que o treino nunca viu. Sem ele (npz
antigo), a nota mistura janelas quase iguais do mesmo video nos dois lados.

Saida (direto na pasta de assets do app):
    mobile/app/src/main/assets/letras_estaticas/geral/model.onnx
    mobile/app/src/main/assets/letras_estaticas/geral/labels.txt
    mobile/app/src/main/assets/letras_dinamicas/geral/model.onnx
    mobile/app/src/main/assets/letras_dinamicas/geral/labels.txt

CONTRATO com o app -- estes 4 pontos nao podem mudar (LetraEngine.kt:234-242
e mobile/TREINAMENTO_MODELOS.md):

  1. nome da entrada .... "landmarks_input"
  2. shape da entrada ... [1, 42] (estatico) / [1, 420] (dinamico), float32
  3. saida .............. zipmap=False, entao out[0]=label e
                          out[1]=probabilidades. O Kotlin le out[1].
  4. labels.txt ......... uma letra por linha, NA MESMA ORDEM das colunas de
                          probabilidade. E o que traduz "saida numero 3" na
                          letra certa.

A normalizacao dos landmarks ja bate: normalize_landmarks() do Python e
LibrasMath.normalizeLandmarks() do Kotlin fazem a mesma conta (translada pelo
ponto 0, divide pelo maior valor absoluto).

Duas coisas entram no treino sem voce gravar nada a mais:
  - ESPELHO: cada amostra entra tambem espelhada (a mesma letra com a outra
    mao). Os videos sao de uma mao so, e o app espelha a camera frontal.
  - NADA (so nas letras com movimento): uma classe a mais, feita dos clipes
    de "nada", das maos dos videos de gesto de corpo e de trocas sinteticas
    entre letras paradas. Sem ela o modelo nao tinha como responder "nao e
    letra" e qualquer mao se mexendo virava H, J, K, X ou Z. O app nunca
    mostra esse rotulo (LetterDecision.normalizarSaida).

Uso:
    python treino/exportar_onnx.py                  # os dois modelos
    python treino/exportar_onnx.py --tipo estatico  # so um
    python treino/exportar_onnx.py --limpar-individuais
    python treino/exportar_onnx.py --sem-espelho --sem-nada   # como era antes
"""
import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parents[1]
REPO = RAIZ.parent
DATA = RAIZ / "data"
ASSETS = REPO / "mobile" / "app" / "src" / "main" / "assets"

NOME_ENTRADA = "landmarks_input"
# Rotulo da classe "isto nao e letra" do modelo dinamico. O app trata como
# "nao sei" (LetterDecision.normalizarSaida) e nunca mostra na tela.
NADA = "NADA"

# Serve pra saber a que categoria pertence cada letra pedida em --reforcar.
LETRAS_DO_TIPO = {
    "estatico": list("ABCDEFGILMNOPQRSTUVWY"),
    "dinamico": ["H", "J", "K", "X", "Z"],
}

# (dataset, features, pasta de assets, maximo de amostras por classe)
# O dinamico era 400. Cada video agora rende janelas em tres taxas de quadros
# (extract_from_videos.py: PASSOS), e com 400 a maior parte delas era sorteada
# fora antes de o treino comecar.
CONFIG = {
    "estatico": (DATA / "dataset_static.npz", 42, ASSETS / "letras_estaticas", 500),
    "dinamico": (DATA / "dataset_dynamic.npz", 420, ASSETS / "letras_dinamicas", 1500),
}


def exige(modulo, pacote=None):
    try:
        return __import__(modulo)
    except ImportError:
        print("ERRO: falta o pacote '%s'." % (pacote or modulo))
        print("Instale com:  python -m pip install %s" % (pacote or modulo))
        raise SystemExit(1)


def balanceia(X, y, maximo, grupos=None):
    """Limita cada classe a `maximo` amostras -- mesma logica dos scripts de treino."""
    indices = []
    for classe in np.unique(y):
        idx = np.where(y == classe)[0]
        if len(idx) > maximo:
            idx = np.random.RandomState(42).choice(idx, maximo, replace=False)
        indices.extend(idx)
    indices = np.array(indices)
    return X[indices], y[indices], (grupos[indices] if grupos is not None else None)


def espelha(X):
    """A mesma amostra feita com a outra mao: nega os x, como
    LibrasMath.mirrorLandmarks. Na janela de 420 as posicoes pares continuam
    sendo os x de cada quadro, entao a conta e a mesma."""
    X = np.array(X, dtype=np.float32, copy=True)
    X[:, 0::2] *= -1
    return X


def com_espelho(X, y, grupos):
    """Acrescenta a copia espelhada. A copia fica no MESMO grupo da original:
    senao a avaliacao testaria um video cujo espelho estava no treino."""
    X2 = np.vstack([X, espelha(X)])
    y2 = np.concatenate([y, y])
    g2 = np.concatenate([grupos, grupos]) if grupos is not None else None
    return X2, y2, g2


def separa_teste(y_enc, grupos):
    """Indices de treino e teste. Por grupo (video/gravacao) quando da: as
    janelas de um mesmo video sao quase iguais, e com elas dos dois lados a
    nota sai inflada -- o modelo e testado no que ja viu."""
    from sklearn.model_selection import GroupShuffleSplit, train_test_split

    indices = np.arange(len(y_enc))
    if grupos is not None and len(set(grupos)) >= 10:
        # Varias tentativas: com poucos videos por letra, um sorteio pode
        # deixar uma letra inteira de fora do teste.
        for semente in range(42, 92):
            tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2,
                                            random_state=semente).split(indices, y_enc, grupos))
            if set(y_enc[te]) == set(y_enc):
                return tr, te, True
    minimo = int(np.bincount(y_enc).min())
    tr, te = train_test_split(indices, test_size=0.2, random_state=42,
                              stratify=y_enc if minimo >= 5 else None)
    return tr, te, False


def novo_mlp(minimo):
    from sklearn.neural_network import MLPClassifier

    return MLPClassifier(
        hidden_layer_sizes=(256, 128),
        activation="relu",
        max_iter=500,
        random_state=42,
        early_stopping=minimo >= 10,   # precisa de amostra pra separar validacao
        validation_fraction=0.1,
    )


def treina(X, y, grupos=None):
    from sklearn.preprocessing import LabelEncoder
    from sklearn.metrics import classification_report

    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    classes = list(le.classes_)

    print("  classes: %s" % classes)
    print("  amostras: %d  |  features: %d" % (len(X), X.shape[1]))
    for c in classes:
        print("     %-4s %d" % (c, int((y == c).sum())))

    if len(classes) < 2:
        print("\n  ERRO: so ha 1 classe com dados. O modelo geral precisa de pelo")
        print("  menos 2 letras pra ter o que distinguir. Grave outra letra.")
        raise SystemExit(1)

    minimo = min(int((y_enc == i).sum()) for i in range(len(classes)))
    tr, te, por_grupo = separa_teste(y_enc, grupos)

    print("\n  treinando MLP (256, 128) pra medir...")
    modelo = novo_mlp(minimo)
    modelo.fit(X[tr], y_enc[tr])
    y_pred = modelo.predict(X[te])
    if por_grupo:
        print("\n  Nota em %d videos/gravacoes que o treino NAO viu:"
              % len(set(grupos[te])))
    else:
        print("\n  Nota em amostras sorteadas (sem informacao de video: pode sair")
        print("  otimista -- rode o Treinar.bat de novo pra refazer os .npz):")
    print("\n" + classification_report(
        y_enc[te], y_pred,
        labels=list(range(len(classes))),
        target_names=classes,
        zero_division=0,
    ))

    # O modelo que vai pro app aprende com TUDO. Antes ele ficava so com os
    # 80% do treino, e os 20% guardados pra nota nunca chegavam ao celular.
    print("  treinando o modelo final com todas as amostras...")
    modelo = novo_mlp(minimo)
    modelo.fit(X, y_enc)
    return modelo, classes


def exporta_onnx(modelo, n_features, destino):
    """Converte pro .onnx no contrato que o LetraEngine espera."""
    exige("skl2onnx")
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    tipos = [(NOME_ENTRADA, FloatTensorType([None, n_features]))]
    # zipmap=False e o que faz a saida virar [label, probabilidades] em vez de
    # uma lista de dicionarios. O Kotlin le out[1] como Array<FloatArray>;
    # com zipmap ligado, aquele indice vem como mapa e o app quebra.
    onx = convert_sklearn(
        modelo, initial_types=tipos, target_opset=12,
        options={id(modelo): {"zipmap": False}},
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(onx.SerializeToString())
    return destino


def salva_labels(classes, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(classes) + "\n", encoding="utf-8")
    return destino


def valida(caminho_onnx, n_features, n_classes):
    """Roda o .onnx recem-gerado do jeito que o app roda. Falha aqui e melhor
    que descobrir com o app instalado e sem reconhecer nada."""
    try:
        import onnxruntime as ort
    except ImportError:
        print("  AVISO: onnxruntime nao instalado -- pulando a validacao.")
        print("         Instale com: python -m pip install onnxruntime")
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

    saidas = sessao.get_outputs()
    if len(saidas) < 2:
        print("  FALHOU: o app le a saida de indice [1] (probabilidades), mas o")
        print("          modelo tem so %d saida(s). Faltou zipmap=False?" % len(saidas))
        return False

    amostra = np.zeros((1, n_features), dtype=np.float32)
    resultado = sessao.run(None, {NOME_ENTRADA: amostra})
    probs = np.asarray(resultado[1])

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


def limpa_individuais(pasta_assets, classes):
    """Remove os modelos por letra. O LetraEngine tenta os individuais ANTES do
    geral (LetraEngine.kt:209-219), entao um individual velho continua mandando
    mesmo depois de voce treinar o geral."""
    removidos = []
    for sub in sorted(pasta_assets.iterdir()):
        if sub.is_dir() and sub.name != "geral":
            shutil.rmtree(sub)
            removidos.append(sub.name)
    return removidos


def carrega_negativos(tipo, n_features, com_grupos=False):
    """Amostras de 'Nada' (mao a mostra sem sinalizar), se houver. No
    dinamico, inclui as maos dos videos de gesto de corpo (extrair_negativos.py)
    e as trocas sinteticas entre letras paradas (transicoes_sinteticas)."""
    caminho = DATA / ("dataset_negativos_static.npz" if tipo == "estatico"
                      else "dataset_negativos_dynamic.npz")
    partes, grupos = [], []
    if caminho.exists():
        dados = np.load(caminho, allow_pickle=True)
        X = dados["X"].astype(np.float32)
        if X.ndim == 2 and X.shape[1] == n_features and len(X):
            partes.append(X)
            grupos.append(dados["grupo"] if "grupo" in dados.files
                          else np.array(["NADA/%d" % (i // 30) for i in range(len(X))]))
    if tipo == "dinamico":
        X = transicoes_sinteticas()
        if X is not None:
            partes.append(X)
            grupos.append(np.array(["TROCA/%d" % (i // 50) for i in range(len(X))]))
    if not partes:
        return (None, None) if com_grupos else None
    X, g = np.vstack(partes), np.concatenate(grupos)
    return (X, g) if com_grupos else X


def transicoes_sinteticas(quantidade=2000, semente=42):
    """Janelas de 10 quadros em que a mao TROCA de uma letra parada pra outra.

    E o falso positivo relatado no app: "quando vamos comecar o sinal ou fazer
    outra letra, sai uma letra com movimento". Na troca a mao se mexe de
    verdade (passa do limiar de movimento), e um modelo que nunca viu troca
    nenhuma chamava aquilo de H, J, K, X ou Z.

    Sai das fotos (dataset_static.npz): interpola os 21 pontos de uma letra ate
    os de outra, com a aceleracao/freada de uma mao real, renormaliza cada
    quadro como o app faz e soma um tremor pequeno. Pega so um trecho da troca
    por janela, como o app pega.
    """
    caminho = DATA / "dataset_static.npz"
    if not caminho.exists():
        return None
    dados = np.load(caminho, allow_pickle=True)
    fotos, rotulos = dados["X"].astype(np.float32), dados["y"].astype(str)
    letras = sorted(set(rotulos))
    if len(letras) < 2:
        return None

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


def treina_individuais(tipo, X, y, n_features, pasta_assets, alvos, espelho=True):
    """Treina um modelo SIM/NAO por letra e salva em <LETRA>/model.onnx.

    O app testa estes ANTES do modelo geral (LetraEngine.kt:209-219), entao
    reforcar uma letra aqui NAO mexe em nenhuma outra -- e por isso este e o
    caminho pra aprimorar letras sem regravar o alfabeto inteiro.

    Cada modelo responde "isto e a letra L?". Os exemplos de "nao" sao as
    outras letras gravadas MAIS os clipes de 'Nada'. Sem os de 'Nada', o
    modelo so aprende a separar L de outras letras e passa a dizer "sim" pra
    qualquer mao solta no ar.

    ATENCAO: "as outras letras gravadas" sao so as que estao em
    computer/data. Uma letra que nunca foi gravada aqui nunca entra como
    "nao" -- o D treinado sem nenhuma foto de L nao aprende que L nao e D.
    """
    from sklearn.neural_network import MLPClassifier

    negativos_nada = carrega_negativos(tipo, n_features)
    if espelho:
        X, y, _ = com_espelho(X, y, None)
        if negativos_nada is not None:
            negativos_nada = np.vstack([negativos_nada, espelha(negativos_nada)])
    disponiveis = sorted(set(y))
    print("\n  --- modelos individuais (%s) ---" % tipo)
    if negativos_nada is None:
        print("  AVISO: sem clipes de 'Nada'. Os modelos individuais vao ficar")
        print("  propensos a falso positivo. Grave alguns no modo 'nada' do")
        print("  Gravar.bat e rode de novo -- e a melhoria mais barata que tem.")
    else:
        print("  usando %d amostras de 'Nada' como exemplo negativo"
              % len(negativos_nada))

    feitos = []
    for letra in alvos:
        if letra not in disponiveis:
            print("  %-3s pulado: voce nao gravou amostras dessa letra." % letra)
            continue

        positivos = X[y == letra]
        outras = X[y != letra]
        if not len(outras) and (negativos_nada is None or not len(negativos_nada)):
            print("  %-3s pulado: nao ha nenhum exemplo de 'nao' pra comparar." % letra)
            continue

        if len(positivos) < 10:
            print("  %-3s pulado: so %d amostras (minimo 10)." % (letra, len(positivos)))
            continue

        # Equilibra os dois lados: um modelo treinado com 20 "sim" e 2000 "nao"
        # aprende a responder sempre "nao". E sorteia as outras letras e o
        # 'Nada' separados: com milhares de janelas de 'Nada', um sorteio unico
        # quase nao deixava letra nenhuma entre os "nao".
        rs = np.random.RandomState(42)
        limite = max(len(positivos) * 3, 60)
        fontes = [p for p in (outras, negativos_nada) if p is not None and len(p)]
        cota = limite // len(fontes)
        negativos = np.vstack([
            p[rs.choice(len(p), cota, replace=False)] if len(p) > cota else p
            for p in fontes
        ])

        X_bin = np.vstack([positivos, negativos]).astype(np.float32)
        y_bin = np.concatenate([np.ones(len(positivos), dtype=int),
                                np.zeros(len(negativos), dtype=int)])

        modelo = MLPClassifier(
            hidden_layer_sizes=(128, 64), activation="relu", max_iter=500,
            random_state=42, early_stopping=len(X_bin) >= 50, validation_fraction=0.15,
        )
        modelo.fit(X_bin, y_bin)
        acerto = modelo.score(X_bin, y_bin)

        destino = pasta_assets / letra / "model.onnx"
        exporta_onnx(modelo, n_features, destino)
        ok = valida(destino, n_features, 2)
        print("  %-3s %d sim / %d nao  |  acerto %.0f%%  |  %s"
              % (letra, len(positivos), len(negativos), acerto * 100,
                 "ok" if ok else "NAO VALIDOU"))
        feitos.append(letra)

    return feitos


def checa_regressao(classes, pasta_assets, forcar):
    """O modelo geral so conhece as letras com que foi treinado. Treinar com um
    punhado de letras SUBSTITUI o modelo do app por um que esqueceu todas as
    outras -- e o labels.txt vai junto, entao nem da erro: o app simplesmente
    para de reconhecer o que reconhecia. Aqui a gente barra isso."""
    labels_path = pasta_assets / "geral" / "labels.txt"
    if not labels_path.exists():
        return True

    atuais = [l.strip() for l in labels_path.read_text(encoding="utf-8").splitlines()
              if l.strip()]
    # NADA nao e letra: treinar com --sem-nada depois de um modelo que tinha a
    # classe nao faz o app esquecer nada.
    faltando = sorted(set(atuais) - set(classes) - {NADA})
    if not faltando:
        return True

    print("\n  " + "!" * 58)
    print("  PAREI: isto faria o app ESQUECER letras que ele ja sabe.")
    print("  " + "!" * 58)
    print("  o app conhece hoje (%d): %s" % (len(atuais), " ".join(atuais)))
    print("  voce gravou so     (%d): %s" % (len(classes), " ".join(classes)))
    print("  seriam PERDIDAS    (%d): %s" % (len(faltando), " ".join(faltando)))
    print()
    print("  O modelo geral so sabe as letras com que foi treinado. Se ele for")
    print("  substituido por um treinado so com %s, o app para de" % " ".join(classes))
    print("  reconhecer as outras %d -- sem dar erro nenhum." % len(faltando))
    print()
    print("  O que fazer:")
    print("    -> grave tambem as letras que faltam e rode de novo (recomendado)")
    print("    -> ou, se voce REALMENTE quer um app que so conhece essas,")
    print("       rode com --forcar")

    if forcar:
        print("\n  --forcar usado: seguindo mesmo assim.")
        return True
    return False


def guarda_copia(pasta_assets):
    """Copia do modelo geral e dos individuais antes de substituir/apagar --
    e o que o RestaurarModelo.bat devolve."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from backup import faz_backup

    arquivos = sorted(p for p in pasta_assets.rglob("*") if p.is_file())
    pasta = faz_backup(arquivos, pasta_assets.name)
    if pasta is not None:
        print("  copia do modelo anterior: %s" % pasta.relative_to(REPO))


def processa(tipo, limpar, forcar=False, reforcar=None, espelho=True, com_nada=True):
    dataset, n_features, pasta_assets, maximo = CONFIG[tipo]

    print("\n" + "=" * 62)
    print("  %s  (%d features)" % (tipo.upper(), n_features))
    print("=" * 62)

    if not dataset.exists():
        print("  pulando: %s nao existe." % dataset.relative_to(RAIZ))
        print("  rode os extractors antes (treino\\Treinar.bat faz isso).")
        return None

    dados = np.load(dataset, allow_pickle=True)
    X = dados["X"].astype(np.float32)
    y = dados["y"].astype(str)
    grupos = dados["grupo"].astype(str) if "grupo" in dados.files else None

    if X.ndim != 2 or X.shape[1] != n_features:
        print("  ERRO: o dataset tem shape %s, mas o app espera [N, %d]."
              % (X.shape, n_features))
        return None

    X, y, grupos = balanceia(X, y, maximo, grupos)

    # Modo reforco: mexe SO nos modelos individuais das letras pedidas.
    # O modelo geral (e o labels.txt) fica exatamente como estava, entao
    # nenhuma outra letra e afetada.
    if reforcar is not None:
        alvos = [l for l in reforcar if l in set(LETRAS_DO_TIPO[tipo])]
        if not alvos:
            print("  nenhuma das letras pedidas e desta categoria -- pulando.")
            return None
        guarda_copia(pasta_assets)
        feitos = treina_individuais(tipo, X, y, n_features, pasta_assets, alvos, espelho)
        if not feitos:
            print("\n  Nenhum modelo individual foi gerado.")
            return False
        print("\n  reforcadas: %s" % " ".join(feitos))
        print("  o modelo geral NAO foi tocado -- as outras letras continuam iguais.")
        return True

    # A classe NADA: so no dinamico. No estatico o app so consulta o modelo
    # com a mao parada, e quem decide "nao e letra" la e o portao de confianca.
    if tipo == "dinamico" and com_nada:
        Xn, gn = carrega_negativos(tipo, n_features, com_grupos=True)
        if Xn is None:
            print("  sem exemplos de 'nao e letra': o modelo sai sem a classe %s." % NADA)
        else:
            teto = max(int((y == c).sum()) for c in set(y))
            if len(Xn) > teto:
                escolha = np.random.RandomState(42).choice(len(Xn), teto, replace=False)
                Xn, gn = Xn[escolha], gn[escolha]
            print("  classe %s: %d exemplos de mao que nao esta fazendo letra" % (NADA, len(Xn)))
            X = np.vstack([X, Xn])
            y = np.concatenate([y, np.full(len(Xn), NADA)])
            grupos = np.concatenate([grupos, gn]) if grupos is not None else None

    if espelho:
        X, y, grupos = com_espelho(X, y, grupos)
        print("  com espelho: %d amostras (cada uma tambem com a outra mao)" % len(X))

    if not checa_regressao(sorted(set(y)), pasta_assets, forcar):
        return "bloqueado"

    modelo, classes = treina(X, y, grupos)

    destino_modelo = pasta_assets / "geral" / "model.onnx"
    destino_labels = pasta_assets / "geral" / "labels.txt"

    guarda_copia(pasta_assets)
    exporta_onnx(modelo, n_features, destino_modelo)
    salva_labels(classes, destino_labels)

    print("  gerado: %s (%.0f KB)"
          % (destino_modelo.relative_to(REPO), destino_modelo.stat().st_size / 1024))
    print("  gerado: %s -> %s"
          % (destino_labels.relative_to(REPO), " ".join(classes)))

    ok = valida(destino_modelo, n_features, len(classes))

    if limpar:
        removidos = limpa_individuais(pasta_assets, classes)
        if removidos:
            print("  removidos modelos individuais: %s" % ", ".join(removidos))
    else:
        individuais = [p.name for p in pasta_assets.iterdir()
                       if p.is_dir() and p.name != "geral"]
        if individuais:
            print("\n  ATENCAO: existem modelos individuais aqui: %s"
                  % ", ".join(individuais))
            print("  O app testa os individuais ANTES do geral, entao essas letras")
            print("  vao continuar usando o modelo antigo. Use --limpar-individuais")
            print("  se quiser que o modelo que voce acabou de treinar valha.")

    return ok


def main():
    ap = argparse.ArgumentParser(
        description="Treina e exporta os modelos .onnx do app Android.")
    ap.add_argument("--tipo", choices=["estatico", "dinamico", "todos"],
                    default="todos", help="qual modelo gerar (padrao: todos)")
    ap.add_argument("--limpar-individuais", action="store_true",
                    help="apaga os modelos por letra, que tem precedencia sobre o geral")
    ap.add_argument("--forcar", action="store_true",
                    help="exporta mesmo que o app perca letras que ja conhecia")
    ap.add_argument("--reforcar", metavar="LETRAS",
                    help="aprimora SO estas letras (ex: --reforcar E,F,G), gerando "
                         "modelos individuais e sem tocar no modelo geral")
    ap.add_argument("--sem-espelho", action="store_true",
                    help="nao acrescenta as amostras espelhadas (outra mao)")
    ap.add_argument("--sem-nada", action="store_true",
                    help="modelo dinamico sem a classe NADA (como era antes)")
    args = ap.parse_args()

    if not ASSETS.exists():
        print("ERRO: nao achei a pasta de assets do app em %s" % ASSETS)
        return 1

    reforcar = None
    if args.reforcar:
        # Aceita as formas que alguem digita na pratica: "E,F,G", "E F G",
        # "e;f;g" e com aspas sobrando do .bat.
        bruto = args.reforcar.strip().strip('"').strip("'")
        for separador in (";", " "):
            bruto = bruto.replace(separador, ",")
        reforcar = [x.strip().upper() for x in bruto.split(",") if x.strip()]
        conhecidas = set(LETRAS_DO_TIPO["estatico"]) | set(LETRAS_DO_TIPO["dinamico"])
        desconhecidas = [l for l in reforcar if l not in conhecidas]
        if desconhecidas:
            print("ERRO: nao conheco a(s) letra(s): %s" % " ".join(desconhecidas))
            print("Validas: %s" % " ".join(sorted(conhecidas)))
            return 1
        print("Modo REFORCO: %s (o modelo geral nao sera alterado)" % " ".join(reforcar))

    tipos = ["estatico", "dinamico"] if args.tipo == "todos" else [args.tipo]
    resultados = {t: processa(t, args.limpar_individuais, args.forcar, reforcar,
                              espelho=not args.sem_espelho, com_nada=not args.sem_nada)
                  for t in tipos}

    print("\n" + "=" * 62)
    for t, r in resultados.items():
        if r is None:
            rotulo = "sem dados (nao gravou ainda)"
        elif r == "bloqueado":
            rotulo = "NAO EXPORTADO - perderia letras (veja acima)"
        elif r:
            rotulo = "OK - modelo novo no app"
        else:
            rotulo = "gerado, mas nao passou na validacao"
        print("  %-9s %s" % (t, rotulo))
    print("=" * 62)

    exportou = [t for t, r in resultados.items() if r is True]
    if not exportou:
        print("\nNenhum modelo novo foi gerado -- o app continua como estava.")
        return 1

    print("\nProximo passo -- instalar o app com os modelos novos:")
    print("  pelo Android Studio: abra a pasta 'mobile' e clique em Run")
    print("  ou pelo terminal:    cd mobile  &&  .\\gradlew.bat assembleDebug")
    return 0


if __name__ == "__main__":
    sys.exit(main())

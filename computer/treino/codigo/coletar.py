"""
Coleta pelo APP: o celular guarda as janelas que ELE entrega ao modelo das
letras com movimento (H J K X Z) e o computador leva pro banco de pontos.

Por que existe: as gravacoes da webcam e as do app nao sao iguais -- a camera
do celular, a velocidade e o tremor mudam. Medido: as janelas do app ficam a
distancia 3 a 6 de qualquer janela do banco, contra 0.8 entre duas gravacoes da
webcam, e o modelo respondia Z como X com 100% de certeza. Treinando tambem com
o que o app entrega, tentativas que o treino nunca viu passaram a sair certas.

Como usar (o .bat "4 - Coletar letra com movimento pelo app.bat" abre isto):

  1. Celular no cabo, depuracao USB ligada, app instalado pelo Android Studio
     (build de depuracao) e aberto no modo ALFABETO.
  2. Escolha a letra aqui, faca o movimento no app varias vezes (uns 30 s) e
     tecle ENTER. As janelas vao pra computer/treino/pontos/letras/<LETRA>/.
  3. Para NADA: mexa a mao SEM fazer letra (trocar de letra, levantar a mao).

Depois e so rodar o "3 - Retreinar letras.bat".
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import pontos  # noqa: E402

ADB = None
PACOTE = "com.visuall.app"
ARQUIVO_LOG = "files/diag_dinamico.txt"
ARQUIVO_FLAG = "files/coletando"
JANELA = 420
APARA_S = 1.0          # corta o primeiro e o ultimo segundo (apertar ENTER, abaixar a mao)
MINIMO_JANELAS = 30


def acha_adb():
    candidatos = ["adb"]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidatos.append(str(Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe"))
    candidatos.append(str(Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"))
    for c in candidatos:
        try:
            subprocess.run([c, "version"], capture_output=True, check=True)
            return c
        except (OSError, subprocess.CalledProcessError):
            continue
    return None


def adb(args, entrada=None):
    return subprocess.run([ADB] + args, capture_output=True, input=entrada)


def celular_conectado():
    saida = adb(["devices"]).stdout.decode("utf-8", "replace").splitlines()[1:]
    return any(l.strip().endswith("device") for l in saida)


def no_app(comando):
    """Roda um comando dentro da pasta do app (so funciona em build de depuracao)."""
    return adb(["shell", "run-as", PACOTE, "sh", "-c", comando])


def liga_coleta():
    r = no_app("rm -f %s; echo 1 > %s" % (ARQUIVO_LOG, ARQUIVO_FLAG))
    return r.returncode == 0


def traz_janelas():
    """Desliga a coleta e devolve (instantes_ms, janelas [n, 420])."""
    no_app("rm -f %s" % ARQUIVO_FLAG)
    r = adb(["exec-out", "run-as", PACOTE, "cat", ARQUIVO_LOG])
    tempos, janelas = [], []
    for linha in r.stdout.decode("utf-8", "replace").splitlines():
        partes = linha.strip().split("|")
        if len(partes) != 4:
            continue
        try:
            valores = [float(v) for v in partes[3].split(",")]
            if len(valores) == JANELA:
                tempos.append(int(partes[0]))
                janelas.append(valores)
        except ValueError:
            continue
    return np.array(tempos), np.array(janelas, dtype=np.float32).reshape(-1, JANELA)


def apara(tempos, janelas, rotulo):
    """Tira o comeco e o fim (o dedo no ENTER, a mao descendo) das letras."""
    if rotulo == comum.NADA or len(tempos) == 0:
        return janelas
    duracao = (tempos[-1] - tempos[0]) / 1000.0
    if duracao < 3 * APARA_S:
        return janelas
    return janelas[(tempos >= tempos[0] + APARA_S * 1000) & (tempos <= tempos[-1] - APARA_S * 1000)]


def salva(rotulo, janelas):
    pasta = comum.PONTOS / "letras" / rotulo
    pasta.mkdir(parents=True, exist_ok=True)
    ident = "app_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = pasta / (ident + ".npz")
    np.savez_compressed(destino, versao=pontos.VERSAO, tipo="janelas", origem=np.array(["app"]),
                        janelas=janelas.astype(np.float16))
    return destino


def importa_arquivo(caminho):
    """Usa um diag_dinamico.txt ja puxado do celular (sem adb)."""
    tempos, janelas = [], []
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        partes = linha.strip().split("|")
        if len(partes) == 4:
            tempos.append(int(partes[0]))
            janelas.append([float(v) for v in partes[3].split(",")])
    return np.array(tempos), np.array(janelas, dtype=np.float32).reshape(-1, JANELA)


def salva_palavra(rotulo, janelas):
    """Janelas de 30 quadros (225 numeros cada) que o app entregou ao modelo de palavras."""
    pasta = comum.PONTOS / "palavras" / rotulo
    pasta.mkdir(parents=True, exist_ok=True)
    ident = "app_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = pasta / (ident + ".npz")
    np.savez_compressed(destino, versao=pontos.VERSAO, tipo="janelas", origem=np.array(["app"]),
                        janelas=janelas.astype(np.float16).reshape(len(janelas), 30, 225))
    return destino


def importa_palavras(caminho, trechos):
    """Usa um diag_corpo.txt puxado do celular. `trechos`: {PALAVRA: [(ini_s, fim_s), ...]}
    (segundos desde a primeira janela). Corta 1 s de cada ponta."""
    tempos, janelas = [], []
    for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
        partes = linha.strip().split("|")
        if len(partes) != 3:
            continue
        v = [float(x) for x in partes[2].split(",") if x]
        if len(v) == 30 * 225:
            tempos.append(int(partes[0]))
            janelas.append(v)
    tempos, janelas = np.array(tempos), np.array(janelas, dtype=np.float32)
    segundos = (tempos - tempos[0]) / 1000.0
    saida = {}
    for palavra, faixas in trechos.items():
        sel = np.zeros(len(tempos), bool)
        for ini, fim in faixas:
            sel |= (segundos >= ini + APARA_S) & (segundos <= fim - APARA_S)
        saida[palavra] = janelas[sel]
    return saida


def letras_da_coleta():
    return sorted(comum.letras_dinamicas()) + [comum.NADA]


def uma_rodada(rotulo):
    print("\n  Preparando o celular...")
    if not liga_coleta():
        print("  ERRO: nao consegui falar com o app. Confira:")
        print("   - o app foi instalado pelo Android Studio (build de depuracao)?")
        print("   - a depuracao USB esta ligada e voce autorizou este computador?")
        return False
    if rotulo == comum.NADA:
        instrucao = "mexa a mao SEM fazer letra (troque de letra, levante a mao, coce a cabeca)"
    else:
        instrucao = "faca a letra %s varias vezes, do jeito que voce usa no dia a dia" % rotulo
    print("\n  AGORA, no celular (modo ALFABETO):")
    print("     %s" % instrucao)
    print("     por uns 30 segundos, devagar e rapido, perto e longe.")
    input("\n  Quando terminar, tecle ENTER aqui... ")
    tempos, janelas = traz_janelas()
    janelas = apara(tempos, janelas, rotulo)
    if len(janelas) < MINIMO_JANELAS:
        print("  So %d janelas (minimo %d): o app quase nao viu movimento. Confira se esta no"
              " modo alfabeto,\n  com a mao a vista, e tente de novo." % (len(janelas), MINIMO_JANELAS))
        return False
    destino = salva(rotulo, janelas)
    print("  Guardei %d janelas de %s em %s" % (len(janelas), rotulo, destino.relative_to(comum.REPO)))
    return True


def main():
    global ADB
    if len(sys.argv) >= 4 and sys.argv[1] == "--importar":
        tempos, janelas = importa_arquivo(sys.argv[2])
        janelas = apara(tempos, janelas, sys.argv[3])
        print("guardado:", salva(sys.argv[3], janelas), len(janelas), "janelas")
        return 0

    ADB = acha_adb()
    if ADB is None:
        print("ERRO: nao achei o adb. Ele vem com o Android Studio (platform-tools).")
        return 1
    if not celular_conectado():
        print("ERRO: nenhum celular no cabo. Ligue a depuracao USB e autorize este computador.")
        return 1

    opcoes = letras_da_coleta()
    while True:
        print("\n  Letras: %s" % "  ".join(opcoes))
        escolha = input("  Qual letra voce vai coletar? (Q sai) ").strip().upper()
        if escolha in ("Q", ""):
            break
        if escolha not in opcoes:
            print("  Nao conheco '%s'." % escolha)
            continue
        uma_rodada(escolha)
    print("\n  Proximo passo: '3 - Retreinar letras.bat' (feche a camera com Q e responda S).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

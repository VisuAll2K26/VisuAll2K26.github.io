"""
Gravador do VisuAll: abre a webcam, voce aperta ESPACO e ele grava 3 segundos.

Cada gravacao vai sozinha pra pasta certa, que e onde o treino procura:

    letra parada:        gravacoes/letras/<LETRA>/AAAAMMDD_HHMMSS_NN.jpg (18 fotos)
    letra com movimento: gravacoes/letras/<LETRA>/AAAAMMDD_HHMMSS.mp4
    NADA:                gravacoes/letras/NADA/AAAAMMDD_HHMMSS.mp4
    palavra:             gravacoes/palavras/<PALAVRA>/AAAAMMDD_HHMMSS.mp4

Letra parada vira FOTOS porque o treino dela e foto a foto: nos 3 segundos,
mexa um pouco o angulo e a distancia da mao (sem desfazer a letra) e cada
foto ensina uma variacao. As 18 fotos de um ESPACO contam como UMA gravacao.

Tres jeitos de abrir (cada .bat abre um):

    python gravar.py palavra-nova   comeca pedindo o nome da palavra
    python gravar.py palavras       percorre as palavras que o app ja sabe
    python gravar.py letras         percorre o alfabeto (e o NADA)

Teclas:
    ESPACO        grava (3 s pra se posicionar, depois 3 s gravando/fotografando)
    R             regrava: apaga a ultima gravacao desta letra/palavra e grava de novo
    X ou DELETE   apaga a ultima gravacao desta letra/palavra (de novo: a anterior)
    N ou ->       proxima letra/palavra
    P ou <-       anterior
    TAB           palavra nova (abre o campo pra digitar o nome)
    0             vai direto pro NEUTRO (palavras), que a tela guia o que gravar
    ESC durante a contagem/gravacao: cancela aquela gravacao
    Q ou ESC      sai
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import pontos  # noqa: E402

CONTAGEM_S = 3.0
GRAVACAO_S = 3.0
FOTOS_POR_GRAVACAO = 18   # o mesmo tanto da rajada do gravador antigo
NOME_MAXIMO = 24

DIGITANDO, PARADO, CONTAGEM, GRAVANDO = "digitando", "parado", "contagem", "gravando"

# Codigos do cv2.waitKeyEx no Windows (setas e Delete nao tem ASCII).
SETA_DIREITA, SETA_ESQUERDA, DELETE = 2555904, 2424832, 3014656
ESPACO, ENTER, ESC, BACKSPACE, TAB = 32, 13, 27, 8, 9

VERDE = (80, 220, 100)
AMARELO = (60, 200, 250)
VERMELHO = (60, 60, 240)
BRANCO = (245, 245, 245)
CINZA = (170, 170, 170)
FUNDO = (28, 28, 28)


# O NEUTRO ensina o app a NAO inventar palavra quando ninguem esta sinalizando.
# Ele so funciona se tiver de tudo um pouco, principalmente com uma e com as
# duas maos a vista (ter as duas maos na tela nao pode virar sinal). A dica muda
# a cada gravacao pra voce nao precisar pensar no que variar.
NEUTRO_ROTEIRO = [
    "NEUTRO: as DUAS maos paradas a vista (no colo ou na frente), SEM sinal",
    "NEUTRO: so a mao DIREITA a vista, parada, SEM sinal",
    "NEUTRO: so a mao ESQUERDA a vista, parada, SEM sinal",
    "NEUTRO: maos mexendo SEM sinal (ajeite o cabelo, coce o rosto)",
    "NEUTRO: duas maos a vista, uma mais alta que a outra, SEM sinal",
    "NEUTRO: maos subindo e descendo devagar, SEM fazer sinal nenhum",
    "NEUTRO: fale 'oi' e mexa as maos soltas, SEM sinal de Libras",
]


def dica(tipo, rotulo, dinamicas, passo=0):
    """O que a pessoa deve fazer na frente da camera (sem acento: o OpenCV
    nao desenha acento). `passo` gira o roteiro do NEUTRO."""
    if tipo == "palavras":
        if rotulo == comum.NEUTRO:
            return NEUTRO_ROTEIRO[passo % len(NEUTRO_ROTEIRO)]
        return "PALAVRA: tronco e as duas maos dentro da tela"
    if rotulo == comum.NADA:
        return "NADA: mexa a mao SEM fazer letra (troque de letra, coce a cabeca...)"
    if rotulo in dinamicas:
        return "LETRA COM MOVIMENTO: faca o movimento inteiro"
    return "LETRA PARADA: segure a letra e va mudando um pouco o angulo da mao"


def conta(tipo, rotulo):
    """Quantas gravacoes esse rotulo tem: no banco (git) e/ou neste PC."""
    ids = {p.stem for p in (comum.PONTOS / tipo / rotulo).glob("*.npz")}
    pasta = comum.GRAVACOES / tipo / rotulo
    if pasta.is_dir():
        ids |= {pontos.id_da_gravacao(a) for a in pasta.iterdir() if a.is_file()}
    return len(ids)


def salva_video(quadros, pasta, duracao):
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / (datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4")
    altura, largura = quadros[0].shape[:2]
    fps = max(1.0, len(quadros) / duracao)
    escritor = cv2.VideoWriter(str(destino), cv2.VideoWriter_fourcc(*"mp4v"), fps,
                               (largura, altura))
    for quadro in quadros:
        escritor.write(quadro)
    escritor.release()
    return destino


def salva_fotos(quadros, pasta):
    """AAAAMMDD_HHMMSS_NN.jpg: o banco junta a rajada numa gravacao so."""
    pasta.mkdir(parents=True, exist_ok=True)
    inicio = datetime.now().strftime("%Y%m%d_%H%M%S")
    fotos = [pasta / ("%s_%02d.jpg" % (inicio, i)) for i in range(len(quadros))]
    for destino, quadro in zip(fotos, quadros):
        cv2.imwrite(str(destino), quadro, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return fotos


def apaga(tipo, rotulo, arquivos):
    """Apaga os arquivos de uma gravacao e, se o treino ja a leu, os pontos dela."""
    ident = pontos.id_da_gravacao(arquivos[0])
    for caminho in list(arquivos) + [pontos.caminho_pontos(tipo, rotulo, ident)]:
        try:
            caminho.unlink()
        except OSError:
            pass


def texto(img, msg, xy, escala=0.7, cor=BRANCO, grossura=2):
    cv2.putText(img, msg, xy, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0),
                grossura + 3, cv2.LINE_AA)
    cv2.putText(img, msg, xy, cv2.FONT_HERSHEY_SIMPLEX, escala, cor, grossura, cv2.LINE_AA)


def abre_camera(indice):
    for i in ([indice] if indice is not None else [0, 1, 2]):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) if sys.platform == "win32" else cv2.VideoCapture(i)
        if cap.isOpened():
            # 640x480 (4:3) e a proporcao em que os modelos aprendem.
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if cap.read()[0]:
                return cap
        cap.release()
    return None


class Gravador:
    def __init__(self, modo):
        self.tipo = "letras" if modo == "letras" else "palavras"
        self.aceita_nome = self.tipo == "palavras"
        if modo == "letras":
            self.itens = comum.alfabeto() + [comum.NADA]
        elif modo == "palavras":
            self.itens = sorted(set(comum.palavras_do_app()) | set(comum.rotulos_gravados("palavras")))
        else:
            self.itens = []
        self.idx = 0
        self.estado = DIGITANDO if not self.itens else PARADO
        self.nome = ""
        self.marca = 0.0
        self.buffer = []
        self.aviso = ("Digite o nome da palavra nova e tecle ENTER"
                      if self.estado == DIGITANDO else "")
        self.feitas = {}     # rotulo -> [arquivos de cada gravacao desta sessao], em ordem
        self.regravar = False
        self.dinamicas = set(comum.letras_dinamicas())
        self._contagem = {}  # contar arquivos a cada quadro pesa num pendrive

    def contagem(self):
        if self.rotulo not in self._contagem:
            self._contagem[self.rotulo] = conta(self.tipo, self.rotulo)
        return self._contagem[self.rotulo]

    @property
    def rotulo(self):
        return self.itens[self.idx % len(self.itens)] if self.itens else ""

    def pasta(self):
        return comum.GRAVACOES / self.tipo / self.rotulo

    def em_fotos(self):
        """Letra parada grava fotos; letra com movimento, NADA e palavra, video."""
        return self.tipo == "letras" and self.rotulo != comum.NADA             and self.rotulo not in self.dinamicas

    # ── teclas ─────────────────────────────────────────────────────────
    def tecla(self, codigo, agora):
        """Devolve False quando e pra sair."""
        if codigo == -1:
            return True
        if self.estado == DIGITANDO:
            return self._tecla_nome(codigo)
        if self.estado in (CONTAGEM, GRAVANDO):
            if codigo == ESC:
                self.estado, self.buffer = PARADO, []
                self.aviso = "Gravacao cancelada. Nada foi salvo."
            return True

        letra = chr(codigo).lower() if 0 < codigo < 256 else ""
        if codigo == ESC or letra == "q":
            return False
        if codigo == ESPACO:
            self._comeca(agora)
        elif letra == "r":
            if self._apaga_ultima():
                self.regravar = True
            self._comeca(agora)
        elif letra == "x" or codigo == DELETE or codigo == BACKSPACE:
            if not self._apaga_ultima():
                self.aviso = "Nada pra apagar de %s nesta sessao." % self.rotulo
        elif letra == "n" or codigo == SETA_DIREITA:
            self.idx = (self.idx + 1) % len(self.itens)
            self.aviso = ""
        elif letra == "p" or codigo == SETA_ESQUERDA:
            self.idx = (self.idx - 1) % len(self.itens)
            self.aviso = ""
        elif codigo == TAB and self.aceita_nome:
            self.estado, self.nome = DIGITANDO, ""
            self.aviso = "Digite o nome da palavra nova e tecle ENTER (ESC volta)"
        elif letra == "0" and self.aceita_nome:
            self._vai_para(comum.NEUTRO)
        return True

    def _vai_para(self, nome):
        """Pula pra uma palavra (criando a pasta se ainda nao houver)."""
        if nome not in self.itens:
            self.itens.append(nome)
        self.idx = self.itens.index(nome)
        self.pasta().mkdir(parents=True, exist_ok=True)
        self.aviso = ""

    def _tecla_nome(self, codigo):
        if codigo == ESC:
            if not self.itens:
                return False
            self.estado, self.aviso = PARADO, ""
        elif codigo == BACKSPACE:
            self.nome = self.nome[:-1]
        elif codigo == ENTER:
            nome = comum.nome_de_palavra(self.nome)
            if not nome:
                self.aviso = "Escreva um nome antes do ENTER."
                return True
            ja_existe = nome in self.itens or nome in comum.palavras_do_app() \
                or conta(self.tipo, nome) > 0
            if nome not in self.itens:
                self.itens.append(nome)
            self.idx = self.itens.index(nome)
            self.pasta().mkdir(parents=True, exist_ok=True)
            self.estado = PARADO
            self.aviso = ("%s ja existe: as gravacoes novas somam as dela." % nome if ja_existe
                          else "Pasta criada: gravacoes/palavras/%s. ESPACO grava." % nome)
        elif 0 < codigo < 128 and len(self.nome) < NOME_MAXIMO:
            caractere = chr(codigo)
            if caractere.isalnum() or caractere == " ":
                self.nome += caractere.upper()
        return True

    def _comeca(self, agora):
        self.estado, self.marca, self.buffer = CONTAGEM, agora, []
        self.aviso = ""

    def _apaga_ultima(self):
        pilha = self.feitas.get(self.rotulo, [])
        if not pilha:
            return False
        arquivos = pilha.pop()
        apaga(self.tipo, self.rotulo, arquivos)
        self._contagem.pop(self.rotulo, None)
        nome = pontos.id_da_gravacao(arquivos[0])
        self.aviso = "APAGADA: %s" % nome
        print("  [%s] apagada %s" % (self.rotulo, nome))
        return True

    # ── tempo ──────────────────────────────────────────────────────────
    def quadro(self, imagem, agora):
        if self.estado == CONTAGEM and agora - self.marca >= CONTAGEM_S:
            self.estado, self.marca, self.buffer = GRAVANDO, agora, []
        elif self.estado == GRAVANDO:
            fotos = self.em_fotos()
            decorrido = agora - self.marca
            # Foto: uma a cada GRAVACAO_S / FOTOS_POR_GRAVACAO, espalhadas nos 3 s.
            if not fotos or (len(self.buffer) < FOTOS_POR_GRAVACAO and
                             decorrido >= len(self.buffer) * GRAVACAO_S / FOTOS_POR_GRAVACAO):
                self.buffer.append(imagem.copy())
            if decorrido >= GRAVACAO_S:
                if fotos:
                    arquivos = salva_fotos(self.buffer, self.pasta())
                    unidade, minimo = "fotos", FOTOS_POR_GRAVACAO // 2
                else:
                    arquivos = [salva_video(self.buffer, self.pasta(), GRAVACAO_S)]
                    unidade, minimo = "quadros", 30
                self.feitas.setdefault(self.rotulo, []).append(arquivos)
                self._contagem.pop(self.rotulo, None)
                self.aviso = "%s: %s salva (%d %s)%s" % (
                    self.rotulo, "regravada" if self.regravar else "gravacao", len(self.buffer),
                    unidade, "" if len(self.buffer) >= minimo else " -- POUCOS, camera lenta?")
                print("  [%s] %s (%d %s)" % (self.rotulo, pontos.id_da_gravacao(arquivos[0]),
                                             len(self.buffer), unidade))
                self.estado, self.buffer, self.regravar = PARADO, [], False

    # ── tela ───────────────────────────────────────────────────────────
    def desenha(self, imagem, agora):
        vista = cv2.flip(imagem, 1)   # espelho so na tela; o que e salvo e o quadro cru
        h, w = vista.shape[:2]
        cv2.rectangle(vista, (0, 0), (w, 112), FUNDO, -1)
        cv2.rectangle(vista, (0, h - 76), (w, h), FUNDO, -1)

        if self.estado == DIGITANDO:
            texto(vista, "NOME DA PALAVRA:", (20, 34), 0.7, CINZA, 2)
            texto(vista, "(pra treinar o NEUTRO, sem sinal: escreva NEUTRO)", (20, 106), 0.45, CINZA, 1)
            cursor = "_" if int(agora * 2) % 2 == 0 else " "
            texto(vista, self.nome + cursor, (20, 84), 1.4, AMARELO, 3)
        else:
            texto(vista, self.rotulo, (20, 68), 1.9 if len(self.rotulo) < 9 else 1.1, VERDE, 4)
            texto(vista, "%d gravacoes" % self.contagem(), (w - 190, 34), 0.6, CINZA, 1)
            texto(vista, "%d de %d" % (self.idx + 1, len(self.itens)), (w - 190, 62), 0.6, CINZA, 1)
            texto(vista, dica(self.tipo, self.rotulo, self.dinamicas, self.contagem()),
                  (20, 100), 0.5, BRANCO, 1)

        if self.estado == CONTAGEM:
            texto(vista, str(int(CONTAGEM_S - (agora - self.marca)) + 1), (w // 2 - 30, h // 2),
                  4.0, AMARELO, 8)
            texto(vista, "prepare-se", (w // 2 - 90, h // 2 + 60), 0.9, AMARELO, 2)
        elif self.estado == GRAVANDO:
            decorrido = agora - self.marca
            cv2.circle(vista, (w - 40, 150), 14, VERMELHO, -1)
            if self.em_fotos():
                texto(vista, "FOTOS %d/%d" % (len(self.buffer), FOTOS_POR_GRAVACAO),
                      (w - 250, 158), 0.7, VERMELHO, 2)
            else:
                texto(vista, "GRAVANDO %.1fs" % decorrido, (w - 250, 158), 0.7, VERMELHO, 2)
            cv2.rectangle(vista, (0, h - 81), (int(w * decorrido / GRAVACAO_S), h - 76),
                          VERMELHO, -1)

        if self.aviso and self.estado in (PARADO, DIGITANDO):
            texto(vista, self.aviso, (16, h - 46), 0.5, VERDE, 1)
        if self.estado == DIGITANDO:
            comandos = "letras/numeros escrevem | BACKSPACE apaga | ENTER confirma | ESC volta"
        elif self.estado == PARADO:
            comandos = "ESPACO grava | R regrava | X apaga ultima | N/P troca | " + \
                       ("TAB palavra nova | 0 NEUTRO | " if self.aceita_nome else "") + "Q sai"
        else:
            comandos = "ESC cancela esta gravacao"
        texto(vista, comandos, (16, h - 16), 0.45, CINZA, 1)
        return vista


def main():
    ap = argparse.ArgumentParser(description="Grava letras e palavras pro treino.")
    ap.add_argument("modo", choices=["palavra-nova", "palavras", "letras"])
    ap.add_argument("--camera", type=int, help="indice da webcam (padrao: a primeira que abrir)")
    args = ap.parse_args()

    cap = abre_camera(args.camera)
    if cap is None:
        print("ERRO: nao consegui abrir a webcam.")
        print("Feche Zoom, Teams, OBS ou outro programa que esteja usando a camera.")
        return 1

    gravador = Gravador(args.modo)
    janela = "VisuAll - gravar (%s)" % args.modo
    cv2.namedWindow(janela, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(janela, 960, 720)
    print("Gravando em: %s" % (comum.GRAVACOES / gravador.tipo))

    try:
        while True:
            ok, imagem = cap.read()
            if not ok:
                print("ERRO: a webcam parou de mandar imagem.")
                break
            agora = time.monotonic()
            gravador.quadro(imagem, agora)
            cv2.imshow(janela, gravador.desenha(imagem, agora))
            if not gravador.tecla(cv2.waitKeyEx(1), agora):
                break
            if cv2.getWindowProperty(janela, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    feitas = {r: len(v) for r, v in gravador.feitas.items() if v}
    if feitas:
        print("\nGravado agora: " + ", ".join("%s %d" % kv for kv in sorted(feitas.items())))
    else:
        print("\nNenhuma gravacao nova nesta sessao.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

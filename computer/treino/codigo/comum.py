"""
O que todos os scripts de treino dividem: onde as coisas ficam e quais
letras/palavras existem. Mudou uma pasta? Muda aqui e so aqui.

    computer/treino/
        gravacoes/<letras|palavras>/<ROTULO>/   videos e fotos (so neste PC)
        pontos/<letras|palavras>/<ROTULO>/      os numeros tirados de cada
                                                gravacao (vao pro git)
        modelos_anteriores/                     copia de cada modelo antes
                                                de um treino substitui-lo
"""
import sys
import unicodedata
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TREINO = Path(__file__).resolve().parents[1]
COMPUTER = TREINO.parent
REPO = COMPUTER.parent

GRAVACOES = TREINO / "gravacoes"
PONTOS = TREINO / "pontos"
BACKUPS = TREINO / "modelos_anteriores"

ASSETS = REPO / "mobile" / "app" / "src" / "main" / "assets"
ASSETS_ESTATICAS = ASSETS / "letras_estaticas"
ASSETS_DINAMICAS = ASSETS / "letras_dinamicas"
ASSETS_PALAVRAS = ASSETS / "gestos" / "geral"

# "A mao apareceu, mas nao esta fazendo letra nenhuma". Grava-se como se fosse
# uma letra (pasta letras/NADA); o modelo das letras com movimento aprende
# como classe propria, e o app trata como "nao sei" (LetterDecision).
NADA = "NADA"
# "Parado, sem sinal" do modo corpo. E uma palavra do modelo como as outras,
# mas o app nunca a escreve na frase (BodyGestureEngine).
NEUTRO = "NEUTRO"

# Valem so quando o app nao tem o labels.txt (checkout sem Git LFS, por
# exemplo). Fora isso, a lista sai sempre do proprio app.
_ESTATICAS_PADRAO = list("ABCDEFGILMNOPQRSTUVWY")
_DINAMICAS_PADRAO = ["H", "J", "K", "X", "Z"]


def le_labels(caminho):
    """Uma linha por rotulo, na ordem das saidas do modelo."""
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except OSError:
        return []
    return [linha.strip() for linha in texto.splitlines() if linha.strip()]


def letras_estaticas():
    return le_labels(ASSETS_ESTATICAS / "geral" / "labels.txt") or list(_ESTATICAS_PADRAO)


def letras_dinamicas():
    letras = [l for l in le_labels(ASSETS_DINAMICAS / "geral" / "labels.txt") if l != NADA]
    return letras or list(_DINAMICAS_PADRAO)


def palavras_do_app():
    return le_labels(ASSETS_PALAVRAS / "labels.txt")


def alfabeto():
    """As letras que o gravador mostra: as paradas e as com movimento, em ordem."""
    return sorted(set(letras_estaticas()) | set(letras_dinamicas()))


def eh_dinamica(rotulo):
    """Letras com movimento e o NADA sao lidos como video; as paradas, como fotos."""
    return rotulo in letras_dinamicas() or rotulo == NADA


def nome_de_palavra(texto):
    """O nome que vira pasta e aparece na frase do app: maiusculo, sem acento.

    Sem acento porque a janela do gravador (OpenCV) nao desenha acento e o
    nome tem que ser o mesmo nos dois lugares. "bom  dia!" -> "BOM DIA".
    """
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpo = "".join(c if c.isalnum() else " " for c in sem_acento.upper())
    return " ".join(limpo.split())


def rotulos_gravados(tipo):
    """Rotulos que tem gravacao neste PC ou pontos no git."""
    nomes = set()
    for base in (GRAVACOES / tipo, PONTOS / tipo):
        if base.is_dir():
            nomes |= {p.name for p in base.iterdir() if p.is_dir() and any(p.iterdir())}
    return sorted(nomes)

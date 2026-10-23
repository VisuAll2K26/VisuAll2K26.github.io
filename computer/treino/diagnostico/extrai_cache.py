"""Monta o cache_corpo.npz que os diagnosticos de corpo leem.

Guarda a sequencia inteira de cada gravacao de palavra (quadros ja
normalizados, sem recortes), pra avaliar separando treino e teste por
gravacao. Sai do banco de pontos (computer/treino/pontos/palavras), entao
nao precisa dos videos nem do MediaPipe: leva segundos, em qualquer PC.
"""
import sys
from pathlib import Path

import numpy as np

COMPUTER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COMPUTER / "treino" / "codigo"))

import pontos  # noqa: E402
import treinar_palavras as tc  # noqa: E402

SAIDA = Path(__file__).parent / "cache_corpo.npz"


def main():
    pontos.atualiza("palavras")
    seqs, rotulos, nomes = [], [], []
    contagem = {}
    for rotulo, ident, dados in pontos.carrega("palavras"):
        quadros = tc.quadros_da_gravacao(dados)
        if len(quadros) < tc.QUADROS_MINIMOS:
            print("    %s/%s: so %d quadros com corpo - ignorado" % (rotulo, ident, len(quadros)))
            continue
        seqs.append(np.array(quadros, dtype=np.float32))
        rotulos.append(rotulo)
        nomes.append("%s/%s" % (rotulo, ident))
        contagem[rotulo] = contagem.get(rotulo, 0) + 1
    for rotulo, n in sorted(contagem.items()):
        print("  %-12s %d gravacoes" % (rotulo, n))

    np.savez_compressed(SAIDA, seqs=np.array(seqs, dtype=object),
                        rotulos=np.array(rotulos), nomes=np.array(nomes))
    print("\nsalvo: %s  (%d gravacoes)" % (SAIDA, len(seqs)))


if __name__ == "__main__":
    sys.exit(main())

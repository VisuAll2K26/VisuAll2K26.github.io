"""
Gera computer/data/dataset_dynamic.npz pro reconhecedor de PC
(training/train_dynamic_model.py):

  X     [N, 420]  janelas de 10 quadros * 42 valores
  y     [N]       letra
  grupo [N]       de que gravacao saiu a janela

Os videos nao sao lidos aqui: as janelas saem do banco do treino do app
(computer/treino/pontos), que le cada gravacao uma vez, com a mesma conta que
o app usa. As gravacoes novas sao lidas pro banco antes.

Uso, dentro de computer/:  python linear/backend/data_extraction/extract_from_videos.py
"""
import sys
from pathlib import Path

import numpy as np

COMPUTER = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(COMPUTER / "treino" / "codigo"))

import pontos  # noqa: E402
from treinar_letras import Banco  # noqa: E402

SAIDA = COMPUTER / "data" / "dataset_dynamic.npz"


def main():
    pontos.atualiza("letras")
    banco = Banco()
    X, y, grupo = Banco.arrays(banco.Xm, banco.ym, banco.gm, 420)
    if not len(X):
        print("Nenhuma letra com movimento no banco. Grave no '3 - Retreinar letras.bat'.")
        return 1
    SAIDA.parent.mkdir(exist_ok=True)
    np.savez(SAIDA, X=X, y=y, grupo=grupo)
    print("Dataset salvo em %s: %d janelas, %s" % (
        SAIDA, len(X), {l: int((y == l).sum()) for l in sorted(set(y))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

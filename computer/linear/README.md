# Reconhecedor de PC, num arquivo só

O primeiro VisuAll: reconhece Libras pela webcam do computador e mostra o
resultado numa página web. Hoje ele serve de **referência**: quando o app se
comporta diferente, a primeira pergunta é "o que o Python faz aqui?".

| Arquivo | O que é |
|---|---|
| `backend/app.py` | O reconhecedor inteiro: webcam, MediaPipe Holistic, modelos, tradução da frase e o servidor que manda tudo para a página. |
| `backend/data_extraction/` | Monta os datasets do reconhecedor de PC (`../data/dataset_*.npz`) a partir do banco de pontos do treino ([`../treino/pontos/`](../treino/)). |
| `backend/training/` | Treina os modelos de letras do PC (`.pkl` em `../models/`). |
| `frontend/index.html` | A página que mostra a câmera, a letra e a frase. |

## Rodar

```powershell
cd computer
python linear\backend\app.py
```

Depois abra `linear\frontend\index.html` no navegador.

Dois modos, escolhidos pela página: **alfabeto** (só a mão) e **corpo** (corpo
e mãos). Nos dois, a sobrancelha levantada transforma a frase em pergunta.

A mesma coisa dividida em partes menores está em [`../modular/`](../modular/).

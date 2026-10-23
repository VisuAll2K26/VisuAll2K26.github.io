# 💻 Lado PC

Tudo o que roda no computador: **gravar vídeos de sinais, treinar os modelos**
que vão para o app e o **reconhecedor de referência** em Python, que foi o
primeiro VisuAll e continua sendo a régua do app.

O celular não depende de nada daqui para funcionar. O PC só entra quando
alguém quer ensinar uma letra ou um sinal novo.

---

## O que tem em cada pasta

| Pasta | O que é | Guia |
|---|---|---|
| [`treino/`](treino/) | **Gravar e treinar** letras e palavras, por duplo-clique nos `.bat`. É a pasta que você mais vai usar. | [treino/README.md](treino/README.md) |
| [`treino/diagnostico/`](treino/diagnostico/) | Scripts que **medem** o treino e o app: acerto honesto, limiares, velocidade. | [README](treino/diagnostico/README.md) |
| [`linear/`](linear/) | O reconhecedor de PC **num arquivo só**, mais a página web que mostra o resultado. | [README](linear/README.md) |
| [`modular/`](modular/) | O **mesmo** reconhecedor, dividido em 10 módulos pequenos para ler e estudar. | [README](modular/README.md) |
| [`models/`](models/) | Os modelos `.pkl` que o reconhecedor de PC usa. O app **não** usa estes. | [README](models/README.md) |
| [`tests/`](tests/) | O **contrato** entre o Python e o app: as contas dos dois lados têm que dar o mesmo número. | [README](tests/README.md) |
| `data/` | Os datasets do reconhecedor de PC (`dataset_*.npz`), gerados a partir do banco de pontos do treino. Não vai para o git. | — |

E os guias soltos nesta pasta:

| Arquivo | Para quê |
|---|---|
| [`VALIDACAO.md`](VALIDACAO.md) | O roteiro de **teste no celular de verdade**, para saber se uma mudança melhorou ou piorou. |
| `requirements.txt` | As bibliotecas Python, com as versões que funcionam juntas. |

---

## Instalar (uma vez)

Precisa do **Python 3.11** (funciona do 3.10 ao 3.12). Os `.bat` do treino
criam o ambiente `computer\.venv` e instalam tudo sozinhos na primeira vez.
Para fazer na mão:

```powershell
cd computer
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Treinar um modelo para o app

```text
treino\1 - Adicionar palavra nova.bat    ensinar uma palavra nova
treino\2 - Retreinar palavras.bat        melhorar as palavras que o app já sabe
treino\3 - Retreinar letras.bat          melhorar as letras
```

Cada um abre a câmera para gravar e, ao fechar, treina. O treino grava o
modelo **direto** em `mobile/app/src/main/assets/` e **soma** as gravações
novas ao banco de pontos (`treino/pontos/`, no git), então nada que já foi
gravado é perdido. Depois é só rodar o app de novo.

Passo a passo: [treino/README.md](treino/README.md).

---

## Rodar o reconhecedor no PC

```powershell
python linear\backend\app.py
```

Com ele rodando, abra `linear\frontend\index.html` no navegador.
`python modular\app_backend_unificado.py` faz a mesma coisa pela versão em
módulos.

---

## Conferir que nada quebrou

```powershell
.venv\Scripts\python -m compileall -q treino linear modular tests   # todo arquivo ainda abre
.venv\Scripts\python -m unittest discover -s treino/tests -v        # testes do treino
```

O CI roda isso, e mais o contrato com o app, a cada push que mexe aqui.

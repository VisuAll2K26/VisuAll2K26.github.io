# Retreino final: C, D, V, H, K e PESSOA/SURDO

Passo a passo para o último retreino das letras com problema e dos sinais
PESSOA e SURDO. Tudo que está aqui foi medido nos vídeos e fotos de
`computer/data` com o caminho do app reproduzido no PC
(`diagnostico/simula_dinamicas.py` e `diagnostico/simula_estaticas.py`).

---

## Por que cada uma falha

| O que acontece no app | O que a medição mostrou |
|---|---|
| **Letras com movimento saem fácil**, até trocando de letra parada | O modelo dinâmico só conhece H J K X Z: não tem como responder "não é letra". 96 de 300 trocas entre letras paradas viravam letra com movimento (76 delas H). |
| **H sai fácil** | O modelo de reforço do H responde H para 64% das janelas de K, 76% das de J e 80% das de X. |
| **K não sai** (vira H) | O reforço do K nunca passa de 0,906 numa janela de K (o app exige 0,97) e responde K para o Z. O modelo geral não reconhece nenhuma das 542 janelas de K. |
| **D só sai de perto** | As 18 fotos de D são **uma gravação só**, com a mão ocupando 34% da altura do quadro. Encolhendo a foto (mão mais longe), com a mão a 21% da altura o app dá D em 9 e **L** em 7 de 18. Nenhuma foto de L foi usada como exemplo de "não é D". |
| **C** e **V** (só inclinando a mão) | Não há nenhuma foto de C nem de V neste PC: os reforços de C e V foram treinados em outro computador. Não dá para medir o porquê; dá para refazer com fotos variadas (ângulo, distância, as duas mãos). |
| **PESSOA / SURDO** com as duas mãos | Nos 33 vídeos de PESSOA e 53 de SURDO, **0%** dos quadros têm as duas mãos visíveis (nos outros sinais, 53 a 93%). Com a outra mão aparecendo, o modelo vê um sinal que nunca viu. |

## O que já está pronto (branch `retreino-final-letras`)

No app:
- A letra com movimento só vale se várias janelas seguidas concordarem
  (`DynamicLetterConsensus`).
- O app entende a classe **NADA** do modelo novo: ela nunca aparece na tela
  e nenhum reforço passa por cima dela.
- Os portões das letras com movimento se ajustam sozinhos ao modelo
  (`AjusteDinamico`): com o modelo de hoje ficam como estão; com o modelo
  novo (que tem NADA) afrouxam, porque quem recusa "não é letra" passa a ser
  o modelo.
- O movimento é medido em 330 ms, não em 5 quadros. Antes, o mesmo gesto
  "mexia" mais num celular lento que num rápido.
- Ícone novo.

No treino:
- **Espelho**: cada amostra entra também espelhada (a outra mão). Sem isso,
  com a câmera frontal o acerto caía de 48 para 20 em 95 vídeos.
- **NADA**: o modelo das letras com movimento ganha uma classe "não é
  letra", feita dos clipes de "nada", das mãos dos vídeos de corpo e de
  trocas sintéticas entre letras paradas.
- **Velocidade do celular**: as janelas saem do vídeo a 30, 15 e 10 quadros
  por segundo (o celular roda a ~15; antes o treino só via 30).
- Vídeo e foto de celular em pé entram na proporção certa.
- Quando a mão some um instante, o vídeo não é mais jogado fora inteiro.
- A nota no fim do treino é **por vídeo**: o teste só tem vídeos que o treino
  não viu.
- Antes de substituir um modelo de letras, o treino guarda uma cópia (o
  `RestaurarModelo.bat` devolve).

Retreinando só com os vídeos que já existem (testando sempre em vídeos que
ficaram fora do treino), no caminho do app a 15 quadros/s:

| | main (hoje) | depois do retreino |
|---|---|---|
| Letras com movimento que entram certas | 40 de 95 | **83 de 95** |
| ...e que soltam também uma letra errada | 35 | **2** |
| Trocas entre letras paradas que viram letra | 96 de 300 | **0 de 300** |
| Letras falsas com a mão se mexendo à toa | 17 por minuto | **0,16 por minuto** |
| Por letra (H, J, K, X, Z) | 2/15, 13/15, 0/20, 0/20, 25/25 | 12/15, 15/15, 15/20, 17/20, 24/25 |

Sem retreinar, só com o código novo (consenso e janela de 330 ms) e os
modelos de hoje, as trocas que viram letra já caem para 7 de 300 e a mão à
toa para 7,9 por minuto, mas K e X continuam sem sair — o problema delas é
o modelo.

---

## Quanto gravar

O que conta é o número de **gravações** variadas, não de fotos: cada
gravação de letra parada gera ~18 fotos quase iguais.

### Letras com movimento (modo `dinamica`, vídeo de 3 s)

O modelo novo é treinado do zero com os vídeos de vocês, então **as cinco
letras** precisam estar boas, não só H e K.

| Letra | Tem hoje | Meta | Por quê |
|---|---|---|---|
| **H** | 15 | **35** | Ainda subindo: 53% com 3 vídeos, 73% com 9, 80% com todos |
| **K** | 20 | **35** | Ainda subindo: 40% → 70% → 85% |
| X | 20 | 25 | 85–90%, quase parado |
| J | 15 | 20 | 100% já com 6 vídeos |
| Z | 25 | 25 | 100% já com 6 vídeos |
| **NADA** (modo `nada`) | **0** | **20** | Veja abaixo |

Esses números são de uma pessoa só, num dia só. Com outra pessoa, outra luz
ou outro celular o acerto cai — por isso as metas de H e K ficam bem acima de
onde a curva chegou.

Como variar os vídeos novos (H e K principalmente):
- **duas pessoas** diferentes, se der (é a variação que mais ajuda);
- **as duas mãos** (metade com cada);
- **três distâncias**: perto (mão ocupando ~1/3 da altura da tela), braço
  esticado, e um passo atrás;
- velocidade normal e um pouco mais rápida;
- parte gravada **pelo celular**, câmera frontal, do jeito que o app é usado
  (importe com `python treino\importar.py`).

**NADA** é o mais importante para o "sai letra sozinha". Grave 20 clipes no
modo `nada` fazendo exatamente o que gera o falso positivo:
- trocar de uma letra parada para outra (A→B, D→L, C→O, V→U, S→T...);
- levantar a mão até a posição antes de começar a letra, e baixar depois;
- gesticular como quem conversa, coçar a cabeça, ajeitar o cabelo.

A mão precisa aparecer; só não pode estar fazendo H, J, K, X ou Z.

### Letras paradas (modo `estatica`, 3 s = ~18 fotos)

| Letra | Tem hoje | Meta | Como variar |
|---|---|---|---|
| **D** | 1 gravação (18 fotos) | **15 gravações** | 3 distâncias × as duas mãos, de frente e um pouco de lado |
| **C** | 0 | **15 gravações** | idem |
| **V** | 0 | **15 gravações** | idem, e de propósito com a mão **reta** (é como deve sair) |
| Vizinhas: **L**, **O**, **U**, **R**, **W** | 0 | **5 gravações cada** | ensinam o "não": L ≠ D, O ≠ C, U/R/W ≠ V |
| Todas as outras paradas | A 5, T 4, U 2, S 1, resto 0 | **3 gravações cada** | dão os outros "não" dos modelos novos |

As distâncias: **perto** (mão ocupando ~1/3 da altura do quadro), **braço
esticado** (~1/5) e **um passo atrás** (~1/7). Mais longe que isso o
detector de mão do app começa a perder a mão: com ela ocupando ~1/10 da
altura, ele já não acha a mão em boa parte das fotos.

### PESSOA e SURDO (modo `corpo`, vídeo de 4 s)

| Sinal | Tem hoje | Meta |
|---|---|---|
| PESSOA | 33, todos com uma mão só | **+25 com as duas mãos visíveis** |
| SURDO | 53, todos com uma mão só | **+25 com as duas mãos visíveis** |

A mão que não faz o sinal fica **na tela**, parada onde ela ficaria numa
conversa (ao lado do corpo, na frente da barriga). Varie a posição dela entre
os clipes. Não apague os vídeos antigos. Os outros quatro sinais (AJUDAR,
COMPUTADOR, CONVERSAR, NEUTRO) já têm vídeos suficientes.

---

## Passo a passo

### 0. Python 3.11 (uma vez por computador)

O treino precisa do Python 3.10–3.12; o `python` deste PC é o 3.13. Os `.bat`
agora usam sozinhos o ambiente `computer\.venv` quando ele existe. Para
criá-lo (o `uv` já está instalado neste PC):

```powershell
cd D:\Estudo\Faculdade\Github\VisuAll\computer
uv venv --seed --python 3.11 .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Demora (o TensorFlow do modelo de corpo tem ~600 MB). Sem o `uv`: instale o
Python 3.11 do python.org e troque a segunda linha por
`py -3.11 -m venv .venv`.

### 1. Gravar

`computer\treino\Gravar.bat` → **TAB** troca o modo, **N/P** a letra,
**ESPAÇO** grava, **R** apaga a última. Siga as tabelas acima.

Vídeos e fotos que já estão no celular:

```powershell
cd D:\Estudo\Faculdade\Github\VisuAll\computer
.venv\Scripts\python.exe treino\importar.py "PASTA\COM\SUBPASTAS\POR\LETRA"
.venv\Scripts\python.exe treino\importar.py "PASTA\DE\UMA\LETRA" --rotulo K
```

### 2. Treinar as letras com movimento (H J K X Z + NADA)

Duplo-clique **não** serve aqui, porque são duas opções. No PowerShell:

```powershell
cd D:\Estudo\Faculdade\Github\VisuAll\computer
.\treino\Treinar.bat --tipo dinamico --limpar-individuais
```

- `--tipo dinamico`: mexe só no modelo das letras com movimento.
- `--limpar-individuais`: apaga os reforços antigos de H, J, K e X, que têm
  precedência sobre o modelo geral e são justamente os que respondem H para
  tudo. Uma cópia deles fica em `treino\modelos_anteriores\`.

No fim, confira:
1. a linha `validado: entrada 'landmarks_input' [None, 420] ...`;
2. a tabela "Nota em N vídeos/gravações que o treino NÃO viu": cada letra com
   *recall* de pelo menos 0,85, e a linha **NADA** também;
3. o `labels.txt` novo tem `H J K NADA X Z`.

### 3. Reforçar as letras paradas C, D e V

Duplo-clique em `computer\treino\Reforcar.bat` e digite `C,D,V`.

Ele gera modelos novos só para essas três, sem tocar nas outras letras.
Depois meça (passo 5). Hoje C e V estão em
`mobile\app\src\main\assets\letras_estaticas\reforcos_restritos.txt`: o app
só consulta o modelo deles quando o modelo geral já disse C, U ou V. Se o V
reto ainda não sair, **tire C e V desse arquivo** (deixe só o `U`) e meça de
novo: assim os modelos novos de C e V passam a ser consultados primeiro, como
já é com A, D, S e T.

### 4. Treinar PESSOA e SURDO

Duplo-clique em `computer\treino\TreinarCorpo.bat`. Ele usa os vídeos de todos
os seis sinais e guarda uma cópia do modelo anterior.

Para a nota honesta (separada por vídeo):

```powershell
.venv\Scripts\python.exe treino\diagnostico\extrai_cache.py
.venv\Scripts\python.exe treino\diagnostico\avalia.py
```

### 5. Medir antes de instalar

```powershell
.venv\Scripts\python.exe treino\diagnostico\simula_dinamicas.py
.venv\Scripts\python.exe treino\diagnostico\simula_estaticas.py C D V L O U
```

`simula_dinamicas.py`, com os modelos e portões de hoje, dá:

```
total  33/95    33/95
maos dos gestos de corpo   7.9 por minuto
trocas entre letras paradas   7 de 300 (2%)
```

Depois do retreino o total tem que subir e as duas linhas de baixo têm que
ficar perto de zero. Os vídeos usados no treino entram nessa conta, então o
acerto dela sai otimista; o que vale de verdade é a tabela do passo 2 e o
celular.

`simula_estaticas.py` mostra, para cada letra e distância, quantas fotos o app
acerta com a mão como gravada e com a outra mão, e o que ele responde no
lugar. Para C, D e V: a linha de "braço esticado" (altura ~0,2) tem que
acertar quase tudo, e as letras vizinhas (L, O, U) não podem virar C, D ou V.

### 6. Instalar e testar no celular

Android Studio → abrir a pasta `mobile` → **Run**. Teste:

- cada letra com problema 10 vezes, perto e de braço esticado, com as duas
  mãos, câmera frontal e traseira;
- 20 trocas entre letras paradas (A→B, D→L, C→O, V→U...): quantas viraram
  letra com movimento? Tem que ser zero ou quase;
- uma letra parada segurada por 5 s: ela tem que entrar na frase. Se letra
  parada passar a falhar, suba `LIMIAR_MOVIMENTO_COM_NADA` no
  `LibrasAnalyzer.kt` (nenhum vídeo atual mede isso);
- PESSOA e SURDO com a outra mão aparecendo.

Anote também o `fps=` que o app escreve no logcat (filtro `LibrasAnalyzer`,
linha `modo=ALFABETO fps=...`): os portões foram medidos a 15 quadros por
segundo.

### Se piorar

`computer\treino\RestaurarModelo.bat` devolve o modelo anterior (letras ou
corpo). Os modelos também estão no git: `git checkout -- mobile/app/src/main/assets`
volta tudo para o último commit.

### Ao commitar

Os `.onnx` e `.tflite` vão pelo Git LFS (já configurado no repo). Entram no
commit: `mobile/app/src/main/assets/letras_dinamicas/` (o `geral/` novo e as
pastas H, J, K, X apagadas), `letras_estaticas/C`, `D`, `V` (e o
`reforcos_restritos.txt`, se mudou) e `gestos/geral/`. Os vídeos e fotos
(`computer/data`) ficam fora do git.

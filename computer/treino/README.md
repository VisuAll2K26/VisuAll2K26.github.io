# Treino do VisuAll

Aqui você **ensina o app**: grava sinais com a webcam do computador, treina, e
o modelo novo já cai dentro do app. Tudo é **duplo-clique**.

| Quero... | Abra |
|---|---|
| ensinar uma **palavra nova** ao app | `1 - Adicionar palavra nova.bat` |
| que o app **acerte melhor** palavras que ele já conhece | `2 - Retreinar palavras.bat` |
| que o app **acerte melhor** letras | `3 - Retreinar letras.bat` |
| corrigir uma letra com movimento (H J K X Z) que **sai errada no celular** | `4 - Coletar letra com movimento pelo app.bat` |
| **voltar** ao modelo de antes do último treino | `Desfazer ultimo treino.bat` |

Os três primeiros funcionam igual: **abre a câmera → você grava → fecha a
câmera → responde `S` → ele treina.**

---

## Passo a passo

### 1. Abra o `.bat`

Na **primeira vez** em um computador ele prepara o Python sozinho: cria
`computer\.venv` e baixa as bibliotecas (uns 600 MB, alguns minutos). Das
outras vezes a câmera abre na hora.

### 2. Grave

A janela da câmera mostra **o que gravar** em cima (a letra ou a palavra) e
**as teclas** embaixo.

| Tecla | O que faz |
|---|---|
| **ESPAÇO** | grava: 3 segundos para se posicionar, depois **3 segundos gravando** (letra parada: 18 fotos nesses 3 segundos) |
| **R** | **regrava**: apaga a última gravação desta letra/palavra e grava de novo |
| **X** | **apaga** a última gravação desta letra/palavra (de novo: apaga a anterior) |
| **N** / **→** | próxima letra/palavra |
| **P** / **←** | anterior |
| **TAB** | **palavra nova**: abre o campo para digitar o nome (só nas palavras) |
| **ESC** | durante a contagem/gravação, cancela aquela gravação |
| **Q** | fecha a câmera |

**Foto ou vídeo?** O gravador escolhe sozinho:

| O que está gravando | Salva | Por quê |
|---|---|---|
| **Letra parada** (A, B, C, D...) | **18 fotos** nos 3 segundos | o treino dela é foto a foto. Enquanto tira as fotos, **mude um pouco o ângulo e a distância da mão** (sem desfazer a letra): cada foto ensina uma variação. As 18 contam como **uma** gravação. |
| **Letra com movimento** (H J K X Z) e **NADA** | vídeo de 3 s | o treino precisa do movimento |
| **Palavra** | vídeo de 3 s | idem |

Cada gravação vai sozinha para a pasta certa, com o nome da letra/palavra:
`gravacoes\letras\H\`, `gravacoes\palavras\OBRIGADO\`... Não precisa criar
pasta nem mover arquivo.

**Palavra nova:** o `1 - Adicionar palavra nova.bat` já abre pedindo o nome.
Digite (letras, números e espaço; **sem acento**, porque a janela não desenha
acento) e tecle **ENTER**. A pasta com esse nome é criada e a palavra aparece
no app **exatamente como foi escrita**. Se o nome já existir, as gravações
novas somam às dela.

### 3. Feche a câmera e treine

Tecle **Q**. O `.bat` pergunta *"Treinar agora, com TUDO que já foi
gravado?"*: responda **S**.

Não quer treinar agora? Responda **N**: as gravações ficam guardadas. Para
treinar depois, abra o mesmo `.bat`, feche a câmera com **Q** e responda **S**.

O treino mostra no fim **a nota em gravações que ele não viu**: quanto de
cada letra/palavra ele acerta em gravações que ficaram de fora do treino
justamente para isso. É o número que mais se parece com o celular.

### 4. Instale no celular

O treino escreve o modelo direto dentro do app
(`mobile\app\src\main\assets\`). Abra a pasta `mobile` no **Android Studio**
e clique em **Run**, com o celular no cabo.

Teste do jeito que vai ser usado: perto e de braço esticado, com as duas mãos,
em lugares diferentes. Roteiro completo: [`../VALIDACAO.md`](../VALIDACAO.md).

- **Ficou pior?** Abra `Desfazer ultimo treino.bat`, escolha a cópia de antes
  e rode o app de novo.
- **Ficou melhor?** Faça commit e push (passo 5).

### 5. Mande para o GitHub

Assim os outros computadores treinam **a partir daqui**, com as suas
gravações somadas às deles:

```powershell
git add computer/treino/pontos mobile/app/src/main/assets
git commit -m "Retrain letters with new recordings"
git push
```

Os vídeos **não** vão (são pesados e mostram o rosto de quem gravou). Vai o
**banco de pontos**, explicado logo abaixo.

---

## Como o treino "soma" em vez de começar do zero

Os vídeos ficam só no computador que gravou. Se o treino dependesse deles,
treinar em outro computador faria o app **esquecer** tudo que foi gravado nos
outros.

Por isso, na hora de treinar, cada gravação nova é lida **uma vez** e os
pontos que importam (as posições dos dedos e do corpo, quadro a quadro) vão
para um arquivo pequeno, que vai para o git:

```text
gravacoes\letras\H\20261023_141500.mp4      só neste computador
        │  lido uma vez pelo MediaPipe
        ▼
pontos\letras\H\20261023_141500.npz         no git (poucos KB)
```

**Todo treino usa o banco inteiro**: tudo que qualquer pessoa já gravou, em
qualquer computador, mais o que você acabou de gravar. O treino nunca apaga
nada do banco. Treinar duas vezes com o mesmo banco dá o mesmo modelo.

Duas proteções, para nunca piorar o app sem perceber:

- **Nada é esquecido.** Se o banco não tiver alguma palavra ou letra que o
  app conhece, o treino **para** e diz o que falta, sem mexer no app.
- **Sempre dá para voltar.** Antes de mudar um modelo, o treino guarda uma
  cópia do anterior em `modelos_anteriores\` (é o que o `Desfazer` usa).

### Letra com movimento que erra no celular: `4 - Coletar...`

A webcam e o app não veem a mão do mesmo jeito (câmera do celular, mais rápido,
mais tremido). Medido no celular: as janelas que o app entrega ao modelo ficam a
distância **3 a 6** das gravações da webcam, contra 0,8 entre duas gravações da
própria webcam, e o modelo respondia o Z como X com 100% de certeza. Treinar com
mais webcam não resolve; treinar com **o que o app entrega** resolve (tentativas
que o treino nunca viu passaram a sair certas).

1. Celular no cabo, **depuração USB** ligada, app instalado pelo Android Studio
   (build de depuração) e aberto no modo **alfabeto**.
2. Abra o `4 - Coletar letra com movimento pelo app.bat`, digite a letra, faça o
   movimento no app por uns 30 s e tecle **ENTER**. As janelas vão para
   `pontos\letras\<LETRA>\app_*.npz` (no git).
3. Faça o mesmo com as letras que erram e com **NADA** (mexer a mão sem fazer
   letra).
4. Rode o `3 - Retreinar letras.bat`. As janelas do app entram no treino ao lado
   das gravações da webcam.

O app só guarda as janelas enquanto o computador pede (cria o arquivo
`coletando` dentro da pasta do app, via `adb`), e só em build de depuração.

### O que cada treino faz

**Palavras** (`1` e `2`): refaz o modelo de palavras com todas as gravações.
Palavra nova não exige mudar nada no código do app: ele lê a lista de
palavras do próprio modelo. A palavra **NEUTRO** ("parado, sem sinal") é
especial: precisa existir (é como o modelo sabe que **não** há sinal) e o app
nunca a escreve na frase.

**Gravar o NEUTRO:** no `2 - Retreinar palavras.bat` aperte **N** até chegar
nele, ou aperte **0** em qualquer um dos dois `.bat` de palavras (no `1` isso
vale depois de dar nome a uma palavra, ou digite `NEUTRO` no campo do nome). A
tela mostra **o que fazer em cada gravação** e troca sozinha a cada uma: duas
mãos paradas à vista, só a direita, só a esquerda, mãos mexendo sem sinal... É a
variedade que importa; grave **uns 30**, sempre com os ombros dentro da tela.

**A outra mão não pode ser pista.** No banco, ter as duas mãos na tela virou
sinal de COMPUTADOR/CONVERSAR (94% e 58% dos quadros) e uma mão só virou sinal
de PESSOA/SURDO (29% e 12%), e o app errava assim que a pessoa fazia PESSOA com
a outra mão à vista. O treino agora detecta sozinho as palavras de uma mão e
treina também com a mão de um NEUTRO no lugar da que faltava, e o NEUTRO ganha
cópias com uma mão só. Medido em gravações que o treino não viu, com a outra
mão à vista: PESSOA **48% → 92%**, SURDO **11% → 99%**, NEUTRO com uma mão
**20% → 100%**. Mesmo assim, grave suas palavras com as duas mãos de vez em
quando: dado real vale mais que a cópia.

**Letras** (`3`):

- **Com movimento (H J K X Z):** refaz o modelo delas com todas as
  gravações, mais uma classe **NADA**, que é "a mão se mexeu, mas não fez
  letra". Ela é o que impede o app de inventar letra quando você troca de letra
  ou levanta a mão.
- **Paradas (A B C D...):** o modelo geral delas sabe 21 letras, e o banco
  ainda não tem gravação de todas. Por isso cada letra parada gravada ganha
  um **reforço** próprio ("isto é um D?"), que o app consulta antes do geral,
  e as outras letras não mudam. O geral só é refeito quando o banco tiver
  todas as 21.
- **Regras que protegem as outras letras.** O reforço aprende "isto é um D?"
  vendo como "não" as outras letras gravadas, o NADA, **os quadros das letras
  com movimento e as mãos das palavras**. Depois o treino mede do jeito que o
  app decide (acima de 0,97) e **só instala** o reforço que dispara em pelo menos
  metade das próprias fotos e em no máximo 1% do que **não** é a letra. Se
  reprovar, a linha diz o motivo e fica o modelo que já estava. Antes dessa
  regra, um reforço do F com 6 gravações passou por cima de tudo e virou H, K, X,
  Z, M, N e U em "F".
- **Reforço "congelado".** As letras listadas em `treino\reforcos_congelados.txt`
  (hoje o **U**) não são refeitas pelo retreino: funcionam no celular do jeito
  que estão. Para refazer uma, apague a linha dela.
- **Letra nova entra "restrita".** Um reforço de uma letra que o app ainda não
  tinha só ajuda a decidir dentro do grupo (`reforcos_restritos.txt`) e nunca
  passa por cima do modelo geral. Quando testar no celular e quiser dar
  prioridade, apague a letra desse arquivo.
- **Grave também as letras que ainda não estão no banco** (B, E, G, I, L, M, N,
  O, P, Q, R, W, Y): cada reforço só aprende a **não** disparar nelas se elas
  estiverem no banco, e é isso que fecha o caminho para refazer o modelo geral.

---

## Quanto gravar

Conte **gravações**, não fotos. E **varie**: é a variação que ensina, não a
repetição.

- **Duas pessoas ou mais**, se der. É o que mais ajuda.
- **As duas mãos**, metade com cada.
- **Três distâncias**: perto (a mão ocupando ~1/3 da altura da tela), braço
  esticado e um passo atrás.
- Luz e fundo diferentes, de frente e um pouco de lado.

| O quê | Mínimo | Bom |
|---|---|---|
| Palavra nova | 5 | **20 a 30** |
| Letra com movimento | 15 | **25 a 35** |
| Letra parada | 5 | **15** |
| NADA | 10 | **20** |

**NADA** (no `3`, depois do Z): faça **com a mão à vista** exatamente o que
faz o app inventar letra: trocar de uma letra parada para outra (A→B, D→L,
C→O, V→U), levantar a mão antes de começar e baixar depois, gesticular,
coçar a cabeça. Só não pode fazer H, J, K, X nem Z.

**Letra parada que confunde com outra** (o D virando L, por exemplo): grave
também **a outra** algumas vezes. Ela vira o exemplo de "não" do reforço.

---

## Onde o retreino parou (outubro de 2026)

O código está pronto e testado; **faltam gravações**. Os números abaixo
foram medidos com os scripts de [`diagnostico/`](diagnostico/), que passam as
gravações pelo mesmo caminho que o app faz.

| Problema no app | Causa medida | O que gravar |
|---|---|---|
| Letras com movimento saem sozinhas (ao trocar de letra, ao começar o sinal) | O modelo antigo não tinha como dizer "não é letra" | **20 NADA** |
| H sai fácil, **K não sai** (vira H) | O reforço antigo do H respondia H para 64% das janelas de K | **H e K até ~35 cada** (hoje 15 e 20) |
| **D** só sai de perto | As 18 fotos de D são **uma** gravação, de perto; de longe vira L | **D: 15**, e **L: 5** |
| **C** e **V** (só inclinando a mão) | Não há nenhuma gravação delas no banco | **C e V: 15 cada** (V com a mão reta); **O, U, R, W: 5 cada** |
| **PESSOA / SURDO** erram com as duas mãos na tela | Ter as duas mãos na tela virou pista de COMPUTADOR/CONVERSAR (ver acima) | Corrigido por cópias automáticas; ainda vale gravar **+25 de cada** com a outra mão parada **na tela** |
| **NEUTRO** fraco | Poucas gravações, quase todas com as duas mãos | **~30**, seguindo a dica da tela (tecla **0**) |

O que o retreino das letras já mostrou com as gravações de hoje (medido em
vídeos que o treino não viu, no caminho do app): letras com movimento certas
**de 28 para 83 em 95**, trocas entre letras paradas que viravam letra **de
96 para 0 em 300**. O app já entende a classe NADA e ajusta os limiares
sozinho. Falta gravar o que está na tabela e rodar o `3`.

Depois de instalar, confira no celular uma letra parada **segurada por 5
segundos**: nenhuma gravação mede isso. Se letra parada passar a falhar com o
modelo novo, suba `LIMIAR_MOVIMENTO_COM_NADA` em `LibrasAnalyzer.kt` (ver
`CHANGELOG.md`).

---

## Começar em outro computador

1. Instale o **[Git](https://git-scm.com/)** e o **[Git LFS](https://git-lfs.com/)**
   (os modelos do app são guardados pelo LFS) e rode `git lfs install` uma vez.
2. Clone e baixe os modelos:
   ```powershell
   git clone https://github.com/VisuAll2K26/VisuAll2K26.github.io.git VisuAll
   cd VisuAll
   git lfs pull
   ```
3. Instale o **[Python 3.11](https://www.python.org/downloads/release/python-3119/)**
   (marque *Add python.exe to PATH*). O `.bat` cria o resto sozinho.
4. Para instalar no celular: **[Android Studio](https://developer.android.com/studio)**.

Pronto: o banco de pontos veio junto no clone, então o primeiro treino já
parte de tudo que foi gravado até hoje. Os vídeos antigos não precisam vir.

---

## Deu errado?

| Sintoma | O que fazer |
|---|---|
| "precisa do Python 3.11" | Instale o Python 3.11 (link acima) e abra o `.bat` de novo. |
| A câmera não abre | Feche Zoom, Teams, OBS ou outro programa usando a câmera. |
| "PAREI, nada foi alterado no app" | Leia a linha de baixo: falta gravação de alguma palavra/letra, ou a palavra nova tem menos de 5. |
| "nada detectado em N gravações" | A mão (ou o tronco, nas palavras) não apareceu. Apague com **X** e regrave. |
| "NÃO instalado: dispara em N% do que NÃO é X" | O reforço dessa letra roubaria outras letras. Fica o modelo que já estava. Grave mais variação da letra (distância, ângulo, duas mãos) e as letras que faltam no banco. |
| Treinei, mas o app não mudou | Rodou o app de novo pelo Android Studio? O treino terminou com `validado`? |
| Gravei errado e já fechei a câmera | Apague o vídeo em `gravacoes\...` **e** o `.npz` de mesmo nome em `pontos\...`, se existir. |
| `model.tflite`/`model.onnx` com poucos bytes | O Git LFS não baixou os modelos: rode `git lfs pull`. |

---

## O que tem nesta pasta

| Pasta / arquivo | O que é | Vai pro git? |
|---|---|---|
| `1 -`, `2 -`, `3 -`, `Desfazer` `.bat` | Os únicos que você abre. | sim |
| `gravacoes\` | Os vídeos e fotos gravados, por letra/palavra. Criada sozinha. | **não** |
| `pontos\` | O banco de pontos: o que o treino usa de cada gravação. | **sim** |
| `modelos_anteriores\` | Cópia de cada modelo antes de um treino (para o `Desfazer`). | não |
| [`codigo\`](codigo/) | Os scripts Python. Não precisa abrir. | sim |
| [`diagnostico\`](diagnostico/) | Scripts que **medem** o treino e o app (acerto honesto, limiares). | sim |
| `tests\` | Testes automáticos do treino (rodam no GitHub a cada push). | sim |

Dentro de `codigo\`:

| Arquivo | O que faz |
|---|---|
| `gravar.py` | A janela da câmera. |
| `pontos.py` | Lê as gravações novas para o banco de pontos. |
| `treinar_palavras.py` | Treina e instala o modelo de palavras (`gestos/geral/model.tflite`). |
| `treinar_letras.py` | Treina e instala os modelos de letras (`letras_*/…/model.onnx`). |
| `comum.py` | Onde fica cada pasta e quais letras/palavras o app conhece. |
| `backup.py`, `restaurar.py` | A cópia antes do treino e o `Desfazer`. |
| `importar.py` | Traz vídeos/fotos gravados no celular para `gravacoes\` (abaixo). |
| `preparar.bat`, `treinar.bat` | Usados pelos `.bat` de cima: preparam o Python e perguntam se é para treinar. |

### Gravou pelo celular?

Ponha os arquivos numa pasta com **uma subpasta por letra/palavra** (o nome
da subpasta manda; nome que não é letra vira palavra) e, dentro de
`computer`:

```powershell
.venv\Scripts\python treino\codigo\importar.py "D:\DCIM\VisuAll"
```

Depois abra o `.bat` correspondente, feche a câmera com **Q** e responda **S**.

### Pela linha de comando

Dentro de `computer`, com o ambiente que o `.bat` criou:

```powershell
.venv\Scripts\python treino\codigo\gravar.py letras          # ou palavras / palavra-nova
.venv\Scripts\python treino\codigo\treinar_letras.py --so movimento
.venv\Scripts\python treino\codigo\treinar_letras.py --so paradas --letras C,D,V
.venv\Scripts\python treino\codigo\treinar_palavras.py
.venv\Scripts\python treino\codigo\pontos.py --reler         # lê de novo todo vídeo deste PC
```

### Por dentro (para quem for mexer no código)

O app espera os modelos num formato exato, e o treino confere o arquivo
gerado antes de dar por concluído (a linha `validado`):

| Modelo | Entrada | Saída | Onde o app lê |
|---|---|---|---|
| letras | `landmarks_input`, `[1, 42]` (parada) ou `[1, 420]` (movimento) | `[rótulo, probabilidades]` (`zipmap=False`) | `LetraEngine.kt` |
| palavras | `[1, 30, 225]`: 30 quadros × 75 pontos × (x, y, z) | `[1, n_palavras]` | `BodyGestureEngine.kt` |

As contas que preparam os pontos existem **duas vezes**, no Python e no
Kotlin (`LibrasMath.kt`), e têm que dar o mesmo número: senão o modelo
aprende num formato e é usado em outro, sem erro nenhum, só errando mais.
`computer/tests/fixtures/landmark_contract.json` prende os dois lados, e o
GitHub confere a cada push.

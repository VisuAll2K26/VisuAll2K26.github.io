# Formato dos modelos que o app lê

Este arquivo descreve **o que o app espera** de cada modelo. Para **treinar**,
use os `.bat` de [`README.md`](README.md): eles já geram tudo neste formato e
validam o resultado antes de escrever no app. O treino acontece só aqui, no
computador; o app não treina nada.

Os modelos ficam em `mobile/app/src/main/assets/`.

## Letras paradas (`letras_estaticas/`)

- Uma mão, **42** números por amostra (21 pontos x, y), normalizados como em
  `LibrasMath.normalizeLandmarks` (a conta gêmea está em `codigo/pontos.py`).
- `geral/model.onnx` + `geral/labels.txt`: um modelo multiclasse.
- `<LETRA>/model.onnx`: **reforço** individual ("isto é um D?"), consultado
  antes do geral. As letras em `reforcos_restritos.txt` só decidem dentro do
  próprio grupo e nunca passam por cima do geral.
- ONNX: entrada `landmarks_input` `[1, 42]` float32; saída `[1]` = probabilidades
  (zipmap desligado); os modelos individuais têm 2 saídas ("não", "sim").

## Letras com movimento (`letras_dinamicas/`)

- Janela de **10 quadros** x 42 = **420** números.
- `geral/model.onnx` + `geral/labels.txt` (H J K X Z e a classe **NADA**, "a mão
  se mexeu mas não é letra"). Com `NADA` no `labels.txt` o app ajusta sozinho
  os limiares (`AjusteDinamico`).
- ONNX: entrada `landmarks_input` `[1, 420]` float32; saída `[1]` = probabilidades.

## Palavras (`gestos/geral/`)

- `model.tflite` (BiLSTM, com `SELECT_TF_OPS`) + `labels.txt`.
- Entrada `[1, 30, 225]`: 30 quadros x 75 pontos (33 do corpo + 21 da mão
  esquerda + 21 da direita) x (x, y, z), normalizados pelos ombros
  (`LibrasMath.normalizeBodyFrame`).
- Saída `[1, n_palavras]`, na ordem do `labels.txt`. **NEUTRO** ("parado, sem
  sinal") precisa existir e nunca vira texto na frase.
- Palavra nova não exige mudar código: o app lê a lista do próprio modelo.

## Conferir antes de instalar

O treino já roda `valida()` em cada arquivo gerado (nome da entrada, formato,
probabilidades somando 1). Depois:

1. Abra a pasta `mobile` no Android Studio e dê **Run**.
2. Teste cada letra/palavra em tempo real e anote o que confunde com o quê, o
   que só funciona num ângulo e o que aparece com a mão parada.
3. Se uma letra ficar fraca, **grave mais exemplos dela** antes de mexer em
   limiares no código.

Os testes automáticos que prendem a matemática do app à do treino são
`LandmarkContractTest` (app) e `treino/tests/test_landmark_contract.py`.

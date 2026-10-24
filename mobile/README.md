# 📱 App VisuAll (Android)

O aplicativo que reconhece Libras. É uma câmera com um **modo Libras**: aponte
para quem está sinalizando e a tradução aparece escrita na tela, e falada se
você quiser. Funciona offline: os modelos vão dentro do APK.

- **Android 8.0 ou mais recente** (minSdk 26)
- Kotlin, CameraX, MediaPipe Tasks (mão, corpo e rosto), ONNX Runtime
  (letras) e TensorFlow Lite (sinais de corpo)

---

## Compilar e instalar

### Pelo Android Studio (o jeito fácil)

1. **File → Open** e escolha a pasta **`mobile`** (não a raiz do repositório).
2. Espere o Gradle sincronizar. Na primeira vez demora bastante.
3. Ligue o celular no cabo com a **depuração USB** ativada.
4. Clique em **▶ Run**.

### Pelo terminal

O terminal precisa saber onde está o Java. O que vem com o Android Studio
serve:

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
cd mobile
.\gradlew.bat assembleDebug      # gera o APK
.\gradlew.bat testDebugUnitTest  # roda os testes
```

O APK sai em `app\build\outputs\apk\debug\app-debug.apk`.

> Na primeira vez, abra a pasta no Android Studio pelo menos uma vez: é ele que
> cria o `local.properties`, o arquivo que diz onde está o Android SDK. Ele não
> vai no git, e sem ele o build para com *"SDK location not found"*.

### Sem compilar nada

O CI compila a cada mudança na `main` e publica o APK em
**[visuall2k26.github.io/baixar](https://visuall2k26.github.io/baixar/)**.

### Uma assinatura só para todo mundo

O APK é assinado com `app/visuall-debug.keystore`, que está no repositório.
Assim, o APK do site, o do CI e o que você compila no seu PC têm a mesma
assinatura, e **um instala por cima do outro sem perder o histórico**. É uma
chave de testes (senha `android`), não de loja.

---

## Onde fica cada coisa

```text
mobile/
├── app/
│   ├── build.gradle                 versão, dependências, assinatura
│   ├── visuall-debug.keystore       a chave compartilhada (veja acima)
│   └── src/
│       ├── main/
│       │   ├── assets/              os MODELOS (vêm de computer/treino/)
│       │   ├── java/com/visuall/app/
│       │   │   ├── camera/          a câmera comum
│       │   │   ├── libras/          o reconhecimento de Libras (o coração do app)
│       │   │   ├── oculos/          a conexão com a câmera dos óculos
│       │   │   └── ui/              a tela principal e o que é desenhado por cima
│       │   └── res/                 telas, textos, ícones
│       └── test/                    testes que rodam no PC, sem celular
├── tools/                           atalhos de desenvolvimento (emulador)
```

### `libras/`, o reconhecimento

| Arquivo | O que faz |
|---|---|
| `LibrasFragment` | A tela do modo Libras: câmera, frase, botões, histórico. |
| `LibrasAnalyzer` | O maestro: recebe cada quadro da câmera, roda o MediaPipe e decide qual motor usar. Todas as **constantes de calibração** ficam no começo dele. |
| `LetraEngine` | Reconhece **letras**, paradas e com movimento, com os modelos ONNX. |
| `BodyGestureEngine` | Reconhece **sinais de corpo** com o modelo TFLite, de forma contínua: dá para emendar um sinal no outro. |
| `FaceMarkerEngine`, `BrowGestureDetector` | Leem o rosto: a sobrancelha levantada vira pergunta. |
| `LetterDecision`, `LetterCommitGate`, `MovementGate`, `ClearGestureGate` | As regras de "isto é uma letra?", "já posso escrever?" e "as **duas** mãos abertas e paradas limpam a frase" (uma mão só não limpa: o C passava no teste). Separadas para poderem ser testadas. |
| `SentenceBuilder`, `SentenceTranslator`, `PhraseOutput` | Montam a frase, fazem a concordância e falam. |
| `ConversationHistoryStore`, `HistoryBottomSheet` | O histórico das conversas. |
| `LibrasMath` | As contas de normalização. **Precisam bater com as do treino em Python**: os testes de contrato garantem isso. |

### `assets/`, os modelos

| Pasta | O que tem |
|---|---|
| `letras_estaticas/geral/` | O modelo das letras paradas (`model.onnx` + `labels.txt`). |
| `letras_dinamicas/geral/` | O modelo das letras com movimento. |
| `letras_estaticas/<LETRA>/`, `letras_dinamicas/<LETRA>/` | Os **reforços** de uma letra só, que o app consulta junto do geral. |
| `gestos/geral/` | O modelo dos sinais de corpo (`model.tflite`). |
| `*_landmarker.task` | Os detectores do MediaPipe (mão, corpo, rosto). |

Os modelos são gerados pelo treino em `computer/treino/` e gravados **direto
aqui**. Por isso, depois de treinar, é só recompilar. Os arquivos pesados
ficam no **Git LFS**: se um modelo aparecer com ~130 bytes, rode `git lfs pull`.

---

## Testes

```powershell
.\gradlew.bat testDebugUnitTest
```

Cerca de 230 testes que rodam no PC, sem celular. Os mais importantes:

- **Contrato com o treino** (`LandmarkContractTest`): confere que a
  matemática do app dá exatamente o mesmo número que a do Python. Se o treino
  e o app divergirem, o modelo erra sem dar erro, e este teste é o que pega.
- **Regras de decisão** (`LetterDecisionTest`, `LetterCommitGateTest`...):
  cada portão de "escrever ou não" com casos reais que já deram problema.

O CI roda os mesmos testes a cada push.

---

## Deu ruim?

| Problema | O que fazer |
|---|---|
| *"SDK location not found"* | Abra a pasta `mobile` no Android Studio uma vez. |
| *"JAVA_HOME is not set"* | Aponte para o Java do Android Studio (veja "Pelo terminal"). |
| O modo Corpo avisa que o modelo não carregou | O modelo veio como ponteiro do LFS. Rode `git lfs pull` e recompile. |
| *"App não instalado"* ao atualizar | O app instalado foi assinado com outra chave. Desinstale uma vez; daí em diante atualiza por cima. |
| Treinei e o app não mudou | Faltou recompilar. O modelo vai dentro do APK. |
| Reconhecimento ruim | Luz, enquadramento e distância contam muito. Para melhorar uma letra ou um sinal, grave mais exemplos dele: [computer/treino/README.md](../computer/treino/README.md). |

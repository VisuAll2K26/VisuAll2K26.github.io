# ⚙️ Automações (GitHub Actions)

Rodam sozinhas no GitHub a cada push. O resultado aparece na aba
**[Actions](https://github.com/VisuAll2K26/VisuAll2K26.github.io/actions)**:
verde deu certo, vermelho quebrou algo.

| Arquivo | Quando roda | O que faz |
|---|---|---|
| [`android-build.yml`](android-build.yml) | Push ou PR que mexe em `mobile/` | Compila o app e roda os testes. Na `main`, ainda **publica o APK** na release `app`, que é o arquivo do botão de download do site. |
| [`python-training.yml`](python-training.yml) | Push ou PR que mexe em `computer/` ou nos modelos | Instala o ambiente de treino do zero, confere que o MediaPipe abre, roda os testes e confere o **contrato** entre o Python e o app. |
| [`pages.yml`](pages.yml) | Push na `main` que mexe em `site/` | Publica o site em [visuall2k26.github.io](https://visuall2k26.github.io/). |
| [`limpar-artefatos.yml`](limpar-artefatos.yml) | Toda segunda de manhã | Apaga APKs antigos guardados pelo build, para a cota de armazenamento não encher. |

Todos também podem ser rodados na mão: aba **Actions** → escolha o workflow →
**Run workflow**.

## Ficou vermelho?

Abra a execução, clique no passo vermelho e leia as últimas linhas.

| Workflow | Causa mais comum |
|---|---|
| Android Build | Erro de compilação ou teste quebrado. Rode `.\gradlew.bat testDebugUnitTest` em `mobile/` para ver no PC. |
| Python Training, passo "Contract fixtures" | A matemática do treino mudou sem o app acompanhar. Veja [computer/tests/README.md](../../computer/tests/README.md). |
| Publicar site | Quase sempre passageiro. Rode de novo pelo **Run workflow**. |

<div align="center">

<img src="site/images/logo-completa.jpg" alt="VisuAll" width="180">

# VisuAll

**Libras em tempo real, na câmera que você já tem.**

A câmera vê o sinal, o celular entende e a frase aparece escrita na tela.
Tudo roda no próprio aparelho: sem nuvem e sem internet.

[![Site](https://img.shields.io/badge/site-visuall2k26.github.io-ffd34d?style=flat-square)](https://visuall2k26.github.io/)
[![Baixar APK](https://img.shields.io/badge/baixar-Android-3ddc84?style=flat-square&logo=android&logoColor=white)](https://visuall2k26.github.io/baixar/)
[![Vídeo](https://img.shields.io/badge/vídeo-YouTube-ff0000?style=flat-square&logo=youtube&logoColor=white)](https://www.youtube.com/watch?v=OTPf8B4C49Y)
<br>
[![Android Build](https://github.com/VisuAll2K26/VisuAll2K26.github.io/actions/workflows/android-build.yml/badge.svg)](https://github.com/VisuAll2K26/VisuAll2K26.github.io/actions/workflows/android-build.yml)
[![Python Training](https://github.com/VisuAll2K26/VisuAll2K26.github.io/actions/workflows/python-training.yml/badge.svg)](https://github.com/VisuAll2K26/VisuAll2K26.github.io/actions/workflows/python-training.yml)

</div>

> **Os óculos são os olhos. O celular é o cérebro. O fone é a voz.**
> Quem ouve conversa olhando para a pessoa, e não para uma tela.

---

## O que ele faz

| Modo | O que reconhece |
|---|---|
| **Alfabeto** | As letras de Libras, paradas (A, B, C...) e com movimento (H, J, K, X, Z), formando palavras letra por letra. |
| **Corpo** | Sinais de palavra inteira (AJUDAR, COMPUTADOR, CONVERSAR, PESSOA, SURDO e as que forem ensinadas), em sequência, sem precisar pausar entre eles. A frase sai com concordância. |
| **Óculos** | A mesma coisa, mas com a câmera presa na armação dos óculos, mandando a imagem para o celular por Wi-Fi. |

## Como funciona

```text
câmera  ──►  MediaPipe            ──►  modelo            ──►  frase na tela
(celular     (pontos da mão,           (que letra ou          (e voz, se
 ou óculos)   do corpo e do rosto)      que sinal é)           quiser)
```

Os modelos nascem no PC (`computer/`), a partir de vídeos gravados pela
equipe, e vão **embutidos** no app (`mobile/`). Depois de instalado, o celular
não precisa de PC nem de internet.

---

## O que tem em cada pasta

| Pasta | O que é | Guia |
|---|---|---|
| 📱 [`mobile/`](mobile/) | O **aplicativo Android**. Reconhece, escreve e fala. | [mobile/README.md](mobile/README.md) |
| 💻 [`computer/`](computer/) | O **lado PC**: gravar vídeos, treinar os modelos e o reconhecedor de referência em Python. | [computer/README.md](computer/README.md) |
| 👓 [`oculos/`](oculos/) | A **câmera dos óculos** (ESP32-S3-CAM) e uma imitação dela para desenvolver sem a placa. | [oculos/README.md](oculos/README.md) |
| 🌐 [`site/`](site/) | O **site** do projeto, publicado em [visuall2k26.github.io](https://visuall2k26.github.io/). | [site/README.md](site/README.md) |
| ⚙️ [`.github/`](.github/) | As **automações**: compilar o app, publicar o APK e o site, testar o treino. | [.github/workflows/README.md](.github/workflows/README.md) |

Na raiz também ficam o [`CHANGELOG.md`](CHANGELOG.md), que é o diário das
**constantes de calibração** do reconhecimento (cada limiar, o valor atual e
por que ele é esse), e a [`LICENSE`](LICENSE) (MIT).

---

## Por onde começar

<details>
<summary><b>Quero só usar o app</b></summary>

<br>

Baixe o APK mais recente em **[visuall2k26.github.io/baixar](https://visuall2k26.github.io/baixar/)**
e instale no celular (Android 8 ou mais recente). Ele é atualizado
automaticamente a cada mudança no app.

</details>

<details>
<summary><b>Quero compilar o app</b></summary>

<br>

Abra a pasta `mobile` no **Android Studio**, espere o Gradle sincronizar e
clique em **Run**. Pelo terminal:

```powershell
cd mobile
.\gradlew.bat assembleDebug
```

Passo a passo: [mobile/README.md](mobile/README.md).

</details>

<details>
<summary><b>Quero ensinar letras ou sinais novos</b></summary>

<br>

Tudo é **duplo-clique** em `computer\treino\`:

| `.bat` | Para quê |
|---|---|
| `1 - Adicionar palavra nova` | ensinar uma palavra que o app ainda não conhece |
| `2 - Retreinar palavras` | o app acertar melhor as palavras que já conhece |
| `3 - Retreinar letras` | o app acertar melhor as letras |
| `4 - Coletar letra com movimento pelo app` | uma letra com movimento (H J K X Z) sai errada **no celular** |

Abre a câmera, você grava (ESPAÇO), fecha (Q), responde **S** e ele treina.
O modelo novo já cai dentro do app: é só rodar de novo pelo Android Studio.
O treino **soma** as gravações novas a tudo que já foi gravado, em qualquer
computador, então nada é esquecido.

Passo a passo: [computer/treino/README.md](computer/treino/README.md).

</details>

<details>
<summary><b>Quero mexer nos óculos</b></summary>

<br>

Dá para fazer quase tudo **sem a placa**: o mock roda no PC com a webcam e
fala o mesmo protocolo.

```powershell
python oculos\mock\mock.py
```

Do zero, escrito para quem nunca mexeu com isso: [oculos/README.md](oculos/README.md).

</details>

<details>
<summary><b>Quero mexer no site</b></summary>

<br>

É HTML, CSS e JavaScript puro, sem build. Edite em `site/`, envie para a
`main` e ele se publica sozinho em menos de um minuto.

Detalhes: [site/README.md](site/README.md).

</details>

---

## Continuar o trabalho em outro computador

Tudo que é preciso para continuar está no repositório, **menos os vídeos
gravados**, que ficam só no PC de quem gravou. Eles não fazem falta: o treino
usa o **banco de pontos** (`computer/treino/pontos/`), que vem no clone.

1. Instale o [Git](https://git-scm.com/), o [Git LFS](https://git-lfs.com/)
   (os modelos do app vão por ele), o
   [Python 3.11](https://www.python.org/downloads/release/python-3119/) e o
   [Android Studio](https://developer.android.com/studio).
2. Clone e baixe os modelos:
   ```powershell
   git lfs install
   git clone https://github.com/VisuAll2K26/VisuAll2K26.github.io.git VisuAll
   cd VisuAll
   git lfs pull
   ```
3. Para gravar e treinar, abra um dos `.bat` de `computer\treino\` (na
   primeira vez ele prepara o Python sozinho). Para o app, abra a pasta
   `mobile` no Android Studio e clique em **Run**.
4. Treinou e ficou bom? Commit e push de `computer/treino/pontos` e de
   `mobile/app/src/main/assets`, para o próximo computador partir daí.

O que estava sendo feito e o que falta gravar:
[computer/treino/README.md → Onde o retreino parou](computer/treino/README.md#onde-o-retreino-parou-outubro-de-2026).
Por que cada limiar do app tem o valor que tem: [CHANGELOG.md](CHANGELOG.md).

---

## Toda a documentação

| Assunto | Onde |
|---|---|
| Compilar e entender o app | [mobile/README.md](mobile/README.md) |
| Formato dos modelos que o app lê | [mobile/TREINAMENTO_MODELOS.md](mobile/TREINAMENTO_MODELOS.md) |
| Gravar e treinar letras e palavras | [computer/treino/README.md](computer/treino/README.md) |
| Onde o retreino parou e o que falta gravar | [computer/treino/README.md](computer/treino/README.md#onde-o-retreino-parou-outubro-de-2026) |
| Testar no celular de verdade | [computer/VALIDACAO.md](computer/VALIDACAO.md) |
| Scripts de medição do treino | [computer/treino/diagnostico/README.md](computer/treino/diagnostico/README.md) |
| Óculos, do zero | [oculos/README.md](oculos/README.md) |
| Firmware da placa | [oculos/firmware/README.md](oculos/firmware/README.md) |
| Avaliações do site | [site/avaliacao/README.md](site/avaliacao/README.md) |
| Por que cada limiar tem o valor que tem | [CHANGELOG.md](CHANGELOG.md) |

---

## Equipe

Estudantes de **Engenharia de Software da FIAP**, no **Challenge 2026 com a JOVI**.

| | |
|---|---|
| **João Victor Pereira Gimenes** | [LinkedIn](https://www.linkedin.com/in/jo%C3%A3o-victor-pereira-gimenes-191615374/) |
| **Juan Duarte Moura** | [LinkedIn](https://www.linkedin.com/in/juan-duarte-moura/) |
| **Julio Cesar da Silva Cocco** | [LinkedIn](https://www.linkedin.com/in/julio-cesar-da-silva-cocco-085400338/) |
| **Rafael Boletini de Oliveira** | [LinkedIn](https://www.linkedin.com/in/rafael-boletini-de-oliveira-24b782275/) |
| **Victor Rossi Sales Zanandré** | [LinkedIn](https://www.linkedin.com/in/victor-zanandre/) |

Contato: [visuall2k26@gmail.com](mailto:visuall2k26@gmail.com) ·
[Instagram](https://www.instagram.com/visuall2k26) ·
[YouTube](https://www.youtube.com/@VisuAll2K26) ·
[TikTok](https://www.tiktok.com/@visuall2k26)

<sub>Este repositório se chama <code>VisuAll2K26.github.io</code> porque é esse
nome que deixa o site no endereço curto. Ele guarda o projeto inteiro, não só
o site.</sub>

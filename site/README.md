# 🌐 Site do VisuAll

A página do projeto: **[visuall2k26.github.io](https://visuall2k26.github.io/)**.

HTML, CSS e JavaScript puros: **sem build, sem framework, sem dependência**.
Abra o arquivo no navegador e ele funciona.

---

## Mexer no site

1. Edite os arquivos desta pasta.
2. Para ver no PC antes de enviar, sirva a pasta e abra no navegador:
   ```powershell
   cd site
   python -m http.server 8000
   ```
   Depois acesse http://localhost:8000.
3. Ao mexer num `.css` ou `.js`, **aumente o `?v=` dele** em `html/index.html`
   (por exemplo, `body.css?v=25` vira `?v=26`). Sem isso, quem já visitou o
   site continua vendo a versão antiga, guardada no navegador.
4. Envie para a `main`. Em menos de um minuto ele está no ar, pelo
   [`pages.yml`](../.github/workflows/pages.yml).

---

## Onde fica cada coisa

```text
site/
├── index.html          porta de entrada: só redireciona para html/index.html
├── html/index.html     A PÁGINA (todas as seções estão aqui)
├── baixar/             a página para onde o QR code aponta
├── CSS/                os estilos (ordem de carga abaixo)
├── js/                 as interações (todas opcionais)
├── images/             logo, fotos da equipe, capa do vídeo, QR code
├── fonts/              a fonte Inter, hospedada aqui mesmo
└── avaliacao/          o script da planilha das avaliações
```

### CSS

Carregados nesta ordem pelo `html/index.html`:

| Arquivo | O que estiliza |
|---|---|
| `_global.css` | As **variáveis**: cores, tamanhos de letra, espaçamentos. Mude uma cor aqui e ela muda no site todo. |
| `reset.css` | Zera os estilos padrão do navegador. |
| `header.css` | O cabeçalho e o menu. |
| `body.css` | As seções da página, uma a uma. |
| `app.css` | O celular de mentira da seção "Explore o app". |
| `footer.css` | O rodapé. |

### JavaScript

**Nenhum é obrigatório.** Sem JavaScript, o site continua navegável e completo.

| Arquivo | O que faz |
|---|---|
| `explorador.js` | O simulador do app: os botões do celular de mentira funcionam e explicam cada tela. |
| `constelacao.js` | Os triângulos que desenham o olho da logo e os títulos que surgem palavra por palavra. |
| `carrossel.js` | O leque com as fotos da equipe. |
| `video.js` | Só carrega o player do YouTube quando a pessoa aperta o play. |
| `versao-apk.js` | Mostra a data e o tamanho do APK ao lado do botão de baixar. |
| `avaliacao.js` | O formulário "Avalie o VisuAll" e as avaliações aprovadas. |

---

## O download do app

O botão **Baixar para Android** e o QR code entregam sempre o APK mais novo:

- O link do APK **nunca muda**: o CI troca o arquivo a cada mudança no app
  (release `app`, ver [`android-build.yml`](../.github/workflows/android-build.yml)).
- O QR code (`images/qr-baixar.svg`) aponta para **`/baixar/`**, uma página
  nossa, e não direto para o arquivo. Se o app mudar de lugar um dia (Play
  Store, por exemplo), só a página muda e todo QR já impresso continua valendo.

## As avaliações

O formulário grava numa planilha Google da equipe, e o site só mostra as
avaliações que alguém da equipe aprovou. Configuração e aprovação:
[avaliacao/README.md](avaliacao/README.md).

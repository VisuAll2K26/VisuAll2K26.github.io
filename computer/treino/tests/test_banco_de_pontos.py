"""Testes do caminho gravacao -> banco de pontos -> amostras de treino.

O que precisa continuar valendo:
  - cada gravacao vira UM arquivo no banco, e gravacao nova so acrescenta;
  - as contas que montam as amostras sao as do app (NaN = sem mao, trecho
    fecha quando a mao some, janelas em 3 taxas de quadros);
  - o gravador cria a pasta com o nome digitado e apaga o que gravou;
  - o treino PARA, sem mexer no app, quando o banco nao tem tudo que o app
    ja conhece.

Rodam sem camera e sem os videos: o que precisa de MediaPipe usa um video
sintetico gerado aqui.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "treino" / "codigo"))

import comum  # noqa: E402
import pontos  # noqa: E402


class PastasTemporarias(unittest.TestCase):
    """Troca gravacoes/ e pontos/ por pastas temporarias durante o teste."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="visuall_banco_"))
        self._antes = (comum.GRAVACOES, comum.PONTOS)
        comum.GRAVACOES = self.tmp / "gravacoes"
        comum.PONTOS = self.tmp / "pontos"

    def tearDown(self):
        comum.GRAVACOES, comum.PONTOS = self._antes
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestNomeDePalavra(unittest.TestCase):

    def test_maiusculo_sem_acento(self):
        self.assertEqual(comum.nome_de_palavra("coração"), "CORACAO")

    def test_espacos_e_pontuacao_viram_um_espaco(self):
        self.assertEqual(comum.nome_de_palavra("  bom   dia! "), "BOM DIA")

    def test_vazio(self):
        self.assertEqual(comum.nome_de_palavra("  ?! "), "")


class TestIdDaGravacao(unittest.TestCase):

    def test_rajada_de_fotos_e_uma_gravacao(self):
        self.assertEqual(pontos.id_da_gravacao(Path("20260822_161309_07.jpg")), "20260822_161309")

    def test_video_e_o_nome(self):
        self.assertEqual(pontos.id_da_gravacao(Path("pessoa_meu_01.mp4")), "pessoa_meu_01")

    def test_foto_solta_e_o_nome(self):
        self.assertEqual(pontos.id_da_gravacao(Path("foto.jpg")), "foto")

    def test_foto_de_celular_nao_e_rajada(self):
        # AAAAMMDD_HHMMSS: o horario nao e o numero da foto na rajada. Antes
        # todas as fotos de um dia viravam uma gravacao so.
        self.assertEqual(pontos.id_da_gravacao(Path("20261023_095931.jpg")), "20261023_095931")


def mao(dx=0.0):
    """Uma mao [21, 2] qualquer, deslocada em x."""
    base = np.linspace(0.3, 0.6, 42, dtype=np.float32).reshape(21, 2)
    base[:, 0] += dx
    return base


class TestAmostras(unittest.TestCase):

    def test_trecho_fecha_quando_a_mao_some(self):
        sem = np.full((21, 2), np.nan, dtype=np.float32)
        maos = np.array([mao(), mao(), sem, mao(), mao(), mao()])
        self.assertEqual([len(t) for t in pontos.trechos(maos)], [2, 3])

    def test_amostra_e_a_conta_do_app(self):
        amostra = pontos.amostras_paradas(np.array([mao()]))[0]
        esperado = pontos.normalize_landmarks(mao().tolist())
        np.testing.assert_allclose(amostra, esperado, atol=1e-6)
        self.assertEqual(amostra.shape, (42,))

    def test_janelas_em_tres_taxas(self):
        # 30 quadros seguidos: a 30/s (passo 1, pulo 3) cabem 7 janelas, a
        # 15/s (passo 2, pulo 1) 6, e a 10/s (passo 3, pulo 1) 1.
        trecho = [np.zeros(42, np.float32)] * 30
        janelas = pontos.janelas([trecho])
        self.assertEqual(len(janelas), 7 + 6 + 1)
        self.assertEqual(janelas[0].shape, (420,))

    def test_video_a_60_quadros_vira_as_mesmas_janelas(self):
        # O mesmo gesto gravado a 60/s tem o dobro de quadros; as janelas
        # tem que cobrir o mesmo tempo que a 30/s.
        a30 = [np.full(42, i, np.float32) for i in range(30)]
        a60 = [np.full(42, i / 2, np.float32) for i in range(60)]
        j30, j60 = pontos.janelas([a30], fps=30), pontos.janelas([a60], fps=60)
        self.assertEqual(len(j30), len(j60))
        np.testing.assert_allclose(j30[3], j60[3])

    def test_maos_do_corpo_corrigem_o_x(self):
        corpo = np.full((2, 75, 3), np.nan, dtype=np.float32)
        corpo[:, 33:54, :2] = mao()
        esquerda, direita = pontos.maos_do_corpo({"corpo": corpo, "aspecto": np.float32(0.5)})
        np.testing.assert_allclose(esquerda[0, :, 0], mao()[:, 0] * 0.5, atol=1e-6)
        self.assertTrue(np.isnan(direita).all())


class TestBanco(PastasTemporarias):

    def _video_sem_mao(self, caminho, quadros=12):
        import cv2

        caminho.parent.mkdir(parents=True, exist_ok=True)
        escritor = cv2.VideoWriter(str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
        for _ in range(quadros):
            escritor.write(np.full((240, 320, 3), 90, np.uint8))
        escritor.release()

    def test_gravacao_vira_um_arquivo_e_so_e_lida_uma_vez(self):
        self._video_sem_mao(comum.GRAVACOES / "letras" / "H" / "20261023_100000.mp4")
        self.assertEqual(pontos.atualiza("letras"), 1)
        arquivo = comum.PONTOS / "letras" / "H" / "20261023_100000.npz"
        self.assertTrue(arquivo.exists())
        self.assertEqual(pontos.atualiza("letras"), 0, "leu de novo o que ja estava no banco")

        rotulo, ident, dados = pontos.carrega("letras")[0]
        self.assertEqual((rotulo, ident, dados["tipo"]), ("H", "20261023_100000", "sequencia"))
        self.assertEqual(dados["maos"].shape, (12, 21, 2))
        self.assertTrue(np.isnan(dados["maos"]).all(), "video sem mao deveria dar so NaN")

    def test_gravacao_nova_nao_reescreve_as_antigas(self):
        self._video_sem_mao(comum.GRAVACOES / "letras" / "H" / "a.mp4")
        pontos.atualiza("letras")
        antigo = (comum.PONTOS / "letras" / "H" / "a.npz").stat().st_mtime_ns
        self._video_sem_mao(comum.GRAVACOES / "letras" / "H" / "b.mp4")
        self.assertEqual(pontos.atualiza("letras"), 1)
        self.assertEqual((comum.PONTOS / "letras" / "H" / "a.npz").stat().st_mtime_ns, antigo)

    def test_palavra_guarda_corpo_e_maos(self):
        self._video_sem_mao(comum.GRAVACOES / "palavras" / "BOM DIA" / "c.mp4")
        pontos.atualiza("palavras")
        rotulo, _, dados = pontos.carrega("palavras")[0]
        self.assertEqual((rotulo, dados["tipo"]), ("BOM DIA", "corpo"))
        self.assertEqual(dados["corpo"].shape, (12, 75, 3))


class TestGravador(PastasTemporarias):

    def setUp(self):
        super().setUp()
        import gravar
        self.gravar = gravar

    def _digita(self, gravador, texto):
        for c in texto:
            gravador.tecla(ord(c), 0.0)
        gravador.tecla(self.gravar.ENTER, 0.0)

    def test_nome_digitado_vira_pasta(self):
        g = self.gravar.Gravador("palavra-nova")
        self.assertEqual(g.estado, self.gravar.DIGITANDO)
        self._digita(g, "bom dia")
        self.assertEqual(g.rotulo, "BOM DIA")
        self.assertEqual(g.estado, self.gravar.PARADO)
        self.assertTrue((comum.GRAVACOES / "palavras" / "BOM DIA").is_dir())

    def test_esc_sem_palavra_fecha(self):
        g = self.gravar.Gravador("palavra-nova")
        self.assertFalse(g.tecla(self.gravar.ESC, 0.0))

    def test_x_apaga_a_ultima_desta_palavra(self):
        g = self.gravar.Gravador("palavra-nova")
        self._digita(g, "teste")
        quadro = np.zeros((48, 64, 3), np.uint8)
        g.tecla(self.gravar.ESPACO, 0.0)
        g.quadro(quadro, self.gravar.CONTAGEM_S)                         # comeca a gravar
        g.quadro(quadro, self.gravar.CONTAGEM_S + 1.0)
        g.quadro(quadro, self.gravar.CONTAGEM_S + self.gravar.GRAVACAO_S)  # salva
        videos = list((comum.GRAVACOES / "palavras" / "TESTE").glob("*.mp4"))
        self.assertEqual(len(videos), 1)
        g.tecla(ord("x"), 0.0)
        self.assertFalse(videos[0].exists())

    def test_letra_parada_vira_fotos_de_uma_gravacao(self):
        g = self.gravar.Gravador("letras")
        g.idx = g.itens.index("A")
        quadro = np.zeros((48, 64, 3), np.uint8)
        g.tecla(self.gravar.ESPACO, 0.0)
        inicio = self.gravar.CONTAGEM_S
        g.quadro(quadro, inicio)                                     # comeca a fotografar
        for i in range(1, 91):                                       # 30 quadros/s por 3 s
            g.quadro(quadro, inicio + i / 30)
        pasta = comum.GRAVACOES / "letras" / "A"
        fotos = list(pasta.glob("*.jpg"))
        self.assertEqual(len(fotos), self.gravar.FOTOS_POR_GRAVACAO)
        self.assertEqual(list(pasta.glob("*.mp4")), [])
        self.assertEqual(len({pontos.id_da_gravacao(f) for f in fotos}), 1)
        g.tecla(ord("x"), 0.0)
        self.assertEqual(list(pasta.iterdir()), [])

    def test_zero_pula_pro_neutro_e_o_roteiro_gira(self):
        g = self.gravar.Gravador("palavra-nova")
        self._digita(g, "bom dia")
        g.tecla(ord("0"), 0.0)
        self.assertEqual(g.rotulo, comum.NEUTRO)
        self.assertTrue((comum.GRAVACOES / "palavras" / comum.NEUTRO).is_dir())
        dicas = {self.gravar.dica("palavras", comum.NEUTRO, set(), i)
                 for i in range(len(self.gravar.NEUTRO_ROTEIRO))}
        self.assertEqual(len(dicas), len(self.gravar.NEUTRO_ROTEIRO))

    def test_letra_com_movimento_e_nada_continuam_video(self):
        g = self.gravar.Gravador("letras")
        for rotulo in [comum.NADA] + sorted(g.dinamicas)[:1]:
            g.idx = g.itens.index(rotulo)
            self.assertFalse(g.em_fotos(), rotulo)


class TestNaoEsquece(PastasTemporarias):

    def test_palavras_param_se_falta_palavra_do_app(self):
        import treinar_palavras
        app = set(comum.palavras_do_app())
        if not app:
            self.skipTest("labels.txt das palavras nao esta no checkout")
        gravacoes = {p: 20 for p in app}
        gravacoes.pop(sorted(app - {comum.NEUTRO})[0])
        self.assertFalse(treinar_palavras.confere_banco(gravacoes))
        self.assertTrue(treinar_palavras.confere_banco({p: 20 for p in app}))

    def test_palavras_param_sem_neutro_ou_com_poucas(self):
        import treinar_palavras
        app = {p: 20 for p in comum.palavras_do_app()} or {comum.NEUTRO: 20, "A": 20}
        sem_neutro = dict(app, **{"NOVA": 20})
        sem_neutro.pop(comum.NEUTRO)
        self.assertFalse(treinar_palavras.confere_banco(sem_neutro))
        self.assertFalse(treinar_palavras.confere_banco(dict(app, NOVA=2)))
        self.assertTrue(treinar_palavras.confere_banco(dict(app, NOVA=20)))

    def test_letras_sabem_o_que_falta(self):
        import treinar_letras
        atuais = set(comum.letras_dinamicas())
        self.assertEqual(treinar_letras.faltam_no_banco(comum.ASSETS_DINAMICAS, atuais), [])
        faltam = treinar_letras.faltam_no_banco(comum.ASSETS_DINAMICAS, atuais - {"K"})
        if comum.le_labels(comum.ASSETS_DINAMICAS / "geral" / "labels.txt"):
            self.assertEqual(faltam, ["K"])


class TestJanelasDoApp(PastasTemporarias):
    """Janelas coletadas pelo proprio app (coletar.py) entram no treino como
    gravacao daquela letra, sem passar pelo MediaPipe."""

    def _janelas(self, n=40):
        return np.random.RandomState(0).uniform(-1, 1, (n, 420)).astype(np.float32)

    def test_letra_com_movimento(self):
        import coletar
        import treinar_letras
        coletar.salva("Z", self._janelas())
        banco = treinar_letras.Banco()
        self.assertEqual(banco.gravacoes["Z"], 1)
        self.assertEqual(len(banco.Xm), 40 * treinar_letras.COPIAS_DO_APP)
        self.assertEqual(set(banco.ym), {"Z"})

    def test_nada_vira_exemplo_de_nada(self):
        import coletar
        import treinar_letras
        coletar.salva(comum.NADA, self._janelas(30))
        banco = treinar_letras.Banco()
        self.assertEqual(len(banco.Xn), 30 * treinar_letras.COPIAS_DO_APP)
        self.assertEqual(banco.Xm, [])

    def test_copias_mantem_a_forma_do_app(self):
        import treinar_letras
        janelas = self._janelas(5).reshape(5, 10, 21, 2)
        janelas[:, :, 0, :] = 0.0                       # o app entrega o pulso na origem
        copias = np.array(treinar_letras.copias_do_app(janelas.reshape(5, 420)))
        self.assertEqual(copias.shape, (5 * treinar_letras.COPIAS_DO_APP, 420))
        frames = copias.reshape(-1, 10, 21, 2)
        np.testing.assert_allclose(frames[:, :, 0, :], 0.0)              # pulso na origem
        self.assertLessEqual(float(np.abs(copias).max()), 1.0 + 1e-6)    # maior valor = 1

    def test_apara_tira_o_comeco_e_o_fim_das_letras_mas_nao_do_nada(self):
        import coletar
        tempos = np.arange(0, 6000, 100)
        janelas = np.zeros((len(tempos), 420), np.float32)
        self.assertEqual(len(coletar.apara(tempos, janelas, "Z")), 40)
        self.assertEqual(len(coletar.apara(tempos, janelas, comum.NADA)), 60)


class TestTransicoes(unittest.TestCase):

    def test_formato_e_reproduzivel(self):
        import treinar_letras
        fotos = np.array([np.array(pontos.normalize_landmarks(mao(dx).tolist()), np.float32)
                          for dx in (0.0, 0.0, 0.1, 0.1)])
        rotulos = np.array(["A", "A", "B", "B"])
        a = treinar_letras.transicoes_sinteticas(fotos, rotulos, quantidade=5)
        b = treinar_letras.transicoes_sinteticas(fotos, rotulos, quantidade=5)
        self.assertEqual(a.shape, (5, 420))
        np.testing.assert_array_equal(a, b)


if __name__ == "__main__":
    unittest.main()

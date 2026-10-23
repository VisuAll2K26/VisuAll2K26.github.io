package com.visuall.app.libras

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

// Fixa qual conjunto de portões vale pra cada modelo dinâmico.
//
// O risco que isto evita: instalar o app com o modelo antigo (sem NADA) e os
// portões afrouxados que só fazem sentido com NADA. O modelo antigo chama de
// letra qualquer mão se mexendo; sem o portão alto, H e K voltariam a sair em
// toda troca de letra parada.
class AjusteDinamicoTest {

    @Test
    fun `modelo sem NADA usa os portoes de sempre`() {
        val ajuste = AjusteDinamico.para(listOf("H", "J", "K", "X", "Z"))
        assertEquals(LibrasAnalyzer.LIMIAR_MOVIMENTO, ajuste.limiarMovimento, 0f)
        assertEquals(LibrasAnalyzer.CONSENSO_DINAMICO_JANELAS, ajuste.consensoJanelas)
        assertEquals(LibrasAnalyzer.CONSENSO_DINAMICO_MS, ajuste.consensoMs)
    }

    @Test
    fun `modelo com NADA usa os portoes medidos com ele`() {
        // A ordem do labels.txt sai do treino (ordem alfabética do LabelEncoder).
        val ajuste = AjusteDinamico.para(listOf("H", "J", "K", "NADA", "X", "Z"))
        assertEquals(LibrasAnalyzer.LIMIAR_MOVIMENTO_COM_NADA, ajuste.limiarMovimento, 0f)
        assertEquals(LibrasAnalyzer.CONSENSO_DINAMICO_JANELAS_COM_NADA, ajuste.consensoJanelas)
        assertEquals(LibrasAnalyzer.CONSENSO_DINAMICO_MS_COM_NADA, ajuste.consensoMs)
    }

    @Test
    fun `linha em branco no labels nao conta como NADA`() {
        val ajuste = AjusteDinamico.para(listOf("H", "J", "", "K", "X", "Z"))
        assertEquals(LibrasAnalyzer.LIMIAR_MOVIMENTO, ajuste.limiarMovimento, 0f)
    }

    @Test
    fun `os portoes com NADA nunca sao mais rigidos que os de sempre`() {
        // Se alguém subir um e esquecer o outro, o modelo novo ficaria mais
        // difícil de acertar que o antigo — o contrário do que foi medido.
        assertTrue(LibrasAnalyzer.LIMIAR_MOVIMENTO_COM_NADA <= LibrasAnalyzer.LIMIAR_MOVIMENTO)
        assertTrue(LibrasAnalyzer.CONSENSO_DINAMICO_JANELAS_COM_NADA <= LibrasAnalyzer.CONSENSO_DINAMICO_JANELAS)
        assertTrue(LibrasAnalyzer.CONSENSO_DINAMICO_MS_COM_NADA <= LibrasAnalyzer.CONSENSO_DINAMICO_MS)
    }
}

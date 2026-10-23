package com.visuall.app.libras

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

// Fixa a regra que impede uma janela solta de virar letra dinâmica.
//
// O sintoma em campo: letras com movimento saíam fácil demais. Bastava mover
// a mão por mais de MOVIMENTO_SUSTENTADO_MS (trocando de uma letra estática
// pra outra, por exemplo) e uma única janela que o modelo dinâmico achasse
// parecida com J ou Z era repetida no ENCERRANDO até passar pela
// estabilidade do LetterCommitGate.
class DynamicLetterConsensusTest {

    private val janelasMin = LibrasAnalyzer.CONSENSO_DINAMICO_JANELAS
    private val tempoMin = LibrasAnalyzer.CONSENSO_DINAMICO_MS

    private fun p(letra: String) = Prediction(letra, 0.99f, "dinamico")

    /** Registra [n] janelas de [letra] a cada [intervalo] ms; devolve a última saída. */
    private fun DynamicLetterConsensus.janelas(
        letra: String,
        n: Int,
        inicio: Long,
        intervalo: Long
    ): Prediction {
        var saida = p("-")
        repeat(n) { i -> saida = registrar(p(letra), inicio + i * intervalo) }
        return saida
    }

    @Test
    fun `uma janela sozinha nao vira letra`() {
        val consenso = DynamicLetterConsensus()
        assertEquals("-", consenso.registrar(p("J"), 1_000L).letra)
        assertNull(consenso.predicaoConfirmada)
    }

    @Test
    fun `janelas seguidas concordando pelo tempo minimo confirmam a letra`() {
        val consenso = DynamicLetterConsensus()
        val intervalo = tempoMin / (janelasMin - 1)
        val saida = consenso.janelas("Z", janelasMin, 1_000L, intervalo)
        assertEquals("Z", saida.letra)
        assertEquals("Z", consenso.predicaoConfirmada?.letra)
    }

    @Test
    fun `muitas janelas em pouco tempo nao bastam`() {
        // Aparelho rápido: janelas quase idênticas, uma colada na outra. A
        // contagem passa, mas é a mesma evidência repetida — o tempo segura.
        val consenso = DynamicLetterConsensus()
        val saida = consenso.janelas("J", janelasMin * 3, 1_000L, 5L)
        assertTrue(janelasMin * 3 * 5L < tempoMin)
        assertEquals("-", saida.letra)
    }

    @Test
    fun `pouco tempo com poucas janelas nao basta`() {
        // Aparelho lento: o tempo passa, mas só com janelas de menos.
        val consenso = DynamicLetterConsensus()
        val saida = consenso.janelas("J", janelasMin - 1, 1_000L, tempoMin)
        assertEquals("-", saida.letra)
    }

    @Test
    fun `janela sem letra quebra a sequencia`() {
        val consenso = DynamicLetterConsensus()
        val intervalo = tempoMin / (janelasMin - 1)
        consenso.janelas("J", janelasMin - 1, 1_000L, intervalo)
        consenso.registrar(p("-"), 1_000L + tempoMin)
        // Retomar J não soma com o que veio antes do "-".
        assertEquals("-", consenso.registrar(p("J"), 1_000L + tempoMin + 1).letra)
    }

    @Test
    fun `letras alternando nunca confirmam`() {
        // O retrato de mão se mexendo sem sinalizar: cada janela vira uma
        // letra diferente, nenhuma se sustenta.
        val consenso = DynamicLetterConsensus()
        var t = 1_000L
        repeat(30) { i ->
            val letra = if (i % 2 == 0) "J" else "Z"
            assertEquals("-", consenso.registrar(p(letra), t).letra)
            t += 50L
        }
        assertNull(consenso.predicaoConfirmada)
    }

    @Test
    fun `no fim do gesto vale a sequencia confirmada mais longa`() {
        // O fim do gesto, com a mão freando, é onde o modelo mais confunde.
        val consenso = DynamicLetterConsensus()
        val intervalo = tempoMin / (janelasMin - 1)
        consenso.janelas("J", janelasMin + 4, 1_000L, intervalo)
        consenso.janelas("H", janelasMin, 10_000L, intervalo)
        assertEquals("J", consenso.predicaoConfirmada?.letra)
    }

    @Test
    fun `reset esquece o gesto anterior`() {
        val consenso = DynamicLetterConsensus()
        val intervalo = tempoMin / (janelasMin - 1)
        consenso.janelas("Z", janelasMin, 1_000L, intervalo)
        consenso.reset()
        assertNull(consenso.predicaoConfirmada)
        assertEquals("-", consenso.registrar(p("Z"), 5_000L).letra)
    }
}

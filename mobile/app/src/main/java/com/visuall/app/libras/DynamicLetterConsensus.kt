package com.visuall.app.libras

// Decide se as janelas classificadas DURANTE um gesto concordam o bastante
// para a letra dinâmica valer.
//
// O furo que isto fecha: no ENCERRANDO do MovementGate o LetraEngine
// reclassificava a janela congelada — sempre a mesma — por
// MOVIMENTO_ENCERRAMENTO_MS. Uma janela só, que por acaso passasse de
// CONFIANCA_DINAMICA (o modelo dinâmico não tem classe "nenhuma", então
// qualquer mão se mexendo vira H/J/K/X/Z para ele), se repetia idêntica, e a
// estabilidade do LetterCommitGate passava por construção: a mesma entrada
// dá a mesma saída. Bastava mover a mão entre duas letras estáticas por mais
// de MOVIMENTO_SUSTENTADO_MS e um quadro de sorte no fim virava letra.
//
// Agora a letra só sai se várias janelas DIFERENTES, seguidas, apontarem pra
// ela por um tempo mínimo — o que é o normal num gesto real. Medido nos
// vídeos de computer/data (dataset_dynamic.npz, ~15 quadros/s): H, J e Z
// reais concordam por 8+ janelas seguidas na maioria das gravações, bem
// acima do exigido aqui.
//
// O instante entra como parâmetro, igual ao MovementGate e ao
// LetterCommitGate. Ver DynamicLetterConsensusTest.
internal class DynamicLetterConsensus(
    private val janelasMinimas: Int = LibrasAnalyzer.CONSENSO_DINAMICO_JANELAS,
    private val duracaoMinimaMs: Long = LibrasAnalyzer.CONSENSO_DINAMICO_MS
) {
    // Sequência atual de janelas iguais. "-" quebra a sequência: uma janela
    // em que o modelo não reconheceu nada não pode emendar dois acertos
    // soltos.
    private var letraAtual = "-"
    private var desde: Long? = null
    private var janelas = 0

    // A sequência confirmada mais longa do gesto — é ela que vale no
    // ENCERRANDO. A mais longa, não a última: o fim do gesto (mão freando)
    // é onde o modelo mais confunde as letras entre si.
    private var predicaoDoGesto: Prediction? = null
    private var janelasDoGesto = 0

    /**
     * Chamado uma vez por janela classificada durante o movimento sustentado.
     * Devolve a própria predição se a sequência atual já está confirmada;
     * senão, a mesma predição com letra "-".
     */
    fun registrar(predicao: Prediction, agora: Long): Prediction {
        val letra = predicao.letra
        if (letra == "-") {
            letraAtual = "-"
            desde = null
            janelas = 0
            return predicao
        }
        if (letra != letraAtual) {
            letraAtual = letra
            desde = agora
            janelas = 0
        }
        janelas++

        val inicio = desde ?: agora
        val confirmada = janelas >= janelasMinimas && (agora - inicio) >= duracaoMinimaMs
        if (!confirmada) return predicao.copy(letra = "-")
        if (janelas > janelasDoGesto) {
            predicaoDoGesto = predicao
            janelasDoGesto = janelas
        }
        return predicao
    }

    /** A predição que o gesto confirmou enquanto durou; null = nenhuma. */
    val predicaoConfirmada: Prediction? get() = predicaoDoGesto

    fun reset() {
        letraAtual = "-"
        desde = null
        janelas = 0
        predicaoDoGesto = null
        janelasDoGesto = 0
    }
}

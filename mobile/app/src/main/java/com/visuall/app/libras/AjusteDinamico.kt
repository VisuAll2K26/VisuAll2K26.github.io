package com.visuall.app.libras

// Os portões das letras com movimento dependem de qual modelo está no app.
//
// O modelo dinâmico antigo só conhece H, J, K, X e Z: qualquer mão se mexendo
// vira uma delas pra ele. Por isso o portão de movimento é alto e o consenso
// exige 3 janelas — é o app que precisa recusar o que não é letra.
//
// O modelo treinado com a classe NADA (exportar_onnx.py) recusa sozinho, e
// os mesmos portões altos passam a cortar só gesto de verdade. Ler o
// labels.txt deixa o app certo nos dois casos, sem ninguém lembrar de mudar
// constante depois de retreinar: com NADA no labels.txt vale o ajuste
// "COM_NADA" do LibrasAnalyzer; sem, o de sempre. Ver AjusteDinamicoTest.
internal data class AjusteDinamico(
    val limiarMovimento: Float,
    val consensoJanelas: Int,
    val consensoMs: Long
) {
    companion object {
        fun para(labelsDoModelo: List<String>): AjusteDinamico =
            if (labelsDoModelo.any { it.isNotBlank() && LetterDecision.normalizarSaida(it) == "-" }) {
                AjusteDinamico(
                    LibrasAnalyzer.LIMIAR_MOVIMENTO_COM_NADA,
                    LibrasAnalyzer.CONSENSO_DINAMICO_JANELAS_COM_NADA,
                    LibrasAnalyzer.CONSENSO_DINAMICO_MS_COM_NADA
                )
            } else {
                AjusteDinamico(
                    LibrasAnalyzer.LIMIAR_MOVIMENTO,
                    LibrasAnalyzer.CONSENSO_DINAMICO_JANELAS,
                    LibrasAnalyzer.CONSENSO_DINAMICO_MS
                )
            }
    }
}

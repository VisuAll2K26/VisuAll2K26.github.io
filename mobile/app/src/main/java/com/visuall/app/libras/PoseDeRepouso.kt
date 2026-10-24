package com.visuall.app.libras

import kotlin.math.sqrt

// "Terminei a letra" nao e "comecei outra".
//
// Depois de uma letra com movimento (Z, por exemplo) a mao fica parada na pose
// em que o gesto acabou, e o modelo das letras paradas passa a ler ESSA pose
// como letra: o Z terminava e, sem ninguem mexer a mao, um V entrava na frase.
// Mesma coisa quando a mao desce de uma limpeza e passa por um formato de C.
//
// A regra: depois de armada, nenhuma letra nova sai enquanto a mao continuar na
// pose de repouso. Ela solta quando a pose MUDA de verdade (a pessoa foi fazer
// outra letra), quando a mao sai do quadro, ou quando quem usa a desarma.
//
// O limite (LibrasAnalyzer.POSE_NOVA_DISTANCIA) vem do banco de pontos: a mao
// parada oscila ~0.1-0.2 entre quadros, e fotos de letras DIFERENTES ficam a
// 0.8 (5%) a 1.7 (mediana) uma da outra. Letras quase iguais (U e V) ficam a
// ~0.3 e nao soltam sozinhas: para escrever uma depois da outra, tire a mao do
// quadro entre as duas.
internal class PoseDeRepouso(
    private val distanciaNovaPose: Float = LibrasAnalyzer.POSE_NOVA_DISTANCIA
) {
    private var armada = false
    private var referencia: FloatArray? = null

    /** A proxima pose vista passa a ser a de repouso. */
    fun armar() {
        armada = true
        referencia = null
    }

    fun desarmar() {
        armada = false
        referencia = null
    }

    /** Verdadeiro enquanto a mao segue na pose de repouso (nenhuma letra pode sair). */
    fun travada(pose: FloatArray): Boolean {
        if (!armada) return false
        val ref = referencia
        if (ref == null) {
            referencia = pose.copyOf()
            return true
        }
        if (distancia(pose, ref) > distanciaNovaPose) {
            desarmar()
            return false
        }
        return true
    }

    private fun distancia(a: FloatArray, b: FloatArray): Float {
        var soma = 0f
        for (i in 0 until minOf(a.size, b.size)) {
            val d = a[i] - b[i]
            soma += d * d
        }
        return sqrt(soma)
    }
}

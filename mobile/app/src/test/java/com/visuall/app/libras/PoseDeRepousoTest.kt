package com.visuall.app.libras

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

// Depois de uma letra com movimento, a mao parada na pose em que o gesto acabou
// nao pode virar letra (o V que entrava depois do Z). So uma pose NOVA, ou a mao
// saindo do quadro, destrava.
class PoseDeRepousoTest {

    private fun pose(valor: Float) = FloatArray(42) { valor }

    @Test
    fun `sem armar nunca trava`() {
        val p = PoseDeRepouso(0.6f)
        assertFalse(p.travada(pose(0.2f)))
    }

    @Test
    fun `armada, a mao parada na mesma pose segue travada mesmo com tremor`() {
        val p = PoseDeRepouso(0.6f)
        p.armar()
        assertTrue(p.travada(pose(0.20f)))
        repeat(30) { i -> assertTrue(p.travada(pose(0.20f + (if (i % 2 == 0) 0.01f else -0.01f)))) }
    }

    @Test
    fun `armada, uma pose nova destrava e continua destravada`() {
        val p = PoseDeRepouso(0.6f)
        p.armar()
        assertTrue(p.travada(pose(0.2f)))
        assertFalse(p.travada(pose(0.9f)))     // outra letra
        assertFalse(p.travada(pose(0.2f)))     // e nao volta a travar sozinha
    }

    @Test
    fun `desarmar solta mesmo na mesma pose`() {
        val p = PoseDeRepouso(0.6f)
        p.armar()
        assertTrue(p.travada(pose(0.2f)))
        p.desarmar()                           // a mao saiu do quadro
        assertFalse(p.travada(pose(0.2f)))
    }

    @Test
    fun `armar de novo escolhe uma pose de repouso nova`() {
        val p = PoseDeRepouso(0.6f)
        p.armar()
        assertTrue(p.travada(pose(0.2f)))
        p.armar()
        assertTrue(p.travada(pose(0.9f)))      // a nova referencia e esta
        assertTrue(p.travada(pose(0.9f)))
    }
}

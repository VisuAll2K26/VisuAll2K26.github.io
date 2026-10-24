package com.visuall.app.libras

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.util.Log
import java.nio.FloatBuffer

// Reconhecimento de letra do alfabeto (MLP estático + dinâmico)
// pessoal — extraído do LibrasAnalyzer pra isolar esse conjunto de
// modelos/estado (sessões ONNX, janela deslizante) do resto do
// pipeline (corpo, marcador de rosto), que não têm nada a ver com isso.
internal class LetraEngine(
    context: Context,
    private val onFeedback: (mensagem: String, nivel: Int) -> Unit
) {
    private val ortEnv          = OrtEnvironment.getEnvironment()
    // Coleta de janelas pro treino (ver classificarDinamico). So funciona em
    // build de depuracao, onde o adb alcanca a pasta do app (run-as).
    private val diagArquivo = java.io.File(context.filesDir, "diag_dinamico.txt")
    private val coletaLigada = java.io.File(context.filesDir, "coletando")
    private val poseDeRepouso = PoseDeRepouso()

    private val sessionEstatico = ortEnv.createSession(
        context.assets.open("letras_estaticas/geral/model.onnx").readBytes()
    )
    private val sessionDinamico = ortEnv.createSession(
        context.assets.open("letras_dinamicas/geral/model.onnx").readBytes()
    )
    // Estes labels.txt são a ÚNICA fonte da verdade sobre quais letras
    // existem: a ordem deles é o que traduz "saída número 3" na letra certa,
    // e eles são regravados junto do modelo a cada treino. Qualquer outra
    // lista de letras no app tem que sair daqui (ver labelsAlfabeto), senão
    // uma some/entra no treino e a tela continua mostrando a lista velha.
    private val labelsEstatico  = context.assets.open("letras_estaticas/geral/labels.txt")
        .bufferedReader().readLines().filter { it.isNotBlank() }
    private val labelsDinamico  = context.assets.open("letras_dinamicas/geral/labels.txt")
        .bufferedReader().readLines().filter { it.isNotBlank() }
    // O modelo dinâmico pode ter, além das letras, a classe NADA: "a mão se
    // mexeu, mas não fez letra nenhuma" (ver treinar_letras.py). Ela continua
    // em labelsDinamico, porque a ordem dali é a ordem das saídas do modelo,
    // mas não é letra — fica fora de tudo que a tela mostra.
    private val letrasDinamicas = labelsDinamico.filter { LetterDecision.normalizarSaida(it) != "-" }

    // Alfabeto completo (estáticas + dinâmicas), em ordem alfabética, pra UI
    // de calibração percorrer.
    val labelsAlfabeto: List<String> = (labelsEstatico + letrasDinamicas).distinct().sorted()
    // Quais delas exigem movimento — usado pra instrução na tela ("segure" vs
    // "faça o movimento").
    val labelsDinamicasSet: Set<String> = letrasDinamicas.toSet()
    private val modelosEstaticosIndividuais = carregarModelosIndividuais(
        context, labelsEstatico, "letras_estaticas"
    )
    private val reforcosEstaticosRestritos: Set<String> = runCatching {
        context.assets.open("letras_estaticas/reforcos_restritos.txt")
            .bufferedReader().readLines()
            .map { it.trim().uppercase() }
            .filter { it.isNotBlank() }
            .toSet()
    }.getOrDefault(emptySet())
    private val modelosDinamicosIndividuais = carregarModelosIndividuais(
        context, letrasDinamicas, "letras_dinamicas"
    )
    private val reforcosDinamicosRestritos: Set<String> = runCatching {
        context.assets.open("letras_dinamicas/reforcos_restritos.txt")
            .bufferedReader().readLines()
            .map { it.trim().uppercase() }
            .filter { it.isNotBlank() }
            .toSet()
    }.getOrDefault(emptySet())

    private val bufferLm          = ArrayDeque<FloatArray>()
    private val bufferPontos      = ArrayDeque<FloatArray>()
    // Instante de cada quadro dos buffers acima, na mesma ordem: o movimento é
    // medido numa janela de tempo (MOVIMENTO_JANELA_MS), não de quadros.
    private val bufferTempos      = ArrayDeque<Long>()

    // Limiar de movimento e exigência do consenso, conforme o modelo dinâmico
    // tenha ou não a classe NADA — ver AjusteDinamico.
    private val ajuste = AjusteDinamico.para(labelsDinamico)

    // Só confiamos no modelo dinâmico depois de o movimento ser sustentado por
    // MOVIMENTO_SUSTENTADO_MS. A regra (e o histórico de por que ela é medida
    // em tempo e não em contagem de frames) está no MovementGate.
    private val movementGate = MovementGate(limiarMovimento = ajuste.limiarMovimento)

    // Só deixa a letra dinâmica sair se várias janelas seguidas do gesto
    // concordarem — ver DynamicLetterConsensus. É também quem guarda a letra
    // que vale durante o ENCERRANDO.
    private val consenso = DynamicLetterConsensus(ajuste.consensoJanelas, ajuste.consensoMs)
    // Houve classificação dinâmica desde o último PARADO.
    private var gestoEmCurso = false

    private data class ModeloIndividual(
        val label: String,
        val session: OrtSession
    )

    private companion object {
        // Modo da predição quando o modelo dinâmico respondeu NADA. Começa com
        // "dinamico" de propósito: o LetterCommitGate continua usando os
        // tempos das letras com movimento.
        const val MODO_NADA = "dinamico_nada"
    }

    private fun carregarModelosIndividuais(
        context: Context,
        labels: List<String>,
        basePath: String
    ): List<ModeloIndividual> {
        val carregados = labels.mapNotNull { label ->
            val safe = label.uppercase().filter { it.isLetterOrDigit() || it == '_' || it == '-' }
            carregarOpcional(context, "$basePath/$safe/model.onnx") { bytes ->
                ModeloIndividual(label = label, session = ortEnv.createSession(bytes))
            }
        }
        Log.i("LetraEngine", "Modelos individuais em $basePath: " +
            if (carregados.isEmpty()) "nenhum" else carregados.joinToString { it.label })
        return carregados
    }

    // Carrega um asset que pode legitimamente não existir. A diferença que
    // importa: NÃO existir é normal e silencioso; existir e falhar ao abrir é
    // erro e vai pro log. Antes os dois casos eram engolidos igualmente, então
    // um modelo corrompido ou em formato errado ficava indistinguível de um
    // modelo que nunca foi treinado.
    private fun <T> carregarOpcional(
        context: Context,
        asset: String,
        build: (ByteArray) -> T
    ): T? {
        val bytes = try {
            context.assets.open(asset).use { entrada -> entrada.readBytes() }
        } catch (_: java.io.FileNotFoundException) {
            return null
        } catch (error: Throwable) {
            Log.w("LetraEngine", "Não consegui ler o asset $asset", error)
            return null
        }
        return try {
            build(bytes)
        } catch (error: Throwable) {
            Log.e("LetraEngine", "Asset $asset existe mas não pôde ser carregado " +
                "(modelo corrompido ou em formato incompatível?)", error)
            null
        }
    }

    fun resetMovimentoSustentado() {
        movementGate.reset()
        consenso.reset()
        gestoEmCurso = false
    }

    fun limparBuffer() {
        poseDeRepouso.desarmar()
        esvaziarJanela()
        consenso.reset()
        gestoEmCurso = false
    }

    private fun esvaziarJanela() {
        bufferLm.clear()
        bufferPontos.clear()
        bufferTempos.clear()
    }

    // Pipeline completo de um frame com mão detectada: normaliza, alimenta a
    // atualiza a janela deslizante,
    // classifica (estático ou dinâmico) e emite o
    // feedback textual correspondente.
    fun process(pontos: List<Pair<Float, Float>>): Prediction {
        val agora = System.currentTimeMillis()
        val pontosCrus = pontosParaArray(pontos)
        val dados = LibrasMath.normalizeLandmarks(pontos)
        bufferPontos.addLast(pontosCrus)
        bufferLm.addLast(dados)
        bufferTempos.addLast(agora)
        while (bufferPontos.size > LibrasAnalyzer.JANELA_MLP + 5) bufferPontos.removeFirst()
        while (bufferLm.size > LibrasAnalyzer.JANELA_MLP + 5) bufferLm.removeFirst()
        while (bufferTempos.size > LibrasAnalyzer.JANELA_MLP + 5) bufferTempos.removeFirst()

        val movimento = calcularMovimento()
        val predicao = escolherClassificacao(dados, movimento, agora)
        emitirFeedback(predicao, movimento)
        return predicao
    }

    private fun emitirFeedback(prediction: Prediction, movimento: Float) {
        val mensagem = when {
            // Sinal firme nao tem texto: a moldura fica verde, e o chip mostra a
            // letra e a confianca. "SINAL ESTAVEL" repetia o que o verde ja diz,
            // e o balao dele cobria o chip da letra.
            prediction.letra != "-" && prediction.confianca >= 0.92f -> ""
            prediction.letra != "-" && prediction.confianca >= 0.82f -> "SEGURE MAIS FIRME"
            movimento > ajuste.limiarMovimento -> "MOVIMENTO ALTO"
            prediction.confianca >= 0.68f -> "QUASE: AJUSTE ANGULO"
            else -> "APROXIME A MAO"
        }
        val nivel = when {
            prediction.letra != "-" && prediction.confianca >= 0.90f -> LibrasAnalyzer.FEEDBACK_BOM
            prediction.confianca >= 0.72f -> LibrasAnalyzer.FEEDBACK_NEUTRO
            else -> LibrasAnalyzer.FEEDBACK_ALERTA
        }
        onFeedback(mensagem, nivel)
    }

    private fun pontosParaArray(pontos: List<Pair<Float, Float>>): FloatArray {
        val arr = FloatArray(pontos.size * 2)
        pontos.forEachIndexed { index, ponto ->
            arr[index * 2] = ponto.first
            arr[index * 2 + 1] = ponto.second
        }
        return arr
    }

    // Desvio dos pontos nos quadros dos últimos MOVIMENTO_JANELA_MS. Eram os
    // últimos 5 quadros, o que fazia a mesma mão "mexer" mais num celular
    // lento que num rápido — ver MOVIMENTO_JANELA_MS.
    private fun calcularMovimento(): Float {
        val quadros = LibrasMath.quadrosNaJanela(
            bufferTempos.toList(),
            LibrasAnalyzer.MOVIMENTO_JANELA_MS,
            LibrasAnalyzer.MOVIMENTO_QUADROS_MINIMOS
        )
        if (quadros == 0) return 0f
        return maxOf(calcularMovimentoForma(quadros), calcularMovimentoCru(quadros))
    }

    private fun calcularMovimentoForma(quadros: Int): Float {
        val recent = bufferLm.toList().takeLast(quadros)
        return LibrasMath.std(recent.map { it[2] }) + LibrasMath.std(recent.map { it[3] }) +
               LibrasMath.std(recent.map { it[16] }) + LibrasMath.std(recent.map { it[17] })
    }

    private fun calcularMovimentoCru(quadros: Int): Float {
        val recent = bufferPontos.toList().takeLast(quadros)
        val escalas = recent.mapNotNull { escalaDaMaoCrua(it).takeIf { escala -> escala > 0f } }
        if (escalas.isEmpty()) return 0f
        val escala = escalas.average().toFloat()
        // Movimento do pulso captura translação da mão inteira. As pontas dos
        // dedos cobrem gestos em que a mão fica quase no lugar, mas a ponta
        // desenha a trajetória. Isso só abre o portão dinâmico; o ONNX recebe
        // a mesma janela normalizada de antes.
        return maxOf(
            movimentoPontoCru(recent, 0, escala),
            movimentoPontoCru(recent, 8, escala),
            movimentoPontoCru(recent, 20, escala)
        )
    }

    private fun escalaDaMaoCrua(frame: FloatArray): Float {
        if (frame.size <= 19) return 0f
        val dx = frame[18] - frame[0]
        val dy = frame[19] - frame[1]
        return kotlin.math.sqrt(dx * dx + dy * dy)
            .takeIf { it > LibrasMath.ESCALA_MINIMA_MAO } ?: 0f
    }

    private fun movimentoPontoCru(frames: List<FloatArray>, ponto: Int, escala: Float): Float {
        val base = ponto * 2
        if (frames.any { it.size <= base + 1 } || escala <= 0f) return 0f
        return (LibrasMath.std(frames.map { it[base] }) +
            LibrasMath.std(frames.map { it[base + 1] })) / escala
    }

    private fun escolherClassificacao(dados: FloatArray, movimento: Float, agora: Long): Prediction {
        // A histerese de movimento (por que ela existe e como se comporta) vive
        // no MovementGate, que é testável porque recebe o instante.
        when (movementGate.avaliar(movimento, agora)) {
            EstadoMovimento.SUSTENTADO -> {
                if (bufferLm.size >= LibrasAnalyzer.JANELA_MLP &&
                    bufferPontos.size >= LibrasAnalyzer.JANELA_MLP) {
                    val janela = bufferLm.toList().takeLast(LibrasAnalyzer.JANELA_MLP)
                    val janelaCrua = bufferPontos.toList().takeLast(LibrasAnalyzer.JANELA_MLP)
                    gestoEmCurso = true
                    // Uma janela sozinha não basta: a letra só sai depois de
                    // várias janelas seguidas concordarem.
                    return consenso.registrar(classificarDinamico(janela, janelaCrua), agora)
                }
            }
            EstadoMovimento.ENCERRANDO -> {
                // O movimento acabou. Continuar lendo bufferLm aqui misturaria
                // a mão voltando ao repouso dentro da janela do gesto — que é
                // exatamente o que fazia a letra dinâmica se perder no fim do
                // movimento. Mantemos a letra que o gesto JÁ confirmou enquanto
                // durava, até ela estabilizar e entrar na frase. Antes isto
                // reclassificava a última janela, sempre a mesma, e uma janela
                // de sorte virava letra sem ninguém concordar com ela.
                if (gestoEmCurso) {
                    return consenso.predicaoConfirmada ?: Prediction("-", 0f, "dinamico")
                }
            }
            EstadoMovimento.PARADO -> {
                if (gestoEmCurso) {
                    gestoEmCurso = false
                    // Uma letra com movimento foi confirmada: a pose em que a
                    // mao parou nao pode virar uma letra parada (o Z acabava e
                    // um V entrava sozinho). Ver PoseDeRepouso.
                    val confirmada = consenso.predicaoConfirmada
                    if (confirmada != null && LetterDecision.normalizarSaida(confirmada.letra) != "-") {
                        poseDeRepouso.armar()
                    }
                    consenso.reset()
                    // O rabicho do gesto que acabou não pode virar o começo da
                    // janela do próximo: a janela recomeça vazia.
                    esvaziarJanela()
                }
            }
        }
        if (poseDeRepouso.travada(dados)) return Prediction("-", 0f, "pos_gesto")
        return classificarEstatico(dados)
    }

    // Uma letra do alfabeto é a MESMA forma com qualquer das duas mãos —
    // muda só o lado. Os modelos, porém, foram treinados a partir de gravações
    // de uma mão só e sem espelhamento de dados (não há aumento por flip no
    // pipeline de treino), então a mão oposta cai numa região do espaço de
    // features que eles nunca viram: era isso que fazia o "M" só sair com a
    // mão esquerda.
    //
    // A correção definitiva é retreinar com as amostras espelhadas — o que o
    // treinar_letras.py passou a fazer sozinho; os modelos treinados antes
    // disso continuam precisando deste remendo. Ele resolve na inferência: se
    // a orientação como veio não gerou
    // resposta, tentamos a espelhada. O espelho entra só quando o modelo já
    // disse "não sei", e ainda precisa passar pelos MESMOS portões de
    // confiança e margem — então não afrouxa nada, só cobre o lado que faltava.
    private fun comFallbackEspelhado(
        entrada: FloatArray,
        classificar: (FloatArray) -> Prediction
    ): Prediction {
        val direto = classificar(entrada)
        if (direto.letra != "-") return direto
        val espelhado = classificar(LibrasMath.mirrorLandmarks(entrada))
        return if (espelhado.letra != "-") espelhado else direto
    }

    private fun classificarEstatico(dados: FloatArray): Prediction =
        comFallbackEspelhado(dados, ::classificarEstaticoOrientado)

    private fun classificarEstaticoOrientado(dados: FloatArray): Prediction {
        // Modelos individuais antigos continuam com a precedência original.
        // Reforços esparsos (listados em reforcos_restritos.txt) entram apenas
        // depois do geral, para nunca ocultarem uma letra fora do seu grupo.
        val individuaisPrioritarios = modelosEstaticosIndividuais.filterNot {
            it.label in reforcosEstaticosRestritos
        }
        if (individuaisPrioritarios.isNotEmpty()) {
            val individual = classificarIndividual(
                entrada = dados,
                modelos = individuaisPrioritarios,
                features = LibrasAnalyzer.FEATURES_ESTATICO,
                confiancaMinima = LibrasAnalyzer.CONFIANCA_INDIVIDUAL,
                margemMinima = LibrasAnalyzer.MARGEM_ESTATICA_MINIMA,
                modo = "estatico_individual"
            )
            if (individual.letra != "-") return individual
        }

        val geral = LetterDecision.deProbabilidades(
            probs = rodarModelo(sessionEstatico, dados, LibrasAnalyzer.FEATURES_ESTATICO),
            labels = labelsEstatico,
            confiancaMinima = LibrasAnalyzer.CONFIANCA_MINIMA,
            margemMinima = LibrasAnalyzer.MARGEM_ESTATICA_MINIMA,
            modo = "estatico"
        )

        val modelosRestritos = modelosEstaticosIndividuais.filter {
            it.label in reforcosEstaticosRestritos
        }
        if (modelosRestritos.isEmpty()) return geral

        val reforco = classificarIndividual(
            entrada = dados,
            modelos = modelosRestritos,
            features = LibrasAnalyzer.FEATURES_ESTATICO,
            confiancaMinima = LibrasAnalyzer.CONFIANCA_INDIVIDUAL,
            margemMinima = LibrasAnalyzer.MARGEM_ESTATICA_MINIMA,
            modo = "estatico_individual_restrito"
        )
        return LetterDecision.combinarComReforcoRestrito(
            base = geral,
            reforco = reforco,
            labelsDoReforco = reforcosEstaticosRestritos,
            // U estava aparecendo para qualquer gesto. Agora ele precisa ser
            // confirmado pelos dois modelos e também não pode roubar C/V.
            labelsQueExigemConcordancia = setOf("U")
        )
    }

    // Roda uma sessão ONNX e devolve o vetor de probabilidades. O índice [1] da
    // saída é a lista de probabilidades porque o treino exporta com
    // zipmap=False (ver verificar_onnx_exportado em treinar_visuall.py, que
    // falha o treino se isso mudar).
    private fun rodarModelo(session: OrtSession, entrada: FloatArray, features: Int): FloatArray {
        val tensor = OnnxTensor.createTensor(
            ortEnv, FloatBuffer.wrap(entrada), longArrayOf(1, features.toLong()))
        val out = session.run(mapOf("landmarks_input" to tensor))
        @Suppress("UNCHECKED_CAST")
        val probs = (out[1].value as Array<FloatArray>)[0]
        tensor.close(); out.close()
        return probs
    }

    private fun classificarDinamico(
        janela: List<FloatArray>,
        janelaCrua: List<FloatArray>
    ): Prediction {
        val entrada = FloatArray(LibrasAnalyzer.FEATURES_DINAMICO)
        janela.forEachIndexed { i, frame ->
            frame.copyInto(entrada, i * LibrasAnalyzer.FEATURES_ESTATICO)
        }
        // mirrorLandmarks nega as posições pares, que na sequência concatenada
        // continuam sendo exatamente os x de cada quadro — espelhar os 420
        // valores de uma vez espelha a sequência inteira.
        val direto = DynamicLetterMotion.filtrar(
            classificarDinamicoOrientado(entrada),
            janelaCrua
        )
        // COLETA PARA O TREINO: so liga quando o computador cria o arquivo
        // "coletando" (computer/treino/codigo/coletar.py, via adb). Guarda a
        // janela exatamente como ela entrou no modelo, pra o treino aprender
        // com o que ESTE app entrega (camera, velocidade e tremor do celular),
        // que nao e igual ao das gravacoes da webcam.
        if (coletaLigada.exists()) runCatching {
            val p = rodarModelo(sessionDinamico, entrada, LibrasAnalyzer.FEATURES_DINAMICO)
            if (diagArquivo.length() < 3_000_000L) {
                diagArquivo.appendText(
                    "${System.currentTimeMillis()}|" +
                        labelsDinamico.zip(p.toList()).joinToString(" ") {
                            "${it.first}:${"%.2f".format(java.util.Locale.US, it.second)}"
                        } + "|${direto.letra}/${direto.modo}|" +
                        entrada.joinToString(",") { "%.4f".format(java.util.Locale.US, it) } + "\n"
                )
            }
        }
        if (direto.letra != "-") return direto
        // O modelo afirmou que não é letra. O espelho existe pra cobrir a mão
        // que o treino não viu, não pra dar uma segunda chance a um "não".
        if (direto.modo == MODO_NADA) return direto

        return DynamicLetterMotion.filtrar(
            classificarDinamicoOrientado(LibrasMath.mirrorLandmarks(entrada)),
            janelaCrua
        )
    }

    private fun classificarDinamicoOrientado(entrada: FloatArray): Prediction {
        // Mantém a precedência dos individuais antigos. Os reforços treinados
        // só com algumas letras não podem esconder J/Z nem qualquer decisão
        // do modelo geral fora do grupo H/K/X.
        val individuaisPrioritarios = modelosDinamicosIndividuais.filterNot {
            it.label in reforcosDinamicosRestritos
        }
        if (individuaisPrioritarios.isNotEmpty()) {
            val individual = classificarIndividual(
                entrada = entrada,
                modelos = individuaisPrioritarios,
                features = LibrasAnalyzer.FEATURES_DINAMICO,
                confiancaMinima = LibrasAnalyzer.CONFIANCA_INDIVIDUAL,
                margemMinima = LibrasAnalyzer.MARGEM_DINAMICA_MINIMA,
                modo = "dinamico_individual"
            )
            if (individual.letra != "-") return individual
        }

        val geral = classificarDinamicoComModelo(
            entrada = entrada,
            session = sessionDinamico,
            labels = labelsDinamico,
            modo = "dinamico"
        )
        // NADA com confiança é o modelo afirmando "isto não é letra". Nenhum
        // reforço passa por cima disso: os reforços nunca viram mão se mexendo
        // à toa, e era assim que o H saía pra qualquer movimento.
        if (geral.letra != "-" && LetterDecision.normalizarSaida(geral.letra) == "-") {
            return geral.copy(letra = "-", modo = MODO_NADA)
        }

        val modelosRestritos = modelosDinamicosIndividuais.filter {
            it.label in reforcosDinamicosRestritos
        }
        if (modelosRestritos.isEmpty()) return geral

        val reforco = classificarIndividual(
            entrada = entrada,
            modelos = modelosRestritos,
            features = LibrasAnalyzer.FEATURES_DINAMICO,
            confiancaMinima = LibrasAnalyzer.CONFIANCA_INDIVIDUAL,
            margemMinima = LibrasAnalyzer.MARGEM_DINAMICA_MINIMA,
            modo = "dinamico_individual_restrito",
            confiancaPorLabel = reforcosDinamicosRestritos.associateWith { label ->
                if (label == "X") LibrasAnalyzer.CONFIANCA_REFORCO_DINAMICO_X
                else LibrasAnalyzer.CONFIANCA_REFORCO_DINAMICO_HK
            }
        )
        return LetterDecision.combinarComReforcoRestrito(
            base = geral,
            reforco = reforco,
            labelsDoReforco = reforcosDinamicosRestritos,
            // O geral rejeita 153/199 janelas de H, 222/319 de K e todas as
            // de X. Os modelos dedicados passam a poder responder nesses
            // casos, ainda sujeitos à confiança por letra, margem, movimento
            // sustentado e estabilidade antes de entrar na frase.
            labelsPermitidosSemBase = setOf("H", "K", "X"),
            // O geral também confunde H com K e K com X. Dentro deste grupo,
            // só o reforço dedicado pode dar a palavra final.
            exigirReforcoParaGrupo = true
        )
    }

    private fun classificarDinamicoComModelo(
        entrada: FloatArray,
        session: OrtSession,
        labels: List<String>,
        modo: String
    ): Prediction = LetterDecision.deProbabilidades(
        probs = rodarModelo(session, entrada, LibrasAnalyzer.FEATURES_DINAMICO),
        labels = labels,
        confiancaMinima = LibrasAnalyzer.CONFIANCA_DINAMICA,
        margemMinima = LibrasAnalyzer.MARGEM_DINAMICA_MINIMA,
        modo = modo
    )

    private fun classificarIndividual(
        entrada: FloatArray,
        modelos: List<ModeloIndividual>,
        features: Int,
        confiancaMinima: Float,
        margemMinima: Float,
        modo: String,
        confiancaPorLabel: Map<String, Float> = emptyMap()
    ): Prediction {
        val pontuacoes = modelos.map { modelo ->
            val probs = rodarModelo(modelo.session, entrada, features)
            // Modelo binário: a saída [1] é "é esta letra". Alguns exports com
            // uma classe só devolvem um valor — aí ele é a própria resposta.
            val positivo = when {
                probs.size >= 2 -> probs[1]
                probs.size == 1 -> probs[0]
                else -> 0f
            }
            modelo.label to positivo
        }
        return LetterDecision.deModelosIndividuais(
            pontuacoes = pontuacoes,
            confiancaMinima = confiancaMinima,
            margemMinima = margemMinima,
            confiancaSemRival = LibrasAnalyzer.CONFIANCA_INDIVIDUAL_SEM_RIVAL,
            modo = modo,
            confiancaPorLabel = confiancaPorLabel
        )
    }

    fun close() {
        modelosEstaticosIndividuais.forEach { modelo ->
            runCatching { modelo.session.close() }
                .onFailure { Log.w("LetraEngine", "Falha ao fechar modelo individual ${modelo.label}", it) }
        }
        modelosDinamicosIndividuais.forEach { modelo ->
            runCatching { modelo.session.close() }
                .onFailure { Log.w("LetraEngine", "Falha ao fechar modelo individual ${modelo.label}", it) }
        }
        runCatching { sessionEstatico.close() }
            .onFailure { Log.w("LetraEngine", "Falha ao fechar modelo estatico", it) }
        runCatching { sessionDinamico.close() }
            .onFailure { Log.w("LetraEngine", "Falha ao fechar modelo dinamico", it) }
        // OrtEnvironment.getEnvironment() retorna um ambiente compartilhado.
        // Fechar aqui quebra a proxima criacao do LetraEngine quando a camera
        // e aberta de novo ou quando o CameraX recria o analyzer.
    }
}


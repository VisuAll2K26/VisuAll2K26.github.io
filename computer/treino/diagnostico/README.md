# Diagnóstico: medir antes de mudar

Scripts que respondem perguntas do tipo "por que o app erra isto?" com números,
em vez de palpite. Cada um mede uma coisa e imprime o resultado. **Nenhum
altera modelo ou app.**

Rode de dentro de `computer/`:

```powershell
python treino\diagnostico\<script>.py
```

Os de corpo leem `cache_corpo.npz`, que guarda os pontos de cada vídeo já
extraídos (o cache **não** vai para o git). Na primeira vez, ou depois de
gravar vídeos novos, gere o cache:

```powershell
python treino\diagnostico\extrai_cache.py
```

## Os scripts

### Avaliar um modelo

| Script | Pergunta |
|---|---|
| `avalia.py` | Qual o acerto **honesto** do modelo de corpo? Treino e teste separados por vídeo, nunca por pedaço do mesmo vídeo. |
| `avalia_reforcos_estaticos.py` | Como o modelo geral e os reforços das letras paradas se saem nas amostras? |
| `avalia_reforcos_dinamicos.py` | Como os modelos das letras com movimento competem entre si? |
| `confere_pacote.py` | O `.tflite` que foi para dentro do APK funciona como o app o usa? |

### Sinais de corpo: captura e limiares

| Script | Pergunta |
|---|---|
| `testa_continuo.py` | Dá para emendar um sinal no outro? Compara o reconhecimento contínuo com o antigo. |
| `mede_movimento.py` | O movimento de cada sinal passa dos limiares que o app usa? |
| `mede_captura.py` | Quanto do sinal o app realmente captura? |
| `mede_parada.py` | Por que o app só classificava quando o próximo sinal começava? |
| `mede_margem.py` | Que margem separa acerto de erro? |
| `testa_taxa_quadros.py` | O celular roda a ~13 quadros/s e os vídeos têm 30. Isso atrapalha? |

### Câmera e mãos

| Script | Pergunta |
|---|---|
| `testa_espelho.py` | O app espelha a câmera frontal e o treino não. Isso muda o resultado? |
| `testa_troca_maos.py` | O app vê as mãos trocadas de lado em relação ao treino? |
| `testa_aumento_troca.py` | Treinar também com as mãos trocadas ajuda ou atrapalha? |

### Experimentos de treino

| Script | Pergunta |
|---|---|
| `experimento.py`, `experimento2.py` | Que configuração de treino acerta mais, em avaliação honesta? |
| `extrai_cache.py` | (utilitário) Gera o `cache_corpo.npz` usado pelos outros. |

## Por que existe

Várias calibrações do app saíram daqui. Exemplo: o reconhecimento contínuo do
corpo foi decidido pelo `testa_continuo.py`, que mostrou as frases emendadas
saindo certas em 89% das vezes contra 24% do jeito antigo. Quando um script
justificar uma constante, cite o resultado no comentário dela e no
[`CHANGELOG.md`](../../../CHANGELOG.md).

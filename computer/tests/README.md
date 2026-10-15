# O contrato entre o treino e o app

O modelo aprende com números calculados em **Python** (no treino) e é usado
com números calculados em **Kotlin** (no app). Se as duas contas derem
resultados diferentes, o modelo erra no celular **sem dar erro nenhum**: só
reconhece pior.

Esta pasta congela um conjunto de entradas e as saídas esperadas. Os dois
lados são testados contra ele:

| Lado | Teste |
|---|---|
| Python | `computer/treino/tests/test_landmark_contract.py` |
| Kotlin | `mobile/app/src/test/.../LandmarkContractTest.kt` |

| Arquivo | O que é |
|---|---|
| `fixtures/landmark_contract.json` | O gabarito: entradas e saídas esperadas. |
| `gerar_fixtures_contrato.py` | Gera o gabarito a partir da matemática do Python. |

## Quando regerar

**Só** quando você mudou a matemática **de propósito, nos dois lados**:

```powershell
cd computer
python tests\gerar_fixtures_contrato.py
```

Se um dos testes falhou sem você ter mudado a matemática, **não regere**: um
dos lados saiu da linha, e o certo é corrigir esse lado. Regerar para o teste
passar apaga justamente a proteção que ele dá.

# Reconhecedor de PC, em módulos

O **mesmo** reconhecedor de [`../linear/`](../linear/), separado em 10 arquivos
pequenos, um assunto por arquivo. Bom para estudar ou para achar uma regra
específica sem ler um arquivo enorme.

| Arquivo | Assunto |
|---|---|
| `app_backend_unificado.py` | **Comece por aqui**: liga a câmera e o servidor. |
| `m01_visuall_config.py` | Todas as constantes: limiares, tamanhos de janela, confianças. |
| `m02_visuall_modelos.py` | Carrega os modelos. |
| `m03_visuall_traducao.py` | Monta a frase com concordância (artigo, gênero, verbo). |
| `m04_visuall_alfabeto.py` | Reconhece as letras. |
| `m05_visuall_corpo.py` | Reconhece os sinais de corpo. |
| `m06_visuall_rosto.py` | Lê a sobrancelha (frase vira pergunta). |
| `m07_visuall_estado.py` | O estado compartilhado entre as partes. |
| `m08_visuall_captura.py` | A webcam. |
| `m09_visuall_processamento.py` | O laço principal, quadro a quadro. |
| `m10_visuall_servidor.py` | O servidor que manda o resultado para a página. |

## Rodar

```powershell
cd computer
python modular\app_backend_unificado.py
```

A página é a mesma do linear: `linear\frontend\index.html`.

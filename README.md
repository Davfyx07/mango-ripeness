# Clasificación del estado de maduración del mango

Clasifica fotos de mango en tres estados: `unripe`, `partially_ripe` y `ripe`.

## Carpetas

| Carpeta | Contenido |
|---|---|
| `data/raw/` | Fotos originales (6 GB). No está en git. |
| `data/processed/` | Copias reducidas a 320 px. Las genera `src/prepare_data.py`. |
| `data/splits/` | `train.csv`, `val.csv`, `test.csv`: qué foto va en cada partición. |
| `src/` | Código. |
| `outputs/` | Modelos entrenados y gráficas. No está en git. |
| `docs/` | Guías, entre ellas cómo preparar el segundo PC. |

## Dataset

Alphonso Mango Ripening Stage Classification Dataset (Mendeley Data):
https://data.mendeley.com/datasets/tyghd6gxw2

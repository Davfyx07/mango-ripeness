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

Prabhu, Akshatha (2024), "Alphonso Mango Ripening Stage Classification Dataset", Mendeley Data, V1,
doi: [10.17632/tyghd6gxw2.1](https://doi.org/10.17632/tyghd6gxw2.1)
(https://data.mendeley.com/datasets/tyghd6gxw2)

Licencia: [Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
Las fotos originales **no** están en este repositorio: hay que descargarlas de Mendeley y ponerlas en `data/raw/`.

### Cambios hechos al dataset

Las fotos de `data/processed/` son una versión modificada del original:

- Reducidas a 320 px en el lado corto y guardadas como JPEG.
- Se quitó `DSC_0285.JPG`, que aparece idéntica en dos clases (`unripe` y `partially_ripe`). Quedan 748 de las 750 fotos.
- Se agruparon por mango y se dividieron en train / val / test (70 / 15 / 15), en `data/splits/`.
- `data/processed/synthetic/` contiene fotos generadas por una GAN entrenada con las de train. No son fotos reales.

Este trabajo no está avalado ni respaldado por la autora del dataset.

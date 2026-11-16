# Versión 0.1: todo entrenado en un solo PC

Corrida completa del 15 de noviembre de 2026 en un PC con una RTX 3050 de 6 GB (PyTorch 2.14.1 + CUDA 13).
Es la **referencia de 1 PC** contra la que se compara el entrenamiento distribuido (`outputs_ddp/`).

Aquí están las tablas, los JSON y las imágenes. Los modelos entrenados (`.pt`, unos 490 MB) están en `outputs/models/` y no van a git.

## Tiempos (segundos)

| Paso | Comando | Tiempo |
|---|---|---|
| Hyperband, 10 pruebas por modelo | `tune.py --trials 10` | 2140 |
| Entrenar los 5 modelos | `train.py --all` | 362 |
| Comparar tipos de validación cruzada | `cross_val.py` | 27 |
| K-fold de EfficientNet-B0 | `cross_val.py --finetune efficientnet_b0` | 269 |
| Ensembles | `ensemble.py` | 11 |
| GAN, 300 épocas | `gan.py` | 183 |
| ResNet50 con fotos sintéticas | `train.py ... --train-csv train_gan` | 103 |

## Resultados

Validación (114 fotos), tras el tuning: ResNet50 0.956, EfficientNet-B0 0.974, ConvNeXt-Tiny 0.991, ViT-Small 0.982, Swin-Tiny 0.974.

Test (114 fotos):

| Modelo | Accuracy | Errores |
|---|---|---|
| ViT-Small | 0.965 | 4 |
| ResNet50 | 0.956 | 5 |
| Swin-Tiny | 0.956 | 5 |
| ConvNeXt-Tiny | 0.947 | 6 |
| EfficientNet-B0 | 0.868 | 15 |
| Ensembles (homogéneo CNN, homogéneo Transformers, heterogéneo, híbrido) | 0.956 | 5 |

Hay más detalle en `ensemble_results.csv`, `cross_val_methods.csv`, `tuning/trials.csv` y `logs/`.
Cada número sale de una sola corrida con una semilla.

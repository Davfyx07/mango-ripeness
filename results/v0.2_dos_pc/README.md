# Versión 0.2: entrenamiento distribuido en 2 PCs

Corrida del 16 de noviembre de 2026 (14:23 a 15:55, 1 h 32 min) con `src/train_ddp.py`: Hyperband, entrenamiento final de los 5 modelos y ensembles, todo repartido entre dos PCs.
Se compara con la versión 0.1 (`../v0.1_un_pc/`), que usó un solo PC.

## Condiciones

- **PC 0:** laptop con RTX 3050 de 6 GB. **PC 1:** PC de escritorio con una tarjeta NVIDIA (bfloat16).
- Los dos por **cable Ethernet a 1 Gbps** al mismo router. El tráfico medido entre los PCs fue de unos 85 MB/s en cada sentido.
- 5 pruebas de Hyperband por modelo (la versión 0.1 usó 10), 15 épocas máximas, 15 épocas en el entrenamiento final.
- Promedio de gradientes hecho a mano: la clase `DistributedDataParallel` de PyTorch se cae en Windows con la GPU (torch 2.14.1).
- Con 2 PCs el lote efectivo se duplica, y la precisión mixta es bfloat16 (la 0.1 usó float16). Por eso los resultados no son idénticos a los de un PC.

## Tiempos (segundos)

| Fase | 1 PC (v0.1, 10 pruebas) | 2 PCs (v0.2, 5 pruebas) |
|---|---|---|
| Hyperband | 2140 | 3996 |
| Entrenar los 5 modelos | 362 | 1309 |
| **Total** | **2502** | **5305** |

Con 2 PCs tardó **2.1 veces más** pese a hacer la mitad de pruebas: los gradientes viajan por la red en cada paso y la red es el cuello de botella. Una época de ResNet50 tardó unos **18 s por cable**; en una primera prueba por Wi-Fi tardaba unos 47 s, y sola en una laptop, unos 5 s.

Tiempos por modelo: `ddp_summary_2pc.json`.

## Resultados en test (114 fotos)

| Modelo | Accuracy | F1 macro | Errores |
|---|---|---|---|
| ViT-Small | 0.974 | 0.974 | 3 |
| Swin-Tiny | 0.974 | 0.974 | 3 |
| ResNet50 | 0.965 | 0.965 | 4 |
| ConvNeXt-Tiny | 0.930 | 0.930 | 8 |
| EfficientNet-B0 | 0.895 | 0.896 | 12 |
| Homogéneo: 3 CNN | 0.956 | 0.956 | 5 |
| Homogéneo: 2 Transformers | 0.974 | 0.974 | 3 |
| Heterogéneo: los 5 | 0.965 | 0.965 | 4 |
| Híbrido: CNN + Transformers | 0.974 | 0.974 | 3 |

Detalle en `ensemble_results.csv`, curvas en `curvas_loss.png` y `curvas_accuracy.png` (la corrida distribuida no calculó el accuracy de train), mejores hiperparámetros en `tuning/best_params.json`.

## Qué se puede decir (y qué no)

- Los Transformers quedan arriba y EfficientNet-B0 abajo, igual que en la versión 0.1.
- Los ensembles **no superan** al mejor modelo solo.
- Una foto de test vale 0.9 puntos, y el test son unos 40 mangos: diferencias de una o dos fotos no son concluyentes.
- Cada número sale de una sola corrida con una semilla.
- Todo es con fotos de estudio; no se sabe cuánto rinde con fotos de celular.

Los modelos entrenados (`.pt`) no están en git; están en `outputs_ddp/models/` del PC 0.

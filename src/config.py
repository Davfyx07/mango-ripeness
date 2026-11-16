import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # carpeta del proyecto (la que contiene src/)
RAW_DIR = ROOT / "data" / "raw"                 # fotos originales: nunca se modifican
PROCESSED_DIR = ROOT / "data" / "processed"     # copias reducidas: las que usa el entrenamiento
SPLITS_DIR = ROOT / "data" / "splits"           # train.csv, val.csv, test.csv
OUTPUTS_DIR = Path(os.environ.get("MANGO_OUTPUTS", ROOT / "outputs"))   # modelos, gráficas, logs (train_ddp usa outputs_ddp)

SEED = 42
CLASSES = ["unripe", "partially_ripe", "ripe"]  # la posición es la etiqueta numérica: 0, 1, 2

STORE_SIZE = 320     # lado corto (px) de las copias en processed
IMG_SIZE = 224       # tamaño de la imagen que entra al modelo
GROUP_GAP_S = 120    # fotos de la misma cámara con <= 120 s de diferencia van al mismo grupo

MEAN = [0.485, 0.456, 0.406]   # media y desviación de ImageNet (los modelos preentrenados las esperan)
STD = [0.229, 0.224, 0.225]

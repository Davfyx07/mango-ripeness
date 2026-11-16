"""Topic 1: transformaciones, Dataset y DataLoader (el "data generator").
Uso (vista previa):  python src/dataset.py
"""
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.transforms import v2 as T

from config import IMG_SIZE, MEAN, OUTPUTS_DIR, PROCESSED_DIR, SPLITS_DIR, STD, STORE_SIZE


def train_transform(flip=True, degrade=True):
    """Aumentación: solo para train. flip y degrade son interruptores que Hyperband va a probar."""
    steps = [
        T.CenterCrop(STORE_SIZE),                                            # cuadrado centrado: solo quita fondo
        T.RandomRotation(30, fill=255),                                      # celular inclinado; esquinas en blanco
        T.RandomResizedCrop(IMG_SIZE, scale=(0.6, 1.0), ratio=(1.0, 1.0)),   # zoom 60-100% sin deformar
    ]
    if flip:
        steps.append(T.RandomHorizontalFlip())
    steps.append(T.ColorJitter(brightness=0.15, contrast=0.15))              # sin hue/saturation: el color es la etiqueta
    if degrade:
        steps.append(T.RandomApply([T.GaussianBlur(5, sigma=(0.1, 1.5))], p=0.3))
    steps += [T.ToImage(), T.ToDtype(torch.float32, scale=True)]             # imagen -> tensor con valores 0..1
    if degrade:
        steps.append(T.RandomApply([T.GaussianNoise(sigma=0.03)], p=0.3))
    steps.append(T.Normalize(MEAN, STD))
    return T.Compose(steps)


def eval_transform():
    """Para val y test: sin nada aleatorio, siempre da el mismo resultado."""
    return T.Compose([
        T.CenterCrop(STORE_SIZE),
        T.Resize(IMG_SIZE),
        T.ToImage(),
        T.ToDtype(torch.float32, scale=True),
        T.Normalize(MEAN, STD),
    ])


def load_split(name):
    """Lee train.csv, val.csv o test.csv."""
    return pd.read_csv(SPLITS_DIR / f"{name}.csv")


class MangoDataset(Dataset):
    """Sabe cuántas fotos hay y cómo cargar UNA. No carga nada hasta que se lo piden."""

    def __init__(self, df, transform):
        self.df = df.reset_index(drop=True)
        self.transform = transform

    def __len__(self):
        return len(self.df)

    def __getitem__(self, i):
        row = self.df.iloc[i]
        img = Image.open(PROCESSED_DIR / row["file"]).convert("RGB")
        return self.transform(img), int(row["label_idx"])


def make_loader(df, transform, batch_size=32, shuffle=False, workers=4):
    """El data generator: entrega las fotos por lotes, así nunca está todo el dataset en memoria."""
    return DataLoader(
        MangoDataset(df, transform),
        batch_size=batch_size,
        shuffle=shuffle,                          # True solo en train
        num_workers=workers,                      # procesos que cargan fotos en paralelo
        persistent_workers=workers > 0,           # no los reinicia en cada época (en Windows arrancan lento)
        pin_memory=torch.cuda.is_available(),     # acelera la copia a la GPU
    )


if __name__ == "__main__":  # obligatorio en Windows cuando workers > 0
    from torchvision.utils import save_image

    loader = make_loader(load_split("train"), train_transform(), batch_size=16, shuffle=True)
    images, labels = next(iter(loader))
    assert images.shape == (16, 3, IMG_SIZE, IMG_SIZE), images.shape
    print("lote:", tuple(images.shape), "| etiquetas:", labels.tolist())

    mean, std = torch.tensor(MEAN).view(3, 1, 1), torch.tensor(STD).view(3, 1, 1)
    OUTPUTS_DIR.mkdir(exist_ok=True)
    save_image(images * std + mean, OUTPUTS_DIR / "preview_train.png", nrow=8)   # deshace el Normalize para poder verlas
    print("vista previa guardada en", OUTPUTS_DIR / "preview_train.png")

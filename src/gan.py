"""Topic 1 (GANs): GAN condicional que genera fotos sintéticas de mango de cada clase.
Uso:  python src/gan.py --epochs 300

Se entrena SOLO con las fotos de train. Al final guarda las fotos sintéticas en
data/processed/synthetic/ y crea data/splits/train_gan.csv (train + sintéticas).
Las sintéticas nunca entran a val ni a test.
"""
import argparse

import pandas as pd
import torch
from torch import nn
from torchvision.transforms import v2 as T
from torchvision.utils import save_image

from config import CLASSES, OUTPUTS_DIR, PROCESSED_DIR, SEED, SPLITS_DIR, STORE_SIZE
from dataset import load_split, make_loader

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SIZE = 64      # las fotos sintéticas son de 64x64: más grande necesita muchas más fotos y tiempo
NOISE = 100    # tamaño del vector de ruido del que parte cada foto


class Generator(nn.Module):
    """Convierte ruido + clase en una foto. Cada bloque duplica el tamaño: 4 -> 8 -> 16 -> 32 -> 64."""

    def __init__(self):
        super().__init__()
        self.embed = nn.Embedding(len(CLASSES), NOISE)   # un vector por clase, que se aprende

        def up(c_in, c_out, stride=2, pad=1):
            return [nn.ConvTranspose2d(c_in, c_out, 4, stride, pad, bias=False), nn.BatchNorm2d(c_out), nn.ReLU(True)]

        self.net = nn.Sequential(
            *up(NOISE, 512, 1, 0), *up(512, 256), *up(256, 128), *up(128, 64),
            nn.ConvTranspose2d(64, 3, 4, 2, 1), nn.Tanh(),   # salida entre -1 y 1
        )

    def forward(self, noise, labels):
        return self.net((noise * self.embed(labels)).view(-1, NOISE, 1, 1))   # el ruido se mezcla con la clase


class Discriminator(nn.Module):
    """Recibe una foto + su clase y responde qué tan real parece. Cada bloque reduce el tamaño a la mitad."""

    def __init__(self):
        super().__init__()
        self.embed = nn.Embedding(len(CLASSES), SIZE * SIZE)   # la clase entra como un cuarto canal de la imagen

        def down(c_in, c_out):
            return [nn.utils.spectral_norm(nn.Conv2d(c_in, c_out, 4, 2, 1)), nn.LeakyReLU(0.2, True)]

        self.net = nn.Sequential(*down(4, 64), *down(64, 128), *down(128, 256), *down(256, 512), nn.Conv2d(512, 1, 4))

    def forward(self, images, labels):
        label_map = self.embed(labels).view(-1, 1, SIZE, SIZE)
        return self.net(torch.cat([images, label_map], dim=1)).view(-1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--per-class", type=int, default=100, help="fotos sintéticas a generar por clase")
    args = parser.parse_args()

    torch.manual_seed(SEED)
    transform = T.Compose([
        T.CenterCrop(STORE_SIZE), T.Resize(SIZE), T.RandomHorizontalFlip(),
        T.ToImage(), T.ToDtype(torch.float32, scale=True), T.Normalize([0.5] * 3, [0.5] * 3),   # valores entre -1 y 1
    ])
    train = load_split("train")
    loader = make_loader(train, transform, batch_size=64, shuffle=True)
    G, D = Generator().to(DEVICE), Discriminator().to(DEVICE)
    opt_g = torch.optim.Adam(G.parameters(), lr=2e-4, betas=(0.5, 0.999))
    opt_d = torch.optim.Adam(D.parameters(), lr=2e-4, betas=(0.5, 0.999))
    bce = nn.BCEWithLogitsLoss()

    for epoch in range(1, args.epochs + 1):
        for real, labels in loader:
            real, labels = real.to(DEVICE), labels.to(DEVICE)
            ones, zeros = torch.ones(len(real), device=DEVICE), torch.zeros(len(real), device=DEVICE)
            fake = G(torch.randn(len(real), NOISE, device=DEVICE), labels)

            # 1) El discriminador aprende a decir "real" a las reales y "falsa" a las generadas
            loss_d = bce(D(real, labels), ones) + bce(D(fake.detach(), labels), zeros)
            opt_d.zero_grad()
            loss_d.backward()
            opt_d.step()

            # 2) El generador aprende a que el discriminador diga "real" a las suyas
            loss_g = bce(D(fake, labels), ones)
            opt_g.zero_grad()
            loss_g.backward()
            opt_g.step()
        if epoch % 10 == 0 or epoch == args.epochs:
            print(f"época {epoch:>3}/{args.epochs}  loss D {loss_d.item():.3f}  loss G {loss_g.item():.3f}")

    # Generar las fotos sintéticas
    G.eval()
    OUTPUTS_DIR.mkdir(exist_ok=True)
    rows = []
    with torch.no_grad():
        for idx, label in enumerate(CLASSES):
            labels = torch.full((args.per_class,), idx, device=DEVICE)
            images = (G(torch.randn(args.per_class, NOISE, device=DEVICE), labels) + 1) / 2     # de vuelta a 0..1
            save_image(images[:16], OUTPUTS_DIR / f"gan_{label}.png", nrow=8)                   # muestra para el informe
            big = nn.functional.interpolate(images, size=STORE_SIZE, mode="bicubic").clamp(0, 1)  # al tamaño de las reales
            (PROCESSED_DIR / "synthetic" / label).mkdir(parents=True, exist_ok=True)
            for i, image in enumerate(big):
                file = f"synthetic/{label}/gan_{i:04d}.jpg"
                save_image(image, PROCESSED_DIR / file)
                rows.append({"file": file, "label": label, "label_idx": idx, "mango_id": -1})

    pd.concat([train, pd.DataFrame(rows)]).to_csv(SPLITS_DIR / "train_gan.csv", index=False)
    print(f"{len(rows)} fotos sintéticas guardadas. Muestras en outputs/gan_<clase>.png")
    print("Para comparar:  python src/train.py --model resnet50 --train-csv train_gan --name resnet50_gan")

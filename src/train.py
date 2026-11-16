"""Topic 4: entrena y evalúa un modelo. Los demás scripts reutilizan fit(), predict() y load_model().
Uso:  python src/train.py --model resnet50
      python src/train.py --all                      (los 5 modelos, uno tras otro)
      python src/train.py --model resnet50 --train-csv train_gan --name resnet50_gan
"""
import argparse
import json
import random
import time

import numpy as np
import torch
from torch import nn

from config import OUTPUTS_DIR, SEED
from dataset import eval_transform, load_split, make_loader, train_transform
from models import MODELS, create_model

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_AMP = DEVICE.type == "cuda"            # precisión mixta: mitad de memoria y más rápido en GPU
MODELS_DIR = OUTPUTS_DIR / "models"
BEST_PARAMS = OUTPUTS_DIR / "tuning" / "best_params.json"
DEFAULTS = {"lr": 1e-4, "batch_size": 32, "weight_decay": 0.05, "epochs": 15, "flip": True, "degrade": True}


def set_seed(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def params_for(model_name):
    """Hiperparámetros del modelo: los que encontró tune.py si existen; si no, los de DEFAULTS."""
    params = dict(DEFAULTS)
    if BEST_PARAMS.exists():
        params.update(json.loads(BEST_PARAMS.read_text()).get(model_name, {}))
    return params


def run_epoch(model, loader, optimizer=None, scaler=None):
    """Una pasada por los datos. Con optimizer entrena; sin él solo evalúa. Devuelve (loss, accuracy)."""
    training = optimizer is not None
    model.train(training)
    total_loss, correct, n = 0.0, 0, 0
    with torch.set_grad_enabled(training):
        for images, labels in loader:
            images, labels = images.to(DEVICE, non_blocking=True), labels.to(DEVICE, non_blocking=True)
            with torch.autocast(DEVICE.type, enabled=USE_AMP):
                logits = model(images)
                loss = nn.functional.cross_entropy(logits, labels)
            if training:
                optimizer.zero_grad()
                scaler.scale(loss).backward()      # calcula los gradientes
                scaler.step(optimizer)             # ajusta los pesos
                scaler.update()
            total_loss += loss.item() * len(labels)
            correct += (logits.argmax(1) == labels).sum().item()
            n += len(labels)
    return total_loss / n, correct / n


def fit(model_name, train_df, val_df, lr, batch_size, weight_decay, epochs, flip, degrade, save_as=None, on_epoch=None):
    """Entrena con train_df y mide con val_df en cada época. Se queda con la época de menor loss de validación."""
    set_seed()
    model = create_model(model_name).to(DEVICE)
    train_loader = make_loader(train_df, train_transform(flip, degrade), batch_size, shuffle=True)
    val_loader = make_loader(val_df, eval_transform(), batch_size, workers=0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)  # baja el lr poco a poco
    scaler = torch.amp.GradScaler(DEVICE.type, enabled=USE_AMP)

    best = {"val_loss": float("inf"), "val_acc": 0.0, "epoch": 0}
    history = []
    for epoch in range(1, epochs + 1):
        start = time.time()
        train_loss, train_acc = run_epoch(model, train_loader, optimizer, scaler)
        val_loss, val_acc = run_epoch(model, val_loader)
        scheduler.step()
        history.append({"epoch": epoch, "train_loss": train_loss, "train_acc": train_acc,
                        "val_loss": val_loss, "val_acc": val_acc, "seconds": time.time() - start})
        print(f"  época {epoch:>2}/{epochs}  train loss {train_loss:.3f} acc {train_acc:.3f}"
              f"  |  val loss {val_loss:.3f} acc {val_acc:.3f}  ({time.time() - start:.0f} s)")
        if val_loss < best["val_loss"]:
            best = {"val_loss": val_loss, "val_acc": val_acc, "epoch": epoch}
            if save_as:
                MODELS_DIR.mkdir(parents=True, exist_ok=True)
                torch.save(model.state_dict(), MODELS_DIR / f"{save_as}.pt")
        if on_epoch:
            on_epoch(epoch, val_loss, val_acc)     # lo usa tune.py para que Hyperband corte los malos
    best["history"] = history
    return best


def load_model(name, arch=None):
    """Carga un modelo ya entrenado desde outputs/models/<name>.pt."""
    model = create_model(arch or name, pretrained=False)
    model.load_state_dict(torch.load(MODELS_DIR / f"{name}.pt", map_location=DEVICE))
    return model.to(DEVICE)


@torch.no_grad()
def predict(model, df, batch_size=64):
    """Probabilidad de cada clase para cada foto de df: matriz (N, 3), en el mismo orden que df."""
    model.eval()
    probs = []
    for images, _ in make_loader(df, eval_transform(), batch_size, workers=0):
        with torch.autocast(DEVICE.type, enabled=USE_AMP):
            logits = model(images.to(DEVICE))
        probs.append(logits.float().softmax(1).cpu())
    return torch.cat(probs).numpy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS)
    parser.add_argument("--all", action="store_true", help="entrena los 5 modelos")
    parser.add_argument("--epochs", type=int, help="si no se da, usa las de los hiperparámetros")
    parser.add_argument("--train-csv", default="train", help="train, o train_gan para incluir las sintéticas")
    parser.add_argument("--name", help="nombre del archivo guardado (por defecto, el del modelo)")
    args = parser.parse_args()
    assert args.model or args.all, "indica --model <nombre> o --all"

    train_df, val_df = load_split(args.train_csv), load_split("val")
    print(f"dispositivo: {DEVICE} | train: {len(train_df)} fotos | val: {len(val_df)} fotos")
    for model_name in MODELS if args.all else [args.model]:
        params = params_for(model_name)
        if args.epochs:
            params["epochs"] = args.epochs
        name = args.name or model_name
        print(f"\n== {name}  {params}")
        result = fit(model_name, train_df, val_df, **params, save_as=name)
        (MODELS_DIR / f"{name}.json").write_text(json.dumps({"params": params, **result}, indent=2))
        print(f"mejor época: {result['epoch']}  val loss {result['val_loss']:.3f}  val acc {result['val_acc']:.3f}")

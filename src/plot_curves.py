"""Dibuja las curvas de entrenamiento (loss y accuracy por época) de los 5 modelos.
Uso:  python src/plot_curves.py
No entrena nada: lee los JSON que guardaron train.py y train_ddp.py.
Guarda curvas_loss.png y curvas_accuracy.png en results/v0.1_un_pc/ y en results/v0.2_dos_pc/.
"""
import json

import matplotlib

matplotlib.use("Agg")  # sin ventana: solo guarda archivos
import matplotlib.pyplot as plt

from config import ROOT
from models import MODELS

RUNS = {"Versión 0.1 (1 PC)": ROOT / "results" / "v0.1_un_pc", "2 PCs (distribuido)": ROOT / "results" / "v0.2_dos_pc"}


def load_histories(folder):
    """Historial época por época de cada modelo: {nombre: (mejor época, lista de épocas)}."""
    out = {}
    for name in MODELS:
        path = folder / "models" / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text())
            out[name] = (data["epoch"], data["history"])
    return out


def plot_loss(histories, title, path):
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), sharey=True)
    for ax, (name, (best, hist)) in zip(axes.flat, histories.items()):
        epochs = [h["epoch"] for h in hist]
        ax.plot(epochs, [h["train_loss"] for h in hist], label="train")
        ax.plot(epochs, [h["val_loss"] for h in hist], label="validación")
        ax.axvline(best, color="gray", linestyle="--", label=f"mejor época ({best})")  # la que se guarda
        ax.set(title=name, xlabel="época", ylabel="loss")
        ax.legend()
    for ax in axes.flat[len(histories):]:
        ax.axis("off")
    fig.suptitle(f"Loss por época: {title}")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_accuracy(histories, title, path):
    fig, ax = plt.subplots(figsize=(9, 5))
    for name, (_, hist) in histories.items():
        epochs = [h["epoch"] for h in hist]
        line, = ax.plot(epochs, [h["val_acc"] for h in hist], label=name)
        if "train_acc" in hist[0]:  # la corrida distribuida no lo calculó
            ax.plot(epochs, [h["train_acc"] for h in hist], linestyle=":", color=line.get_color())
    ax.set(xlabel="época", ylabel="accuracy", title=f"Accuracy por época: {title}  (línea continua = validación, punteada = train)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    for title, folder in RUNS.items():
        histories = load_histories(folder)
        if not histories:
            print(f"{title}: no hay historiales en {folder}, se omite")
            continue
        plot_loss(histories, title, folder / "curvas_loss.png")
        plot_accuracy(histories, title, folder / "curvas_accuracy.png")
        print(f"{title}: {len(histories)} modelos -> {folder}")

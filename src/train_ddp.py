"""Topic 6: entrenamiento distribuido entre varios PCs, desde Hyperband hasta los ensembles.

Hace lo mismo que tune.py + train.py + ensemble.py, pero cada entrenamiento se reparte entre los PCs:
cada PC procesa una parte distinta de las fotos y en cada paso promedian sus gradientes por la red.
El PC 0 (el que tiene RANK=0) manda las órdenes y guarda los resultados en outputs_ddp/.

Uso en dos PCs (primero el PC 0, luego el PC 1; ver docs/setup_pc_amigo.md):
    $env:MASTER_ADDR="<IP del PC 0>"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="0"   (RANK=1 en el otro)
    python src\\train_ddp.py
Opciones (se ponen solo en el PC 0; el PC 1 obedece):
    --trials 10      pruebas de Hyperband por modelo
    --max-epochs 15  épocas máximas de cada prueba
    --epochs 15      épocas del entrenamiento final de cada modelo
    --models a b     solo esos modelos (por defecto, los 5)
    --skip-tune      sin Hyperband: usa outputs_ddp/tuning/best_params.json, o los valores por defecto
Prueba rápida:  python src\\train_ddp.py --models efficientnet_b0 --trials 2 --max-epochs 3 --epochs 2
Sin las variables MASTER_ADDR, etc., corre en un solo PC (sirve de referencia para comparar tiempos).
"""
import os
from pathlib import Path

# Antes de importar config: así train.py y ensemble.py guardan en outputs_ddp y no pisan la versión 0.1.
os.environ.setdefault("MANGO_OUTPUTS", str(Path(__file__).resolve().parent.parent / "outputs_ddp"))

import argparse
import functools
import json
import socket
import subprocess
import sys
import time

import optuna
import torch
import torch.distributed as dist
from torch import nn
from torch.utils.data import DataLoader
from torch.utils.data.distributed import DistributedSampler

from config import OUTPUTS_DIR, SEED
from dataset import MangoDataset, eval_transform, load_split, make_loader, train_transform
from models import MODELS, create_model
from train import BEST_PARAMS, DEVICE, MODELS_DIR, params_for, run_epoch, set_seed

TUNING_DIR = OUTPUTS_DIR / "tuning"

# DistributedDataParallel (la clase de PyTorch para esto) se cae en Windows cuando los gradientes están
# en la GPU (probado con torch 2.14.1). Por eso aquí el promedio se hace a mano, pasando por la CPU.


@functools.cache
def amp_dtype():
    """bfloat16 si la GPU lo soporta (RTX serie 30 en adelante): memoria a la mitad y sin GradScaler."""
    ok = DEVICE.type == "cuda" and torch.cuda.is_bf16_supported(including_emulation=False)
    return torch.bfloat16 if ok else None


def to_vector(tensors):
    """Une muchos tensores en un solo vector en la CPU, para enviarlo de una vez por la red."""
    return torch.cat([t.flatten() for t in tensors]).cpu()


@torch.no_grad()
def from_vector(vector, tensors):
    """Reparte el vector de vuelta en los tensores originales (en la GPU)."""
    start = 0
    for t in tensors:
        t.copy_(vector[start:start + t.numel()].view_as(t))
        start += t.numel()


@torch.no_grad()
def sync_state(model):
    """Todos los PCs arrancan con los pesos exactos del PC 0 (pesos y estadísticas de BatchNorm).
    Así el PC 1 no necesita descargar los pesos preentrenados: los recibe por la red."""
    for tensor in model.state_dict().values():
        cpu = tensor.detach().cpu().contiguous()
        dist.broadcast(cpu, src=0)
        tensor.copy_(cpu)


def average_gradients(model, world):
    """El corazón del entrenamiento distribuido: cada PC reemplaza sus gradientes por el promedio de todos."""
    grads = [p.grad for p in model.parameters() if p.grad is not None]
    vector = to_vector(grads)
    dist.all_reduce(vector)                # suma los vectores de todos los PCs (viaja por la red)
    from_vector(vector / world, grads)


def train_epoch(model, loader, optimizer, world):
    model.train()
    total_loss, n = 0.0, 0
    for images, labels in loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)
        with torch.autocast(DEVICE.type, dtype=amp_dtype(), enabled=amp_dtype() is not None):
            loss = nn.functional.cross_entropy(model(images), labels)
        optimizer.zero_grad()
        loss.backward()                    # gradientes con las fotos de ESTE PC
        average_gradients(model, world)    # se promedian con los del otro PC
        optimizer.step()                   # todos aplican el mismo ajuste: los modelos siguen idénticos
        total_loss += loss.item() * len(labels)
        n += len(labels)
    return total_loss / n


def run_job(job, rank, world, train_df, val_df, on_epoch=None):
    """Entrena UN modelo entre todos los PCs. Todos los PCs ejecutan esta función a la vez, con el mismo job.
    El PC 0 valida después de cada época y decide si se sigue (on_epoch devuelve True para parar)."""
    p = job["params"]
    set_seed()
    model = create_model(job["model"], pretrained=rank == 0).to(DEVICE)
    sync_state(model)
    train_set = MangoDataset(train_df, train_transform(p["flip"], p["degrade"]))
    sampler = DistributedSampler(train_set, num_replicas=world, rank=rank, shuffle=True, seed=SEED)  # cada PC, fotos distintas
    loader = DataLoader(train_set, batch_size=p["batch_size"], sampler=sampler, num_workers=4,
                        persistent_workers=True, pin_memory=DEVICE.type == "cuda")
    val_loader = make_loader(val_df, eval_transform(), 64, workers=0) if rank == 0 else None
    optimizer = torch.optim.AdamW(model.parameters(), lr=p["lr"], weight_decay=p["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=job["epochs"])

    best = {"val_loss": float("inf"), "val_acc": 0.0, "epoch": 0}
    history, train_seconds, stopped = [], 0.0, False
    for epoch in range(1, job["epochs"] + 1):
        sampler.set_epoch(epoch)           # cambia el reparto de fotos en cada época
        start = time.time()
        train_loss = train_epoch(model, loader, optimizer, world)
        scheduler.step()
        seconds = time.time() - start
        train_seconds += seconds
        stats = torch.zeros(3)
        if rank == 0:                      # solo el PC 0 valida, guarda y decide
            val_loss, val_acc = run_epoch(model, val_loader)
            history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss,
                            "val_acc": val_acc, "seconds": seconds})
            print(f"  época {epoch:>2}/{job['epochs']}  train loss {train_loss:.3f}"
                  f"  |  val loss {val_loss:.3f} acc {val_acc:.3f}  ({seconds:.0f} s)", flush=True)
            if val_loss < best["val_loss"]:
                best = {"val_loss": val_loss, "val_acc": val_acc, "epoch": epoch}
                if job.get("save_as"):
                    MODELS_DIR.mkdir(parents=True, exist_ok=True)
                    torch.save(model.state_dict(), MODELS_DIR / f"{job['save_as']}.pt")
            stop = on_epoch(epoch, val_loss, val_acc) if on_epoch else False
            stats = torch.tensor([val_loss, val_acc, float(stop)])
        dist.broadcast(stats, src=0)       # el PC 1 se entera de si hay que parar
        if stats[2] > 0:
            stopped = True
            break
    return {**best, "stopped": stopped, "train_seconds": train_seconds, "history": history}


def send(job):
    """El PC 0 le manda el trabajo a todos los demás (None = terminar)."""
    dist.broadcast_object_list([job], src=0)


def worker_loop(rank, world, train_df, val_df):
    """Lo que hacen los PCs que no son el 0: recibir un trabajo, entrenarlo junto al PC 0, y repetir."""
    while True:
        box = [None]
        dist.broadcast_object_list(box, src=0)
        if box[0] is None:
            return
        run_job(box[0], rank, world, train_df, val_df)


def tune_model(model_name, trials, max_epochs, world, train_df, val_df):
    """Hyperband para un modelo. Cada prueba se entrena entre todos los PCs."""
    TUNING_DIR.mkdir(parents=True, exist_ok=True)
    study = optuna.create_study(
        study_name=model_name, storage=f"sqlite:///{(TUNING_DIR / 'study.db').as_posix()}", load_if_exists=True,
        direction="minimize", sampler=optuna.samplers.TPESampler(seed=SEED),
        pruner=optuna.pruners.HyperbandPruner(min_resource=1, max_resource=max_epochs, reduction_factor=3))

    def objective(trial):
        params = {
            "lr": trial.suggest_float("lr", 1e-5, 1e-3, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [16, 32]),
            "weight_decay": trial.suggest_float("weight_decay", 1e-4, 1e-1, log=True),
            "flip": trial.suggest_categorical("flip", [True, False]),
            "degrade": trial.suggest_categorical("degrade", [True, False]),
        }
        job = {"model": model_name, "params": params, "epochs": max_epochs}
        print(f"\n== {model_name}, prueba {trial.number}: {params}", flush=True)
        send(job)

        def on_epoch(epoch, val_loss, val_acc):
            trial.report(val_loss, epoch)
            return trial.should_prune()    # Hyperband decide si vale la pena seguir

        result = run_job(job, 0, world, train_df, val_df, on_epoch)
        if result["stopped"]:
            raise optuna.TrialPruned()
        return result["val_loss"]

    done = sum(t.state.is_finished() for t in study.trials)    # si se interrumpió, continúa donde quedó
    study.optimize(objective, n_trials=max(trials - done, 0))
    return study


def save_best(study, model_name):
    """Guarda la mejor configuración del modelo en outputs_ddp/tuning/best_params.json (la lee train.params_for)."""
    best = json.loads(BEST_PARAMS.read_text()) if BEST_PARAMS.exists() else {}
    if any(t.state == optuna.trial.TrialState.COMPLETE for t in study.trials):
        best[model_name] = study.best_params
        print(f"{model_name}: mejor val loss {study.best_value:.3f}  {study.best_params}")
    else:
        print(f"{model_name}: ninguna prueba llegó al final; se usarán los valores por defecto")
    BEST_PARAMS.write_text(json.dumps(best, indent=2))


def drive(args, world, train_df, val_df):
    """Lo que hace el PC 0: Hyperband, entrenamiento final y resumen de tiempos."""
    summary = {"pcs": world, "tune": {}, "train": {}}
    if not args.skip_tune:
        for name in args.models:
            start = time.time()
            save_best(tune_model(name, args.trials, args.max_epochs, world, train_df, val_df), name)
            summary["tune"][name] = {"seconds": time.time() - start}
    for name in args.models:
        keys = ("lr", "batch_size", "weight_decay", "flip", "degrade")
        params = {k: v for k, v in params_for(name).items() if k in keys}
        print(f"\n== entrenamiento final: {name}  {params}", flush=True)
        job = {"model": name, "params": params, "epochs": args.epochs, "save_as": name}
        send(job)
        result = run_job(job, 0, world, train_df, val_df)
        print(f"mejor época: {result['epoch']}  val loss {result['val_loss']:.3f}  val acc {result['val_acc']:.3f}"
              f"  (entrenamiento: {result['train_seconds']:.0f} s)")
        summary["train"][name] = {k: result[k] for k in ("epoch", "val_loss", "val_acc", "train_seconds")}
        (MODELS_DIR / f"{name}.json").write_text(json.dumps({"params": params, **result}, indent=2))
    send(None)
    summary["total_seconds"] = (sum(v["seconds"] for v in summary["tune"].values())
                                + sum(v["train_seconds"] for v in summary["train"].values()))
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / f"ddp_summary_{world}pc.json").write_text(json.dumps(summary, indent=2))
    print(f"\ntiempo con {world} PC: {summary['total_seconds']:.0f} s "
          f"(Hyperband + entrenamiento final). Resumen en outputs_ddp/ddp_summary_{world}pc.json")


if __name__ == "__main__":  # obligatorio en Windows: los procesos que cargan fotos vuelven a leer este archivo
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", choices=MODELS, default=MODELS)
    parser.add_argument("--trials", type=int, default=10, help="pruebas de Hyperband por modelo")
    parser.add_argument("--max-epochs", type=int, default=15, help="épocas máximas de cada prueba de Hyperband")
    parser.add_argument("--epochs", type=int, default=15, help="épocas del entrenamiento final")
    parser.add_argument("--skip-tune", action="store_true")
    args = parser.parse_args()

    # Sin variables de entorno se comporta como un solo PC
    for key, value in {"MASTER_ADDR": "127.0.0.1", "MASTER_PORT": "29500", "WORLD_SIZE": "1", "RANK": "0"}.items():
        os.environ.setdefault(key, value)
    dist.init_process_group("gloo")        # gloo: el único sistema de comunicación que hay en Windows
    rank, world = dist.get_rank(), dist.get_world_size()
    print(f"[{socket.gethostname()}] PC {rank} de {world} | dispositivo: {DEVICE} | "
          f"precisión: {amp_dtype() or 'float32'} | resultados en {OUTPUTS_DIR}", flush=True)

    train_df, val_df = load_split("train"), load_split("val")
    if rank == 0:
        drive(args, world, train_df, val_df)
    else:
        worker_loop(rank, world, train_df, val_df)
    dist.destroy_process_group()

    if rank == 0 and set(args.models) == set(MODELS):
        print("\n== ensembles (test)", flush=True)
        subprocess.run([sys.executable, str(Path(__file__).with_name("ensemble.py"))], check=False)

"""Topic 2: búsqueda de hiperparámetros con Hyperband (Optuna). Hace una búsqueda por cada modelo.
Uso:  python src/tune.py --trials 10                    (10 pruebas para cada uno de los 5 modelos)
      python src/tune.py --trials 10 --model resnet50   (solo un modelo)
Se puede interrumpir y volver a correr: continúa donde quedó (se guarda en outputs/tuning/study.db).
"""
import argparse
import json

import optuna
import pandas as pd

from config import OUTPUTS_DIR, SEED
from dataset import load_split
from models import MODELS
from train import fit

MAX_EPOCHS = 15                      # lo máximo que Hyperband le da a una configuración
TUNING_DIR = OUTPUTS_DIR / "tuning"


def make_objective(model_name):
    def objective(trial):
        """Una prueba: Optuna elige los valores, se entrena con ellos y se devuelve el loss de validación."""
        params = {
            "lr": trial.suggest_float("lr", 1e-5, 1e-3, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [16, 32]),
            "weight_decay": trial.suggest_float("weight_decay", 1e-4, 1e-1, log=True),
            "flip": trial.suggest_categorical("flip", [True, False]),
            "degrade": trial.suggest_categorical("degrade", [True, False]),
        }

        def on_epoch(epoch, val_loss, val_acc):
            trial.report(val_loss, epoch)            # le cuenta a Hyperband cómo va
            trial.set_user_attr("val_acc", val_acc)
            if trial.should_prune():                 # Hyperband decide si vale la pena seguir
                raise optuna.TrialPruned()

        print(f"\n== {model_name}, prueba {trial.number}: {params}")
        result = fit(model_name, TRAIN, VAL, **params, epochs=MAX_EPOCHS, on_epoch=on_epoch)
        return result["val_loss"]

    return objective


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=10, help="pruebas por modelo")
    parser.add_argument("--model", choices=MODELS, help="si no se da, busca para los 5")
    args = parser.parse_args()

    TRAIN, VAL = load_split("train"), load_split("val")   # el test no se toca aquí
    TUNING_DIR.mkdir(parents=True, exist_ok=True)
    for model_name in [args.model] if args.model else MODELS:
        study = optuna.create_study(
            study_name=model_name,
            storage=f"sqlite:///{(TUNING_DIR / 'study.db').as_posix()}",
            load_if_exists=True,
            direction="minimize",                    # se busca el menor loss de validación
            sampler=optuna.samplers.TPESampler(seed=SEED),
            pruner=optuna.pruners.HyperbandPruner(min_resource=1, max_resource=MAX_EPOCHS, reduction_factor=3),
        )
        study.optimize(make_objective(model_name), n_trials=args.trials)

    # Resumen de todos los modelos que tengan búsqueda guardada (para el informe y para train.py)
    storage = f"sqlite:///{(TUNING_DIR / 'study.db').as_posix()}"
    tables, best = [], {}
    for name in optuna.get_all_study_names(storage):
        study = optuna.load_study(study_name=name, storage=storage)
        table = study.trials_dataframe()
        table.insert(0, "model", name)
        tables.append(table)
        complete = table[table["state"] == "COMPLETE"]
        if len(complete):
            best[name] = study.best_params
            pruned = int((table["state"] == "PRUNED").sum())
            print(f"{name:<30} mejor val loss {study.best_value:.3f}  "
                  f"({len(complete)} completas, {pruned} cortadas)  {study.best_params}")
    pd.concat(tables).to_csv(TUNING_DIR / "trials.csv", index=False)
    (TUNING_DIR / "best_params.json").write_text(json.dumps(best, indent=2))

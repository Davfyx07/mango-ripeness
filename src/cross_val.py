"""Topic 3: validación cruzada.
Uso:  python src/cross_val.py                              (compara los tipos de validación cruzada)
      python src/cross_val.py --finetune efficientnet_b0   (K-fold real, entrenando la red en cada fold)
      python src/cross_val.py --finetune all               (K-fold real con los 5 modelos, unos 30 min)

Parte 1: compara los tipos con un clasificador rápido (regresión logística sobre las características
que saca una red preentrenada). Es rápido, y por eso se puede correr hasta leave-one-out.
Parte 2: K-fold estratificado con el entrenamiento completo de la red, que es la evaluación que cuenta.
Siempre se reparten grupos (mangos) enteros, y el test no se usa.
"""
import argparse

import numpy as np
import pandas as pd
import timm
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import (GroupKFold, GroupShuffleSplit, LeaveOneGroupOut, LeavePGroupsOut,
                                     StratifiedGroupKFold, cross_val_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import OUTPUTS_DIR, SEED
from dataset import eval_transform, load_split, make_loader
from models import MODELS
from train import DEVICE, fit, params_for

MAX_FITS = 1000   # más entrenamientos que esto no se corren: solo se reporta cuántos serían


@torch.no_grad()
def extract_features(df):
    """Pasa cada foto por EfficientNet-B0 sin su última capa: cada foto queda como 1280 números."""
    backbone = timm.create_model("efficientnet_b0", pretrained=True, num_classes=0).to(DEVICE).eval()
    feats = [backbone(images.to(DEVICE)).cpu() for images, _ in make_loader(df, eval_transform(), 64, workers=0)]
    return torch.cat(feats).numpy()


def compare_methods(data):
    X, y, groups = extract_features(data), data["label_idx"].values, data["mango_id"].values
    methods = {
        "Hold-out (80/20)": GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED),
        "K-fold (k=5)": GroupKFold(n_splits=5),
        "Stratified K-fold (k=5)": StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED),
        "Monte Carlo (20 x 80/20)": GroupShuffleSplit(n_splits=20, test_size=0.2, random_state=SEED),
        "Leave-one-out (por mango)": LeaveOneGroupOut(),
        "Leave-p-out (p=2, por mango)": LeavePGroupsOut(n_groups=2),
    }
    classifier = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    rows = []
    for name, cv in methods.items():
        n_fits = cv.get_n_splits(X, y, groups)
        if n_fits > MAX_FITS:
            rows.append({"método": name, "entrenamientos": n_fits, "accuracy": None, "desviación": None,
                         "nota": "no se corre: demasiados entrenamientos"})
            continue
        scores = cross_val_score(classifier, X, y, groups=groups, cv=cv, n_jobs=-1)
        rows.append({"método": name, "entrenamientos": n_fits, "accuracy": scores.mean(),
                     "desviación": scores.std(), "nota": ""})
    rows.append({"método": "Time series (rolling)", "entrenamientos": None, "accuracy": None, "desviación": None,
                 "nota": "no aplica: las fotos no son una serie de tiempo"})
    table = pd.DataFrame(rows)
    table["entrenamientos"] = table["entrenamientos"].astype("Int64")   # enteros aunque haya celdas vacías
    table.to_csv(OUTPUTS_DIR / "cross_val_methods.csv", index=False)
    print(table.to_string(index=False, float_format="%.3f", na_rep="-"))


def kfold_finetune(data, model_name, k):
    cv = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=SEED)
    rows = []
    for fold, (train_idx, val_idx) in enumerate(cv.split(data, data["label_idx"], data["mango_id"]), start=1):
        print(f"\n== fold {fold}/{k}: {len(train_idx)} fotos para entrenar, {len(val_idx)} para validar")
        result = fit(model_name, data.iloc[train_idx], data.iloc[val_idx], **params_for(model_name))
        rows.append({"fold": fold, "val_loss": result["val_loss"], "val_acc": result["val_acc"]})
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUTS_DIR / f"cross_val_{model_name}.csv", index=False)
    print(table.to_string(index=False, float_format="%.3f"))
    print(f"accuracy {model_name}: {table['val_acc'].mean():.3f} ± {table['val_acc'].std():.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--finetune", metavar="MODELO", help="K-fold entrenando este modelo en cada fold")
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()

    OUTPUTS_DIR.mkdir(exist_ok=True)
    data = pd.concat([load_split("train"), load_split("val")], ignore_index=True)   # el test queda fuera
    print(f"{len(data)} fotos de {data['mango_id'].nunique()} mangos (train + val)")
    if args.finetune:
        for name in MODELS if args.finetune == "all" else [args.finetune]:
            kfold_finetune(data, name, args.folds)
    else:
        compare_methods(data)

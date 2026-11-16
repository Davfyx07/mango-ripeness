"""Topic 5: ensembles con los 5 modelos ya entrenados. Es el único script que usa el test.
Uso:  python src/ensemble.py      (antes hay que correr: python src/train.py --all)

Cada modelo da 3 probabilidades por foto. Un ensemble promedia las de varios modelos (soft voting)
y se queda con la clase de mayor probabilidad promedio.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from config import CLASSES, OUTPUTS_DIR
from dataset import load_split
from models import CNNS, MODELS, TRANSFORMERS
from train import load_model, predict

if __name__ == "__main__":
    test = load_split("test")
    y = test["label_idx"].values
    probs = {name: predict(load_model(name), test) for name in MODELS}

    def average(names):
        return np.mean([probs[name] for name in names], axis=0)

    candidates = {name: probs[name] for name in MODELS}                  # cada modelo solo
    candidates["Homogéneo: 3 CNN"] = average(CNNS)                        # solo modelos del mismo tipo
    candidates["Homogéneo: 2 Transformers"] = average(TRANSFORMERS)
    candidates["Heterogéneo: los 5"] = average(MODELS)                    # tipos distintos, un voto cada uno
    candidates["Híbrido: CNN + Transformers"] = (average(CNNS) + average(TRANSFORMERS)) / 2  # ensemble de ensembles

    rows = []
    for name, p in candidates.items():
        pred = p.argmax(1)
        rows.append({"modelo": name, "accuracy": accuracy_score(y, pred),
                     "f1_macro": f1_score(y, pred, average="macro"), "errores": int((pred != y).sum())})
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUTS_DIR / "ensemble_results.csv", index=False)
    print(f"Resultados en test ({len(test)} fotos)")
    print(table.to_string(index=False, float_format="%.3f"))

    best = table.loc[table["accuracy"].idxmax(), "modelo"]
    pred = candidates[best].argmax(1)
    print(f"\nDetalle del mejor: {best}")
    print(classification_report(y, pred, target_names=CLASSES, digits=3))
    print("Matriz de confusión (filas = clase real, columnas = predicción):")
    print(pd.DataFrame(confusion_matrix(y, pred), index=CLASSES, columns=CLASSES))

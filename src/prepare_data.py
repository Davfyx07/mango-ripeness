"""Topic 1: limpia el dataset, agrupa las fotos por mango, parte 70/15/15 y guarda los CSV.
Uso:  python src/prepare_data.py
"""
import hashlib
import io
import re
from datetime import datetime

import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from sklearn.model_selection import StratifiedGroupKFold

from config import CLASSES, GROUP_GAP_S, PROCESSED_DIR, RAW_DIR, SEED, SPLITS_DIR, STORE_SIZE


def scan_and_resize():
    """Lee cada foto original una sola vez: saca sus datos y guarda la copia reducida."""
    rows = []
    for path in sorted(RAW_DIR.glob("*/*.JPG")):
        label = path.parent.name.lower()                    # "pArtially_ripe" -> "partially_ripe"
        assert label in CLASSES, f"carpeta inesperada: {path.parent.name}"
        data = path.read_bytes()
        img = Image.open(io.BytesIO(data))
        exif = img.getexif()
        taken = exif.get_ifd(0x8769)[0x9003]                # EXIF DateTimeOriginal: cuándo se tomó la foto
        numbered = re.fullmatch(r"(\d+)\(\d+\)", path.stem)  # "860(2)" -> mango 860

        img.draft("RGB", (STORE_SIZE * 2, STORE_SIZE * 2))  # decodifica el JPEG ya reducido: mucho más rápido
        img = ImageOps.exif_transpose(img).convert("RGB")   # endereza la foto si la cámara la guardó girada
        scale = STORE_SIZE / min(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        file = f"{label}/{path.stem}.jpg"
        (PROCESSED_DIR / label).mkdir(parents=True, exist_ok=True)
        img.save(PROCESSED_DIR / file, quality=95)

        rows.append({
            "file": file,
            "label": label,
            "md5": hashlib.md5(data).hexdigest(),           # huella del archivo: dos fotos idénticas dan el mismo md5
            "taken": datetime.strptime(taken, "%Y:%m:%d %H:%M:%S"),
            "camera": exif[0x0110],                         # modelo de cámara
            "number": numbered.group(1) if numbered else None,
        })
    return pd.DataFrame(rows)


def drop_duplicates(df):
    """La misma foto exacta en dos clases tiene etiqueta dudosa: se quitan las dos."""
    n_labels = df.groupby("md5")["label"].transform("nunique")
    kept = df[n_labels == 1].drop_duplicates("md5")
    for file in sorted(set(df["file"]) - set(kept["file"])):
        print("  quitada:", file)
        (PROCESSED_DIR / file).unlink()
    return kept


def add_mango_id(df):
    """Agrupa las fotos que son (o pueden ser) del mismo mango. El grupo es lo que se reparte entre splits."""
    df = df.sort_values(["camera", "taken"]).reset_index(drop=True)
    gap = df.groupby("camera")["taken"].diff().dt.total_seconds()
    chain = (gap.isna() | (gap > GROUP_GAP_S)).cumsum()     # cadena nueva si cambia la cámara o pasan > 120 s
    group = chain.copy()
    while True:  # une las cadenas que comparten número de mango, hasta que ya nada cambie
        new = group.groupby(df["number"]).transform("min").fillna(group)
        new = new.groupby(chain).transform("min")
        if (new == group).all():
            break
        group = new
    df["mango_id"] = group.astype(int)
    return df


def add_split(df):
    """70/15/15 repartiendo grupos enteros y manteniendo la proporción de clases en cada parte."""
    df = df.sort_values("file").reset_index(drop=True)
    cv = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=SEED)  # 20 partes de ~5% cada una
    part = np.zeros(len(df), dtype=int)
    for i, (_, idx) in enumerate(cv.split(df, df["label"], df["mango_id"])):
        part[idx] = i                                                        # en qué parte cayó cada foto
    df["split"] = np.where(part < 3, "test", np.where(part < 6, "val", "train"))  # 3 partes = 15%
    return df


if __name__ == "__main__":
    print("1) Leyendo y reduciendo fotos (tarda 1-2 minutos)...")
    df = scan_and_resize()
    print(f"   {len(df)} fotos")
    print("2) Quitando duplicados...")
    df = drop_duplicates(df)
    print("3) Agrupando por mango...")
    df = add_mango_id(df)
    print(f"   {len(df)} fotos en {df['mango_id'].nunique()} grupos")
    print("4) Partiendo 70/15/15...")
    df = add_split(df)
    df["label_idx"] = df["label"].map(CLASSES.index)

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["train", "val", "test"]:
        part = df[df["split"] == name].sort_values("file")
        part[["file", "label", "label_idx", "mango_id"]].to_csv(SPLITS_DIR / f"{name}.csv", index=False)

    # Autochequeo: ningún grupo puede estar en dos splits (eso sería data leakage)
    assert (df.groupby("mango_id")["split"].nunique() == 1).all(), "hay un mango en dos splits"
    print(pd.crosstab(df["label"], df["split"], margins=True)[["train", "val", "test", "All"]])
    print((df["split"].value_counts(normalize=True) * 100).round(1).to_string())

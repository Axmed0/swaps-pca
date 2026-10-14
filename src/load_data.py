"""Convert the raw curve pickles (dict of tenor -> {'rate': DataFrame}) into one CSV per currency.

Pickle files can run arbitrary code when loaded, so this uses a restricted unpickler that only
allows the pandas/numpy classes a plain DataFrame needs. Anything else raises an error.

Usage: python src/load_data.py path/to/usd_sofr_curve.p path/to/eur_estr_curve.p path/to/gbp_sonia_curve.p
"""
import importlib
import pickle
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TENORS = ["1w", "2w", "3w", "1m", "2m", "3m", "6m", "9m", "1y", "18m", "2y", "3y", "4y", "5y", "6y", "7y",
          "8y", "9y", "10y", "11y", "12y", "15y", "20y", "25y", "30y", "35y", "40y", "45y", "50y"]
ALLOWED = {
    ("pandas.core.frame", "DataFrame"), ("pandas.core.internals.managers", "BlockManager"),
    ("pandas._libs.internals", "_unpickle_block"), ("numpy._core.numeric", "_frombuffer"), ("numpy", "dtype"),
    ("builtins", "slice"), ("pandas.core.indexes.base", "_new_Index"), ("pandas.core.indexes.base", "Index"),
    ("numpy._core.multiarray", "_reconstruct"), ("numpy", "ndarray"),
    ("pandas.core.indexes.datetimes", "_new_DatetimeIndex"), ("pandas.core.indexes.datetimes", "DatetimeIndex"),
    ("pandas._libs.arrays", "__pyx_unpickle_NDArrayBacked"), ("pandas.core.arrays.datetimes", "DatetimeArray"),
}


class SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in ALLOWED:
            raise pickle.UnpicklingError(f"blocked: {module}.{name}")
        return getattr(importlib.import_module(module), name)


def main(paths):
    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    for p in paths:
        ccy = next(c for c in ("usd", "eur", "gbp") if c in Path(p).name.lower())
        with open(p, "rb") as f:
            raw = SafeUnpickler(f).load()
        df = pd.DataFrame({k: v["rate"].iloc[:, 0] for k, v in raw.items()})
        df = df[[t for t in TENORS if t in df.columns]].sort_index()
        df.index.name = "date"
        df.to_csv(out / f"{ccy}_swap_curve.csv", float_format="%.6f")
        print(f"{ccy.upper()}: {len(df)} days {df.index.min().date()} to {df.index.max().date()}, {df.shape[1]} tenors")


if __name__ == "__main__":
    main(sys.argv[1:])

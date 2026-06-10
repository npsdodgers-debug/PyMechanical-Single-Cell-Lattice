"""
run_ml.py

Entry point for the SHM classification pipeline.
Auto-discovers sweep CSVs for each case, builds the feature matrix, trains, and evaluates.

Folder layout:
    Single Cell Lattice/
        Healthy/
            Sweep/                  ← healthy_*_complex.csv
        Missing_Upper_Strut/
            Sweep/                  ← damaged_*_complex.csv
        Missing_Lower_Strut/        ← future
            Sweep/
        shm_dataset.csv

Adding a new damage case:
    1. Create the folder and run the sweep
    2. Add one line to CASES below
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from dataset    import build_dataset, save_dataset
from classifier import train, evaluate

# ── Data paths ────────────────────────────────────────────────────────────────
DATA_DIR    = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice"
DATASET_CSV = os.path.join(DATA_DIR, "shm_dataset.csv")

# ── Case definitions ──────────────────────────────────────────────────────────
# folder_name : label_int  (0 = healthy, 1+ = damage cases)
CASES = {
    "Healthy":              0,
    "Missing_Upper_Strut":  1,
    "Missing_Lower_Strut":  2,
}

# ── Force location per excitation label (mm) ──────────────────────────────────
FORCE_Z = 31.5
FORCE_LOCATIONS = {
    # Corners
    "center":               (15.0,  -15.0, FORCE_Z),
    "corner(0,0)":          ( 0.0,    0.0, FORCE_Z),
    "corner(0.03,0)":       (30.0,    0.0, FORCE_Z),
    "corner(0,-0.03)":      ( 0.0,  -30.0, FORCE_Z),
    "corner(0.03,-0.03)":   (30.0,  -30.0, FORCE_Z),
    # Edge midpoints
    "edge(15,0)":           (15.0,    0.0, FORCE_Z),
    "edge(0,-15)":          ( 0.0,  -15.0, FORCE_Z),
    "edge(30,-15)":         (30.0,  -15.0, FORCE_Z),
    "edge(15,-30)":         (15.0,  -30.0, FORCE_Z),
}
DEFAULT_FORCE = (10.0, -10.0, FORCE_Z)

# ── Feature extraction settings ───────────────────────────────────────────────
N_PEAKS  = 5
MIN_FREQ = 500.0

# ── FRF extraction method ─────────────────────────────────────────────────────
# 'pipeline'         — driving point node (node closest to force location)
# 'averaged'         — spatial average across all nodes
# 'averaged_top_face'— spatial average across top face nodes only (use for PSV comparison)
CSV_TYPE = 'averaged'


def _force(label):
    fx, fy, fz = FORCE_LOCATIONS.get(label, DEFAULT_FORCE)
    return dict(force_x_mm=fx, force_y_mm=fy, force_z_mm=fz)


def discover_samples():
    samples = []

    for case_name, label in CASES.items():
        sweep_dir = os.path.join(DATA_DIR, case_name, "Sweep")
        if not os.path.isdir(sweep_dir):
            print(f"  [{case_name}] No Sweep folder found — skipping")
            continue

        csvs = sorted([f for f in os.listdir(sweep_dir) if f.endswith("_complex.csv")])
        if not csvs:
            print(f"  [{case_name}] Sweep folder empty — skipping")
            continue

        for fname in csvs:
            # Extract excitation label from filename (e.g. healthy_center_complex.csv → center)
            exc_label = fname.replace("healthy_", "").replace("damaged_", "").replace("_complex.csv", "")
            samples.append({
                'csv_path' : os.path.join(sweep_dir, fname),
                'label'    : label,
                'csv_type' : CSV_TYPE,
                **_force(exc_label),
                'meta'     : {'case': case_name, 'excitation': exc_label},
            })

        print(f"  [{case_name}] {len(csvs)} CSV(s) found  (label={label})")

    return samples


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("── Discovering samples ───────────────────────────────────────────")
    samples = discover_samples()
    print(f"\nTotal samples found: {len(samples)}")

    if len(samples) == 0:
        print("No samples found — check folder structure and CASES dict.")
        sys.exit(1)

    # Build int→name map from CASES (e.g. {0: 'Healthy', 1: 'Missing_Upper_Strut', ...})
    label_int_to_name = {v: k for k, v in CASES.items()}

    print("\n── Building dataset ──────────────────────────────────────────────")
    X, y, meta = build_dataset(samples, n_peaks=N_PEAKS, min_freq=MIN_FREQ,
                                label_names=label_int_to_name)

    print(f"\nSamples: {len(y)}  |  Features: {X.shape[1]}")
    for case, label in CASES.items():
        print(f"  {case}: {int((y == label).sum())} samples")
    print("\nFeature table:")
    print(X.to_string())

    save_dataset(X, y, DATASET_CSV, label_names=label_int_to_name)

    print("\n── Training & evaluation ─────────────────────────────────────────")
    if len(np.unique(y)) < 2:
        print("Only one class found — collect data for more cases.")
    elif int(np.min(np.bincount(y))) < 2:
        print("Not enough samples for LOO cross-validation (need ≥2 per class).")
        print("Fitting model on all data — collect more samples to evaluate properly.")
        train(X, y, model='rf')
    else:
        label_names = [k for k, _ in sorted(CASES.items(), key=lambda x: x[1])]
        evaluate(X, y, model='rf', label_names=label_names)

    print("\n── Done ──────────────────────────────────────────────────────────")

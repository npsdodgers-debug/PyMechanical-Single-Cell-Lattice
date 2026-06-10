"""
dataset.py

Aggregates FRF CSV files into a labeled feature matrix for ML training.

Adding a new sample = appending one dict to the SAMPLES list:
    {
        'csv_path'  : str,
        'label'     : 0 (healthy) or 1 (defective),
        'csv_type'  : 'pipeline' | 'simple',   # default: 'pipeline'
        'force_x_mm': float,                    # only for pipeline type
        'force_y_mm': float,
        'force_z_mm': float,
        'meta'      : dict,                     # optional — stored but not used as features
    }

For localization (future): add 'defect_location' key to each defective sample.
"""

import numpy as np
import pandas as pd

from features import (
    load_frf_pipeline,
    load_frf_averaged,
    load_frf_simple,
    extract_features,
    N_PEAKS_DEFAULT,
    MIN_FREQ_DEFAULT,
    PROMINENCE_FRAC,
)

# Default force location (driving point) in mm
DEFAULT_FORCE = {'force_x_mm': 10.0, 'force_y_mm': -10.0, 'force_z_mm': 31.5}

def build_dataset(samples, n_peaks=N_PEAKS_DEFAULT,
                  min_freq=MIN_FREQ_DEFAULT,
                  prominence_frac=PROMINENCE_FRAC,
                  label_names=None):
    """
    Build feature matrix X and label vector y from a list of sample dicts.

    Returns
    -------
    X : pd.DataFrame   — feature matrix (n_samples × n_features)
    y : np.ndarray     — integer labels
    meta : list[dict]  — per-sample metadata (csv_path, label name, etc.)
    """
    rows   = []
    labels = []
    meta   = []

    for s in samples:
        csv_type = s.get('csv_type', 'pipeline')

        if csv_type == 'pipeline':
            fx = s.get('force_x_mm', DEFAULT_FORCE['force_x_mm'])
            fy = s.get('force_y_mm', DEFAULT_FORCE['force_y_mm'])
            fz = s.get('force_z_mm', DEFAULT_FORCE['force_z_mm'])
            freqs, amp = load_frf_pipeline(s['csv_path'], fx, fy, fz)
        elif csv_type == 'averaged':
            freqs, amp = load_frf_averaged(s['csv_path'])
        elif csv_type == 'averaged_top_face':
            freqs, amp = load_frf_averaged(s['csv_path'], top_face_only=True)
        else:
            freqs, amp = load_frf_simple(s['csv_path'])

        feats = extract_features(freqs, amp, n_peaks=n_peaks,
                                 min_freq=min_freq,
                                 prominence_frac=prominence_frac)
        rows.append(feats)
        labels.append(s['label'])
        name = (label_names or {}).get(s['label'], str(s['label']))
        meta.append({
            'csv_path'   : s['csv_path'],
            'label_int'  : s['label'],
            'label_name' : name,
            **s.get('meta', {}),
        })

    X = pd.DataFrame(rows)
    y = np.array(labels, dtype=int)
    return X, y, meta


def save_dataset(X, y, path, label_names=None):
    df          = X.copy()
    df['label'] = y
    df.to_csv(path, index=False)
    lmap   = label_names or {}
    counts = {lmap.get(k, str(k)): v for k, v in zip(*np.unique(y, return_counts=True))}
    print(f"Saved {path}  |  {len(df)} samples, {len(X.columns)} features  |  {counts}")


def load_dataset(path):
    df = pd.read_csv(path)
    y  = df.pop('label').values.astype(int)
    return df, y

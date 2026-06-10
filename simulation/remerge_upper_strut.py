"""
remerge_upper_strut.py

Re-merges the upper strut real + APDL imaginary CSVs using coordinates from
the APDL file (mm) instead of the DPF real file (meters).  Run this once to
fix the existing 3 complex CSVs without re-opening Mechanical.

Usage:
    python simulation/remerge_upper_strut.py
"""

import os
import pandas as pd
import numpy as np

SWEEP_DIR = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Missing_Upper_Strut\Sweep"

LOCATIONS = [
    ("center",          "damaged_center"),
    ("corner(0,0)",     "damaged_corner(0,0)"),
    ("corner(0.03,0)",  "damaged_corner(0.03,0)"),
]

for label, stem in LOCATIONS:
    real_path    = os.path.join(SWEEP_DIR, f"{stem}_real.csv")
    imag_path    = os.path.join(SWEEP_DIR, f"{stem}_imag_apdl.csv")
    complex_path = os.path.join(SWEEP_DIR, f"{stem}_complex.csv")

    if not os.path.exists(real_path):
        print(f"[{label}] SKIP — real CSV not found: {real_path}")
        continue
    if not os.path.exists(imag_path):
        print(f"[{label}] SKIP — APDL imag CSV not found: {imag_path}")
        continue

    real_df = pd.read_csv(real_path)
    imag_df = pd.read_csv(imag_path, skiprows=1, header=None, sep=',',
                          names=['freq_Hz','node_id','x','y','z','ux_imag','uy_imag','uz_imag'])
    imag_df = imag_df.apply(lambda col: pd.to_numeric(col.astype(str).str.strip(), errors='coerce'))
    imag_df = imag_df.dropna(subset=['freq_Hz','node_id'])

    real_freqs = sorted(real_df['freq_Hz'].unique())
    imag_freqs = sorted(imag_df['freq_Hz'].dropna().unique())
    freq_map   = {rf: min(imag_freqs, key=lambda x: abs(x - rf)) for rf in real_freqs}

    rows = []
    for real_freq, imag_freq in freq_map.items():
        r  = real_df[real_df['freq_Hz'] == real_freq].set_index('node_id')
        im = imag_df[abs(imag_df['freq_Hz'] - imag_freq) < 0.01].set_index('node_id')
        r_vals = r.drop(columns=['x', 'y', 'z'])
        merged = r_vals.join(im[['x', 'y', 'z', 'ux_imag', 'uy_imag', 'uz_imag']], how='inner')
        merged['freq_Hz'] = real_freq
        rows.append(merged.reset_index())

    if not rows:
        print(f"[{label}] ERROR — no rows after merge; check that node IDs overlap")
        continue

    combined = pd.concat(rows, ignore_index=True)
    combined = combined[['freq_Hz','node_id','x','y','z',
                          'ux_real','uy_real','uz_real',
                          'ux_imag','uy_imag','uz_imag']]
    combined.to_csv(complex_path, index=False)

    # Sanity check: print coordinate range
    coords = combined.groupby('node_id')[['x','y','z']].first()
    print(f"[{label}] OK — {len(combined):,} rows | "
          f"X {coords['x'].min():.1f}..{coords['x'].max():.1f}  "
          f"Y {coords['y'].min():.1f}..{coords['y'].max():.1f}  "
          f"Z {coords['z'].min():.1f}..{coords['z'].max():.1f}  mm")

print("\nDone.  Re-run run_ml.py to check updated features.")

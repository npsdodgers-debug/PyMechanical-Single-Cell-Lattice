"""
plot_lattice_frf.py

Plots the FRF from the PyMechanical simulation pipeline output.
Reads: nodal_displacement_complex.csv  (freq_Hz, node_id, x, y, z,
                                         ux_real, uy_real, uz_real,
                                         ux_imag, uy_imag, uz_imag)
       modal_frequencies.json          (optional — overlays mode lines)
"""

import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR    = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice"
CSV_NAME    = "nodal_displacement_complex.csv"
MODAL_JSON  = "modal_frequencies.json"
OUTPUT_FILE = os.path.join(DATA_DIR, "lattice_frf.png")

# Force application point in mm (matches healthy_run.py force_x/y/z_m × 1000)
FORCE_X_MM =  10.0
FORCE_Y_MM = -10.0
FORCE_Z_MM =  31.5

# ── Load CSV ──────────────────────────────────────────────────────────────────
csv_path = os.path.join(DATA_DIR, CSV_NAME)
df = pd.read_csv(csv_path)
print(f"Loaded: {len(df)} rows  |  nodes: {df['node_id'].nunique()}  |  "
      f"freqs: {df['freq_Hz'].nunique()}")

# ── Pick the node closest to the force application point ─────────────────────
node_coords = df.groupby('node_id')[['x', 'y', 'z']].first()
dist = np.sqrt(
    (node_coords['x'] - FORCE_X_MM)**2 +
    (node_coords['y'] - FORCE_Y_MM)**2 +
    (node_coords['z'] - FORCE_Z_MM)**2
)
best_node = dist.idxmin()
node_df   = df[df['node_id'] == best_node].sort_values('freq_Hz')

nx, ny, nz = node_df[['x', 'y', 'z']].iloc[0]
print(f"Closest node to force ({FORCE_X_MM}, {FORCE_Y_MM}, {FORCE_Z_MM}) mm:")
print(f"  Node {best_node}  at  ({nx:.4f}, {ny:.4f}, {nz:.4f}) mm  dist={dist[best_node]:.4f} mm")

freqs    = node_df['freq_Hz'].values
uz_real  = node_df['uz_real'].values * 1e3   # m → mm
uz_imag  = node_df['uz_imag'].values * 1e3
amp      = np.sqrt(uz_real**2 + uz_imag**2)
real_db  = 20 * np.log10(np.maximum(np.abs(uz_real), 1e-12))
imag_db  = 20 * np.log10(np.maximum(np.abs(uz_imag), 1e-12))
phase    = np.degrees(np.arctan2(uz_imag, uz_real))

# ── Load modal frequencies ────────────────────────────────────────────────────
modal_freqs = []
modal_path  = os.path.join(DATA_DIR, MODAL_JSON)
if os.path.exists(modal_path):
    with open(modal_path) as f:
        modal_freqs = json.load(f)["frequencies_hz"]
    print(f"Modal frequencies: {[round(m, 1) for m in modal_freqs]} Hz")


# ── Plot ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
fig.suptitle(
    f"Single-Cell Lattice — Harmonic FRF (Z-direction)\n"
    f"Node {best_node}  ({nx:.3f}, {ny:.3f}, {nz:.3f}) mm",
    fontsize=12
)

# Amplitude (log scale)
axes[0].semilogy(freqs, amp, color='darkgreen', linewidth=1.2, label='FRF amplitude')
for mf in modal_freqs:
    axes[0].axvline(mf, color='gray', linewidth=1.0, linestyle='--', alpha=0.7)
if modal_freqs:
    axes[0].axvline(modal_freqs[0], color='gray', linewidth=1.0,
                    linestyle='--', alpha=0.7, label='Modal freq')
axes[0].set_ylabel("Amplitude (mm, log)")
axes[0].set_title("Magnitude")
axes[0].legend(fontsize=8)
axes[0].grid(True, which='both', alpha=0.3)

# Real and Imaginary (dB of absolute value)
axes[1].plot(freqs, real_db, color='steelblue', linewidth=1.2, label='Real')
axes[1].plot(freqs, imag_db, color='darkorange', linewidth=1.2, label='Imaginary')
for mf in modal_freqs:
    axes[1].axvline(mf, color='gray', linewidth=1.0, linestyle='--', alpha=0.5)
axes[1].set_ylabel("Displacement (dB re 1 mm/N)")
axes[1].set_title("Real and Imaginary parts (|·| in dB)")
axes[1].legend(fontsize=8)
axes[1].grid(True, alpha=0.3)

# Phase
axes[2].plot(freqs, phase, color='purple', linewidth=1.2)
for mf in modal_freqs:
    axes[2].axvline(mf, color='gray', linewidth=1.0, linestyle='--', alpha=0.5)
axes[2].axhline( 90, color='gray', linewidth=0.5, linestyle=':', alpha=0.7)
axes[2].axhline(-90, color='gray', linewidth=0.5, linestyle=':', alpha=0.7)
axes[2].set_ylim(-10, 180)
axes[2].set_ylabel("Phase (deg)")
axes[2].set_xlabel("Frequency (Hz)")
axes[2].set_title("Phase angle")
axes[2].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_FILE, dpi=150)
print(f"\nPlot saved to: {OUTPUT_FILE}")
plt.show()

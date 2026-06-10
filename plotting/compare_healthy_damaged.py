"""
compare_healthy_damaged.py

Overlays healthy vs damaged (missing strut) FRFs at the same excitation point.
Both CSVs must be from the same force location and frequency range for a
meaningful comparison.
"""

import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
HEALTHY_CSV  = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Healthy\Sweep\healthy_center_complex.csv"
# To compare a different excitation point, change "center" to any of:
# corner(0,0), corner(0.03,0), corner(0,-0.03), corner(0.03,-0.03),
# edge(15,0), edge(0,-15), edge(30,-15), edge(15,-30)
DAMAGED_CSV  = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Missing_Lower_Strut\Sweep\damaged_center_complex.csv"

HEALTHY_MODAL = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Healthy\modal_frequencies.json"
DAMAGED_MODAL = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Missing_Lower_Strut\modal_frequencies.json"

OUTPUT_FILE  = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\healthy_vs_lower_strut.png"

# Force location in mm — center of top face
FORCE_X_MM =  15.0
FORCE_Y_MM = -15.0
FORCE_Z_MM =  31.5

# ── Helper: load CSV and extract driving point FRF ────────────────────────────
def load_frf(csv_path, fx, fy, fz):
    df = pd.read_csv(csv_path)
    node_coords = df.groupby('node_id')[['x', 'y', 'z']].first()
    max_abs = node_coords.abs().max().max()
    if 0 < max_abs < 1.0:
        node_coords = node_coords * 1000.0
    dist = np.sqrt(
        (node_coords['x'] - fx)**2 +
        (node_coords['y'] - fy)**2 +
        (node_coords['z'] - fz)**2
    )
    best_node = dist.idxmin()
    node_df   = df[df['node_id'] == best_node].sort_values('freq_Hz')
    nx, ny, nz = node_df[['x', 'y', 'z']].iloc[0]
    print(f"  Node {best_node} at ({nx:.2f}, {ny:.2f}, {nz:.2f}) mm  dist={dist[best_node]:.2f} mm")

    freqs   = node_df['freq_Hz'].values
    uz_real = node_df['uz_real'].values * 1e3
    uz_imag = node_df['uz_imag'].values * 1e3
    amp     = np.sqrt(uz_real**2 + uz_imag**2)
    phase   = np.degrees(np.arctan2(uz_imag, uz_real))
    return freqs, amp, phase

# ── Load ──────────────────────────────────────────────────────────────────────
print("Healthy:")
h_freqs, h_amp, h_phase = load_frf(HEALTHY_CSV,  FORCE_X_MM, FORCE_Y_MM, FORCE_Z_MM)
print("Damaged:")
d_freqs, d_amp, d_phase = load_frf(DAMAGED_CSV, FORCE_X_MM, FORCE_Y_MM, FORCE_Z_MM)

# ── Load modal frequencies ────────────────────────────────────────────────────
def load_modal(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)["frequencies_hz"]
    return []

h_modal = load_modal(HEALTHY_MODAL)
d_modal = load_modal(DAMAGED_MODAL)
print(f"Healthy modal:  {[round(f, 1) for f in h_modal]} Hz")
print(f"Damaged modal:  {[round(f, 1) for f in d_modal]} Hz")

# ── Plot ──────────────────────────────────────────────────────────────────────
plt.rcParams.update({'font.size': 14})

fig, ax = plt.subplots(1, 1, figsize=(12, 5))
fig.suptitle("Single-Cell Lattice — Healthy vs Missing Lower Strut (Z-direction)", fontsize=16)

ax.semilogy(h_freqs, h_amp, color='steelblue',  linewidth=1.4, label='Healthy')
ax.semilogy(d_freqs, d_amp, color='darkorange', linewidth=1.4, label='Missing lower strut', linestyle='--')
# for mf in h_modal:
#     ax.axvline(mf, color='steelblue',  linewidth=0.7, linestyle=':', alpha=0.5)
# for mf in d_modal:
#     ax.axvline(mf, color='darkorange', linewidth=0.7, linestyle=':', alpha=0.5)
ax.set_xlim(500, 3500)
ax.set_ylabel("Amplitude (mm, log)", fontsize=15)
ax.set_xlabel("Frequency (Hz)", fontsize=15)
ax.set_title("Magnitude", fontsize=15)
ax.tick_params(axis='both', labelsize=13)
ax.legend(fontsize=13)
ax.grid(True, which='both', alpha=0.3)

# ── Phase angle (commented out) ───────────────────────────────────────────────
# axes[1].plot(h_freqs, h_phase, color='steelblue',  linewidth=1.4, label='Healthy')
# axes[1].plot(d_freqs, d_phase, color='darkorange', linewidth=1.4, label='Missing strut', linestyle='--')
# axes[1].set_ylim(-180, 180)
# axes[1].axhline( 90, color='gray', linewidth=0.5, linestyle=':', alpha=0.7)
# axes[1].axhline(-90, color='gray', linewidth=0.5, linestyle=':', alpha=0.7)
# axes[1].set_ylabel("Phase (deg)")
# axes[1].set_xlabel("Frequency (Hz)")
# axes[1].set_title("Phase angle")
# axes[1].legend(fontsize=9)
# axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_FILE, dpi=150)
print(f"\nPlot saved to: {OUTPUT_FILE}")
plt.show()

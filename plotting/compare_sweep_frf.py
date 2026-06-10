"""
compare_sweep_frf.py

Overlays FRFs from all excitation locations in the Sweep folder.
Reads all healthy_*_complex.csv files automatically — no changes needed
when new locations are added.
Node selection: closest to the force location defined per CSV filename
(falls back to highest mean Z-amplitude if coordinates not in FORCE_LOCATIONS).
"""

import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
SWEEP_DIR   = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Sweep"
MODAL_JSON  = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Sweep\modal_frequencies.json"
OUTPUT_FILE = os.path.join(SWEEP_DIR, "sweep_frf_comparison.png")

# Force location per label in mm — add corners here as you fill them in
FORCE_LOCATIONS = {
    "center":  (10.0,  -10.0, 31.5),
    "corner(0,0)": (0.0,  0.0, 31.5),  # update when corner coords are known
    "corner(0.03,0)": (30.0,  0.0, 31.5),  # update when corner coords are known
    "corner(0,0.03)": (0.0,  -30.0, 31.5),  # update when corner coords are known
    "corner(0.03,0.03)": (30.0,  -30.0, 31.5),  # update when corner coords are known
}

# ── Find all sweep CSVs ───────────────────────────────────────────────────────
csv_files = sorted([
    f for f in os.listdir(SWEEP_DIR)
    if f.startswith("healthy_") and f.endswith("_complex.csv")
])
print(f"Found {len(csv_files)} sweep CSVs: {csv_files}")

# ── Load modal frequencies ────────────────────────────────────────────────────
modal_freqs = []
if os.path.exists(MODAL_JSON):
    with open(MODAL_JSON) as f:
        modal_freqs = json.load(f)["frequencies_hz"]
    print(f"Modal frequencies: {[round(m, 1) for m in modal_freqs]} Hz")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
fig.suptitle("Single-Cell Lattice — FRF Sweep Comparison (Z-direction)", fontsize=13)

colors = plt.cm.tab10(np.linspace(0, 1, max(len(csv_files), 1)))

for idx, fname in enumerate(csv_files):
    # Extract label from filename: healthy_<label>_complex.csv
    label = fname.replace("healthy_", "").replace("_complex.csv", "")

    df = pd.read_csv(os.path.join(SWEEP_DIR, fname))

    # Find closest node to force location
    fx, fy, fz = FORCE_LOCATIONS.get(label, (10.0, -10.0, 31.5))
    node_coords = df.groupby('node_id')[['x', 'y', 'z']].first()
    dist = np.sqrt(
        (node_coords['x'] - fx)**2 +
        (node_coords['y'] - fy)**2 +
        (node_coords['z'] - fz)**2
    )
    best_node = dist.idxmin()
    node_df   = df[df['node_id'] == best_node].sort_values('freq_Hz')

    nx, ny, nz = node_df[['x', 'y', 'z']].iloc[0]
    print(f"  [{label}] node {best_node} at ({nx:.2f}, {ny:.2f}, {nz:.2f}) mm  dist={dist[best_node]:.2f} mm")

    freqs   = node_df['freq_Hz'].values
    uz_real = node_df['uz_real'].values * 1e3
    uz_imag = node_df['uz_imag'].values * 1e3
    amp   = np.sqrt(uz_real**2 + uz_imag**2)
    phase = np.degrees(np.arctan2(uz_imag, uz_real))

    c = colors[idx]
    axes[0].semilogy(freqs, amp,  color=c, linewidth=1.2, label=label)
    axes[1].plot(freqs, phase,    color=c, linewidth=1.2, label=label)

# Modal frequency lines on all panels
for mf in modal_freqs:
    for ax in axes:
        ax.axvline(mf, color='gray', linewidth=0.8, linestyle='--', alpha=0.5)

# Formatting
axes[0].set_ylabel("Amplitude (mm, log)")
axes[0].set_title("Magnitude")
axes[0].legend(fontsize=8)
axes[0].grid(True, which='both', alpha=0.3)

axes[0].set_xlim(500, 3500)
axes[1].set_ylim(-180, 180)
axes[1].axhline( 90, color='gray', linewidth=0.5, linestyle=':', alpha=0.7)
axes[1].axhline(-90, color='gray', linewidth=0.5, linestyle=':', alpha=0.7)
axes[1].set_ylabel("Phase (deg)")
axes[1].set_xlabel("Frequency (Hz)")
axes[1].set_title("Phase angle")
axes[1].legend(fontsize=8)
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_FILE, dpi=150)
print(f"\nPlot saved to: {OUTPUT_FILE}")
plt.show()

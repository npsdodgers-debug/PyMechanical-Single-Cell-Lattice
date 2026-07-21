"""
compare_two_psv.py

Overlays two Polytec PSV experimental FRFs (e.g. two excitation points,
or healthy vs damaged scans) directly against each other — no simulation
data involved.

Reads:  Polytec PSV UNV files (H1 Displacement/Force, type 58 datasets)
        Averaged across all scan points (RMS magnitude) per file.
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyuff

# ── Config ────────────────────────────────────────────────────────────────────
PSV_FILE_1 = r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PolyTech PSV\BigLatticeHammerCenterEdge052726.unv"
LABEL_1    = "Center Edge"

PSV_FILE_2 = r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PolyTech PSV\BigLatticeHammerCorner052726.unv"
LABEL_2    = "Corner"

OUT_FILE   = r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PolyTech PSV\PSV_Comparison.png"
FREQ_MIN   = 1150.0
FREQ_MAX   = 2700.0

os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)


# ── Helper: load a PSV UNV file → averaged FRF (amplitude in mm) ──────────────
def load_psv(path, freq_min, freq_max):
    uff = pyuff.UFF(path)
    sets = uff.read_sets()

    all_freqs = None
    all_data = []
    for s in sets:
        if s.get('type') != 58:
            continue
        if 'H1 Displacement / Force' not in s.get('id2', ''):
            continue
        x = np.array(s['x'])
        data = np.array(s['data'])
        if all_freqs is None:
            all_freqs = x
        all_data.append(data)

    if not all_data:
        raise ValueError(f"No H1 Displacement/Force (type 58) sets found in {path}")

    print(f"  {os.path.basename(path)}: {len(all_data)} scan points")

    all_data = np.array(all_data)   # shape: (n_points, n_freqs)
    mag_avg  = np.sqrt(np.mean(np.abs(all_data) ** 2, axis=0))
    real_avg = np.mean(all_data.real, axis=0)
    imag_avg = np.mean(all_data.imag, axis=0)

    df = pd.DataFrame({
        'freq_Hz': all_freqs,
        'amplitude': mag_avg,
        'real': real_avg,
        'imag': imag_avg,
    }).sort_values('freq_Hz').reset_index(drop=True)

    # PSV exports in meters — convert to mm
    df['amplitude'] *= 1000
    df['real']      *= 1000
    df['imag']      *= 1000

    mask = (df['freq_Hz'] >= freq_min) & (df['freq_Hz'] <= freq_max)
    df = df[mask].reset_index(drop=True)

    df['phase_deg'] = np.degrees(np.arctan2(df['imag'], df['real']))

    print(f"    {len(df)} frequency bands, "
          f"{df['freq_Hz'].min():.1f} - {df['freq_Hz'].max():.1f} Hz")
    return df


# ── Load both PSV datasets ─────────────────────────────────────────────────────
print(f"Loading '{LABEL_1}':")
psv1 = load_psv(PSV_FILE_1, FREQ_MIN, FREQ_MAX)
print(f"Loading '{LABEL_2}':")
psv2 = load_psv(PSV_FILE_2, FREQ_MIN, FREQ_MAX)

# Normalize each to its own maximum within the trimmed window (shape comparison)
psv1_amp_norm = psv1['amplitude'] / psv1['amplitude'].max()
psv2_amp_norm = psv2['amplitude'] / psv2['amplitude'].max()

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(20, 5))
fig.suptitle(f"PSV Experiment Comparison: {LABEL_1} vs {LABEL_2}", fontsize=13)

# Normalized amplitude (shape comparison)
axes[0].semilogy(psv1['freq_Hz'], psv1_amp_norm, color='steelblue', linewidth=1.4,
                  label=f'PSV: {LABEL_1}')
axes[0].semilogy(psv2['freq_Hz'], psv2_amp_norm, color='darkorange', linewidth=1.4,
                  label=f'PSV: {LABEL_2}', linestyle='--')
axes[0].set_xlim(FREQ_MIN, FREQ_MAX)
axes[0].set_ylabel("Normalized Amplitude (log)")
axes[0].set_title("Shape Comparison (normalized)")
axes[0].legend()
axes[0].grid(True, which='both', alpha=0.3)
axes[0].set_xlabel("Frequency (Hz)")

# Absolute amplitude (mm)
axes[1].semilogy(psv1['freq_Hz'], psv1['amplitude'], color='steelblue', linewidth=1.4,
                  label=f'PSV: {LABEL_1}')
axes[1].semilogy(psv2['freq_Hz'], psv2['amplitude'], color='darkorange', linewidth=1.4,
                  label=f'PSV: {LABEL_2}', linestyle='--')
axes[1].set_xlim(FREQ_MIN, FREQ_MAX)
axes[1].set_ylabel("Amplitude (mm, log)")
axes[1].set_title("Absolute Amplitude")
axes[1].legend()
axes[1].grid(True, which='both', alpha=0.3)
axes[1].set_xlabel("Frequency (Hz)")

# Phase
axes[2].plot(psv1['freq_Hz'], psv1['phase_deg'], color='steelblue', linewidth=1.2,
             label=f'PSV: {LABEL_1}')
axes[2].plot(psv2['freq_Hz'], psv2['phase_deg'], color='darkorange', linewidth=1.2,
             label=f'PSV: {LABEL_2}', linestyle='--')
axes[2].set_xlim(FREQ_MIN, FREQ_MAX)
axes[2].set_ylim(-180, 180)
axes[2].axhline(90, color='gray', linewidth=0.5, linestyle=':', alpha=0.7)
axes[2].axhline(-90, color='gray', linewidth=0.5, linestyle=':', alpha=0.7)
axes[2].set_ylabel("Phase (deg)")
axes[2].set_title("Phase angle")
axes[2].legend()
axes[2].grid(True, alpha=0.3)
axes[2].set_xlabel("Frequency (Hz)")

plt.tight_layout()
plt.savefig(OUT_FILE, dpi=150)
print(f"\nPlot saved to: {OUT_FILE}")
plt.show()

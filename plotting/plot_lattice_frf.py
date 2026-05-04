"""
plot_lattice_frf.py

Plots the Frequency Response Function from a Mechanical probe export.
Input format (tab/csv with .xls extension from Mechanical):
  Frequency (Hz), Amplitude (mm), Phase Angle (deg), Real (mm), Imaginary (mm)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# ── Config ────────────────────────────────────────────────────────────────────
INPUT_FILE  = r"C:\Users\coetech\Documents\Lattice Z direction.xls"
OUTPUT_FILE = r"C:\Users\coetech\Documents\Lattice Z direction FRF.png"

# ── Load ──────────────────────────────────────────────────────────────────────
df = pd.read_csv(INPUT_FILE, sep=None, engine='python')
print(f"Loaded: {len(df)} frequency points")
print(f"  Range: {df['Frequency (Hz)'].min():.1f} - {df['Frequency (Hz)'].max():.1f} Hz")

freqs   = df['Frequency (Hz)'].values
amp     = df['Amplitude (mm)'].values
real    = df['Real (mm)'].values
imag    = df['Imaginary (mm)'].values
phase   = df['Phase Angle (deg)'].values

# ── Detect peaks ──────────────────────────────────────────────────────────────
peaks, _ = find_peaks(amp, height=0.001 * amp.max(), distance=3)
print(f"Peaks detected at: {freqs[peaks].round(1)} Hz")
for p in peaks:
    print(f"  {freqs[p]:.1f} Hz  amp={amp[p]:.4e} mm  phase={phase[p]:.1f} deg")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
fig.suptitle("Lattice Z Direction — Harmonic Response FRF", fontsize=13)

# Amplitude
axes[0].semilogy(freqs, amp, color='darkgreen', linewidth=1.2)
for p in peaks:
    axes[0].axvline(freqs[p], color='red', linewidth=0.8, alpha=0.6)
    axes[0].text(freqs[p], amp[p], f' {freqs[p]:.0f}', fontsize=8,
                 color='red', va='bottom')
axes[0].set_ylabel("Amplitude (mm, log)")
axes[0].set_title("Magnitude")
axes[0].grid(True, which='both', alpha=0.3)

# Real and Imaginary
axes[1].plot(freqs, real, color='steelblue', linewidth=1.2, label='Real')
axes[1].plot(freqs, imag, color='darkorange', linewidth=1.2, label='Imaginary')
axes[1].axhline(0, color='black', linewidth=0.5, linestyle='--')
for p in peaks:
    axes[1].axvline(freqs[p], color='red', linewidth=0.8, alpha=0.6)
axes[1].set_ylabel("Displacement (mm)")
axes[1].set_title("Real and Imaginary parts")
axes[1].legend()
axes[1].grid(True, alpha=0.3)

# Phase
axes[2].plot(freqs, phase, color='purple', linewidth=1.2)
for p in peaks:
    axes[2].axvline(freqs[p], color='red', linewidth=0.8, alpha=0.6)
axes[2].axhline(90,  color='gray', linewidth=0.5, linestyle='--', alpha=0.7)
axes[2].axhline(-90, color='gray', linewidth=0.5, linestyle='--', alpha=0.7)
axes[2].set_ylabel("Phase (deg)")
axes[2].set_xlabel("Frequency (Hz)")
axes[2].set_title("Phase angle (dashed lines at +/-90 deg)")
axes[2].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_FILE, dpi=150)
print(f"\nPlot saved to: {OUTPUT_FILE}")
plt.show()

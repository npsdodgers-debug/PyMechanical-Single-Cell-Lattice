"""
compare_lattice_psv.py

Compares the Mechanical simulation FRF against the Polytec PSV experimental FRF
for the lattice structure (Z-direction displacement / force).

Simulation:  Lattice Z direction2.xls (columns in meters, converted to mm)
Experiment:  Polytec PSV UNV file (H1 Displacement/Force, Z direction)
             Averaged across all scan points (RMS magnitude)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pyuff

# ── Config ────────────────────────────────────────────────────────────────────
EXCITATION_LABEL = "Center Edge"   # change this for each run — folder name and filename

BASE_DIR  = r"C:\Users\coetech\Documents\Ansys Mechanical\Excitation Location"
SIM_FILE  = rf"{BASE_DIR}\{EXCITATION_LABEL}\FRF\FRF249N.xls"
EXP_FILE  = r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PolyTech PSV\BigLatticeHammerCenterEdge052726.unv"
OUT_DIR   = rf"{BASE_DIR}\{EXCITATION_LABEL}\ScreenShots"
OUT_FILE  = rf"{OUT_DIR}\PSV_vs_Sim_{EXCITATION_LABEL}.png"
FREQ_MIN  = 1150.0
FREQ_MAX  = 2700.0

import os
os.makedirs(OUT_DIR, exist_ok=True)

# ── Load simulation ───────────────────────────────────────────────────────────
sim = pd.read_csv(SIM_FILE, sep=None, engine='python')
sim_freq = sim['Frequency (Hz)'].values
sim_amp  = sim['Amplitude (m)'].values * 1000
sim_real = sim['Real (m)'].values * 1000
sim_imag = sim['Imaginary (m)'].values * 1000
print(f"Simulation: {len(sim_freq)} points, "
      f"{sim_freq.min():.1f} - {sim_freq.max():.1f} Hz")

# ── Load PSV experimental data ────────────────────────────────────────────────
uff = pyuff.UFF(EXP_FILE)
sets = uff.read_sets()

# Collect all H1 Displacement/Force FRF sets (type 58)
# Each set = one scan point; average across all points per frequency
all_freqs = None
all_data  = []

for s in sets:
    if s.get('type') != 58:
        continue
    if 'H1 Displacement / Force' not in s.get('id2', ''):
        continue
    x    = np.array(s['x'])
    data = np.array(s['data'])
    if all_freqs is None:
        all_freqs = x
    all_data.append(data)

print(f"Found {len(all_data)} scan points in UNV file")

all_data  = np.array(all_data)   # shape: (n_points, n_freqs)
mag_avg   = np.sqrt(np.mean(np.abs(all_data)**2, axis=0))
real_avg  = np.mean(all_data.real, axis=0)
imag_avg  = np.mean(all_data.imag, axis=0)

freq_bands = [
    {'freq_Hz': f, 'amplitude': m, 'real': r, 'imag': im}
    for f, m, r, im in zip(all_freqs, mag_avg, real_avg, imag_avg)
]

exp = pd.DataFrame(freq_bands).sort_values('freq_Hz').reset_index(drop=True)

# Convert m to mm (PSV exports in meters)
exp['amplitude'] *= 1000
exp['real']      *= 1000
exp['imag']      *= 1000

print(f"Experiment: {len(exp)} frequency bands, "
      f"{exp['freq_Hz'].min():.1f} - {exp['freq_Hz'].max():.1f} Hz")

# Trim both datasets to the shared frequency window
sim_mask = (sim_freq >= FREQ_MIN) & (sim_freq <= FREQ_MAX)
sim_freq = sim_freq[sim_mask]
sim_amp  = sim_amp[sim_mask]
sim_real = sim_real[sim_mask]
sim_imag = sim_imag[sim_mask]

exp_mask = (exp['freq_Hz'] >= FREQ_MIN) & (exp['freq_Hz'] <= FREQ_MAX)
exp      = exp[exp_mask].reset_index(drop=True)

exp_freq = exp['freq_Hz'].values
exp_amp  = exp['amplitude'].values
exp_real = exp['real'].values
exp_imag = exp['imag'].values

# Normalize to own maximum within the trimmed window
sim_amp_norm = sim_amp / sim_amp.max()
exp_amp_norm = exp_amp / exp_amp.max()


# ── Plot ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 1, figsize=(11, 5))
axes = [axes]
fig.suptitle("Lattice Z Direction: Simulation vs PSV Experiment", fontsize=13)

# Amplitude
axes[0].semilogy(sim_freq, sim_amp_norm, color='steelblue', linewidth=1.5,
                 label='Simulation (Mechanical)')
axes[0].semilogy(exp_freq, exp_amp_norm, color='darkorange', linewidth=1.2,
                 label='Experiment (PSV)')
axes[0].set_xlim(FREQ_MIN, FREQ_MAX)
axes[0].set_ylabel("Normalized Amplitude (log)")
axes[0].set_title("Magnitude")
axes[0].legend()
axes[0].grid(True, which='both', alpha=0.3)

axes[0].set_xlabel("Frequency (Hz)")

plt.tight_layout()
plt.savefig(OUT_FILE, dpi=150)
print(f"\nPlot saved to: {OUT_FILE}")
plt.show()

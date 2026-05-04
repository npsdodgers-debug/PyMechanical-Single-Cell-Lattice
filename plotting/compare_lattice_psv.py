"""
compare_lattice_psv.py

Compares the Mechanical simulation FRF against the Polytec PSV experimental FRF
for the lattice structure (Z-direction displacement / force).

Simulation:  Lattice Z direction.xls
Experiment:  Polytec PSV UNV file (H1 Displacement/Force, Z direction)
             Averaged across all scan points (RMS magnitude)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pyuff
from scipy.signal import find_peaks

# ── Config ────────────────────────────────────────────────────────────────────
SIM_FILE = r"C:\Users\coetech\Documents\Lattice Z direction.xls"
EXP_FILE = r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PolyTech PSV\BigLatticeHammer041526.unv"
OUT_FILE = r"C:\Users\coetech\Documents\Lattice_PSV_vs_Simulation.png"

# ── Load simulation ───────────────────────────────────────────────────────────
sim = pd.read_csv(SIM_FILE, sep=None, engine='python')
sim_freq = sim['Frequency (Hz)'].values
sim_amp  = sim['Amplitude (mm)'].values
sim_real = sim['Real (mm)'].values
sim_imag = sim['Imaginary (mm)'].values
print(f"Simulation: {len(sim_freq)} points, "
      f"{sim_freq.min():.1f} - {sim_freq.max():.1f} Hz")

# ── Load PSV experimental data ────────────────────────────────────────────────
uff = pyuff.UFF(EXP_FILE)
sets = uff.read_sets()

# Collect only H1 Displacement/Force sets (true FRF)
freq_bands = []
for s in sets:
    if s.get('type') == 55 and s.get('freq') is not None:
        id2 = s.get('id2', '')
        if 'H1 Displacement / Force' not in id2:
            continue
        f  = s['freq']
        r3 = np.array(s['r3'])   # Z-direction complex FRF
        # RMS magnitude across all scan points
        mag      = np.sqrt(np.mean(np.abs(r3)**2))
        real_avg = np.mean(r3.real)
        imag_avg = np.mean(r3.imag)
        freq_bands.append({'freq_Hz': f, 'amplitude': mag,
                           'real': real_avg, 'imag': imag_avg})

exp = pd.DataFrame(freq_bands).sort_values('freq_Hz').reset_index(drop=True)

# Convert m to mm (PSV exports in meters)
exp['amplitude'] *= 1000
exp['real']      *= 1000
exp['imag']      *= 1000

print(f"Experiment: {len(exp)} frequency bands, "
      f"{exp['freq_Hz'].min():.1f} - {exp['freq_Hz'].max():.1f} Hz")

exp_freq = exp['freq_Hz'].values
exp_amp  = exp['amplitude'].values
exp_real = exp['real'].values
exp_imag = exp['imag'].values

# Normalize both to their own maximum
sim_amp_norm  = sim_amp  / sim_amp.max()
sim_real_norm = sim_real / np.abs(sim_real).max()
sim_imag_norm = sim_imag / np.abs(sim_imag).max()
exp_amp_norm  = exp_amp  / exp_amp.max()
exp_real_norm = exp_real / np.abs(exp_real).max()
exp_imag_norm = exp_imag / np.abs(exp_imag).max()

# ── Detect peaks ──────────────────────────────────────────────────────────────
sim_peaks, _ = find_peaks(sim_amp, height=0.001 * sim_amp.max(), distance=3)
exp_peaks, _ = find_peaks(exp_amp, height=0.001 * exp_amp.max(), distance=2)

print(f"\nSimulation peaks: {sim_freq[sim_peaks].round(1)} Hz")
print(f"Experiment peaks: {exp_freq[exp_peaks].round(1)} Hz")

# ── Peak comparison table ─────────────────────────────────────────────────────
print("\n── Peak comparison ──")
print(f"{'Sim (Hz)':>10}  {'Exp (Hz)':>10}  {'Error (Hz)':>10}  {'Error (%)':>10}")
for sp in sim_freq[sim_peaks]:
    if len(exp_freq[exp_peaks]) == 0:
        break
    closest = exp_freq[exp_peaks][np.argmin(np.abs(exp_freq[exp_peaks] - sp))]
    err_hz  = closest - sp
    err_pct = 100 * err_hz / sp
    print(f"{sp:>10.1f}  {closest:>10.1f}  {err_hz:>+10.1f}  {err_pct:>+9.1f}%")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 1, figsize=(11, 5))
axes = [axes]
fig.suptitle("Lattice Z Direction: Simulation vs PSV Experiment", fontsize=13)

# Amplitude
axes[0].semilogy(sim_freq, sim_amp_norm, color='steelblue', linewidth=1.5,
                 label='Simulation (Mechanical)')
axes[0].semilogy(exp_freq, exp_amp_norm, 'o-', color='darkorange', markersize=5,
                 linewidth=1.2, label='Experiment (PSV)')
for p in sim_freq[sim_peaks]:
    axes[0].axvline(p, color='steelblue', linewidth=0.7, alpha=0.5)
for p in exp_freq[exp_peaks]:
    axes[0].axvline(p, color='darkorange', linewidth=0.7, alpha=0.5,
                    linestyle='--')
axes[0].set_ylabel("Normalized Amplitude (log)")
axes[0].set_title("Magnitude")
axes[0].legend()
axes[0].grid(True, which='both', alpha=0.3)

axes[0].set_xlabel("Frequency (Hz)")

plt.tight_layout()
plt.savefig(OUT_FILE, dpi=150)
print(f"\nPlot saved to: {OUT_FILE}")
plt.show()

"""
features.py

Extracts a fixed-length feature vector from an FRF for SHM classification.

Features per peak (up to N_PEAKS):
    peak_freq_i    — resonance frequency (Hz)
    peak_amp_i     — amplitude at peak (mm)
    damping_i      — damping ratio via half-power bandwidth

Local / rigid-body modes are suppressed by:
    min_freq        — ignore everything below this frequency
    prominence_frac — peak must be >= this fraction of the window max
"""

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

N_PEAKS_DEFAULT   = 5
MIN_FREQ_DEFAULT  = 500.0   # Hz — filters rigid-body and local strut modes
PROMINENCE_FRAC   = 0.05    # 5 % of window maximum


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_frf_pipeline(csv_path, force_x_mm, force_y_mm, force_z_mm):
    """Driving-point FRF from nodal_displacement_complex.csv."""
    df     = pd.read_csv(csv_path)
    coords = df.groupby('node_id')[['x', 'y', 'z']].first()

    # DPF mesh API returns meters; APDL uses model units (mm).
    # If the max absolute coordinate is < 1.0 the CSV is in meters — convert.
    max_abs = coords.abs().max().max()
    if 0 < max_abs < 1.0:
        coords = coords * 1000.0

    dist   = np.sqrt(
        (coords['x'] - force_x_mm)**2 +
        (coords['y'] - force_y_mm)**2 +
        (coords['z'] - force_z_mm)**2
    )
    node    = dist.idxmin()
    node_df = df[df['node_id'] == node].sort_values('freq_Hz')
    freqs   = node_df['freq_Hz'].values
    uz_real = node_df['uz_real'].values * 1e3   # m → mm
    uz_imag = node_df['uz_imag'].values * 1e3
    amp     = np.sqrt(uz_real**2 + uz_imag**2)
    return freqs, amp


def load_frf_averaged(csv_path, top_face_only=False, z_top_mm=31.5, z_tol=1.0):
    """Spatially-averaged FRF across all nodes (or top face only)."""
    df = pd.read_csv(csv_path)

    if top_face_only:
        node_z = df.groupby('node_id')['z'].first()
        if 0 < node_z.abs().max() < 1.0:
            node_z = node_z * 1000.0
        top_nodes = node_z[node_z >= (z_top_mm - z_tol)].index
        df = df[df['node_id'].isin(top_nodes)]

    # Compute per-node magnitude first, then average — avoids mode cancellation
    # (averaging complex values lets +Z and -Z nodes cancel each other out)
    df['uz_amp'] = np.sqrt(df['uz_real']**2 + df['uz_imag']**2) * 1e3
    grp   = df.groupby('freq_Hz')['uz_amp']
    freqs = np.array(grp.mean().index)
    amp   = grp.mean().values
    return freqs, amp


def load_frf_simple(csv_path, freq_col='Frequency (Hz)', amp_col=None):
    """FRF from a two-column CSV (frequency, amplitude)."""
    df = pd.read_csv(csv_path, sep=None, engine='python')
    if amp_col is None:
        for candidate in ['Amplitude (mm)', 'Amplitude (m)', 'Amplitude']:
            if candidate in df.columns:
                amp_col = candidate
                break
        else:
            raise ValueError(f"Cannot detect amplitude column. Found: {df.columns.tolist()}")
    freqs = df[freq_col].values
    amp   = df[amp_col].values
    if '(m)' in amp_col and '(mm)' not in amp_col:
        amp = amp * 1000   # m → mm
    return freqs, amp


# ── Internal helpers ──────────────────────────────────────────────────────────

def _half_power_damping(freqs, amp, peak_idx):
    """Damping ratio ζ = (f2 - f1) / (2 * fn) via half-power bandwidth."""
    fn       = freqs[peak_idx]
    half_pow = amp[peak_idx] / np.sqrt(2)

    left        = amp[:peak_idx]
    below_left  = np.where(left < half_pow)[0]
    f1 = freqs[below_left[-1]] if len(below_left) > 0 else freqs[0]

    right       = amp[peak_idx + 1:]
    below_right = np.where(right < half_pow)[0]
    f2 = freqs[peak_idx + 1 + below_right[0]] if len(below_right) > 0 else freqs[-1]

    return (f2 - f1) / (2.0 * fn)


# ── Main feature extractor ────────────────────────────────────────────────────

def extract_features(freqs, amp, n_peaks=N_PEAKS_DEFAULT,
                     min_freq=MIN_FREQ_DEFAULT,
                     prominence_frac=PROMINENCE_FRAC):
    """
    Return a fixed-length feature dict from an FRF.

    Parameters
    ----------
    freqs, amp      : 1-D arrays from any loader above
    n_peaks         : number of peaks to keep (pads with NaN if fewer found)
    min_freq        : low-frequency cutoff to suppress local/rigid-body modes
    prominence_frac : minimum prominence as fraction of window max amplitude

    Returns
    -------
    dict  feature_name → float
    """
    mask = freqs >= min_freq
    f    = freqs[mask]
    a    = amp[mask]

    if len(a) == 0:
        raise ValueError(f"No data above min_freq={min_freq} Hz")

    min_prominence = prominence_frac * a.max()
    peaks, props   = find_peaks(a, prominence=min_prominence, distance=3)

    # Keep top n_peaks by prominence, then re-sort by frequency
    if len(peaks) > 0:
        order = np.argsort(props['prominences'])[::-1]
        peaks = peaks[order[:n_peaks]]
        peaks = np.sort(peaks)

    features = {}
    for i in range(n_peaks):
        if i < len(peaks):
            idx = peaks[i]
            features[f'peak_freq_{i}'] = f[idx]
            features[f'peak_amp_{i}']  = a[idx]
            features[f'damping_{i}']   = _half_power_damping(f, a, idx)
        else:
            features[f'peak_freq_{i}'] = np.nan
            features[f'peak_amp_{i}']  = np.nan
            features[f'damping_{i}']   = np.nan

    features['n_peaks_found'] = int(len(peaks))
    return features

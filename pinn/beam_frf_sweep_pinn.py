"""
beam_frf_sweep_pinn.py

Builds a cantilever beam FRF by solving a separate 1-D PINN at each frequency.

Why frequency-by-frequency instead of the 2-D (x, ω) approach:
    The FRF spans ~3 orders of magnitude between peaks and troughs.
    A single 2-D network struggles to represent that variation.
    Splitting by frequency turns each solve into a smooth 1-D problem
    that the PINN handles easily.

Warm-starting: the network weights carry over from one frequency to the next.
Adjacent frequencies have similar solutions, so convergence is fast after
the first solve.

PDE at each fixed ω:
    EI·(1+iη)·d⁴W/dx⁴  −  ω²·ρA·W  =  F·g(x)

where g(x) is a Gaussian approximating a point force at x_f.

FRF: |H(ω)| = |W(x_m, ω)| / F  assembled across all frequencies.

Requirements: pip install torch numpy matplotlib scipy
"""

import numpy as np
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
from scipy.integrate import quad

# ── Beam parameters ───────────────────────────────────────────────────────────
L    = 0.30
E    = 200e9
side = 0.01
EI   = E * side**4 / 12       # 166.7 N·m²
rhoA = 7850 * side**2          # 0.785 kg/m
eta  = 0.02                    # structural damping loss factor

F    = 1.0                     # force (N)
x_f  = L / 2                  # force location (m)
x_m  = L                      # measurement point — tip (m)

sigma_f = L / 25               # Gaussian width  ≈ 12 mm
W0      = F * L**3 / (3*EI)   # static tip scale  ≈ 5.4×10⁻⁵ m

# ── Natural frequencies ───────────────────────────────────────────────────────
lambda_L = np.array([1.87510, 4.69409, 7.85476, 10.99554, 14.13717])
omega_n  = (lambda_L / L)**2 * np.sqrt(EI / rhoA)
freq_n   = omega_n / (2 * np.pi)

# ── Frequency sweep ───────────────────────────────────────────────────────────
FREQ_MIN  = 1.0
FREQ_MAX  = 700.0

# Non-uniform sweep: coarse background + dense bands around each resonance
# so the narrow peaks are actually sampled
_coarse = np.linspace(FREQ_MIN, FREQ_MAX, 60)
_dense  = np.concatenate([np.linspace(fn - 15, fn + 15, 40)
                           for fn in freq_n[:2]])
freq_sweep = np.unique(np.clip(np.concatenate([_coarse, _dense]),
                               FREQ_MIN, FREQ_MAX))
N_FREQ = len(freq_sweep)

# ── Training settings ─────────────────────────────────────────────────────────
N_COL           = 150     # collocation points per solve
N_EPOCHS_INIT   = 8000   # epochs for first frequency (cold start)
N_EPOCHS_WARM   = 2000   # epochs away from resonance
N_EPOCHS_RES    = 4000   # epochs near a resonance peak
RESONANCE_BAND  = 20.0   # Hz — extra epochs within this range of a resonance
LR              = 1e-3
W_BC            = 10.0   # reduced: prevents BC loss dominating over PDE

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")
print("Natural frequencies:  " + "  ".join(f"Mode {i+1}: {f:.1f} Hz" for i, f in enumerate(freq_n[:3])))
print()


# ── Network ───────────────────────────────────────────────────────────────────
class BeamNet1D(nn.Module):
    """Maps x/L → (W_real/W0, W_imag/W0) for one fixed frequency."""
    def __init__(self, hidden=32, depth=4):
        super().__init__()
        layers = [nn.Linear(1, hidden), nn.Tanh()]
        for _ in range(depth - 1):
            layers += [nn.Linear(hidden, hidden), nn.Tanh()]
        layers.append(nn.Linear(hidden, 2))
        self.net = nn.Sequential(*layers)

    def forward(self, xn):
        return self.net(xn)   # → [N, 2]


# ── Derivatives ───────────────────────────────────────────────────────────────
def all_derivs(model, x_phys):
    """W and spatial derivatives to 4th order (physical units)."""
    xn  = (x_phys / L).requires_grad_(True)
    out = model(xn) * W0
    Wr, Wi = out[:, 0:1], out[:, 1:2]

    def d(y):
        return torch.autograd.grad(y, xn, grad_outputs=torch.ones_like(y),
                                   create_graph=True)[0] / L

    Wr1 = d(Wr);  Wr2 = d(Wr1);  Wr3 = d(Wr2);  Wr4 = d(Wr3)
    Wi1 = d(Wi);  Wi2 = d(Wi1);  Wi3 = d(Wi2);  Wi4 = d(Wi3)
    return Wr, Wi, Wr1, Wi1, Wr2, Wi2, Wr3, Wi3, Wr4, Wi4


# ── Loads and losses ──────────────────────────────────────────────────────────
def g_load(x):
    return F / (sigma_f * np.sqrt(2*np.pi)) * torch.exp(-0.5*((x - x_f)/sigma_f)**2)


def loss_pde(model, x, omega_val):
    Wr, Wi, _, _, _, _, _, _, Wr4, Wi4 = all_derivs(model, x)
    q  = g_load(x)
    w2 = omega_val**2
    # Divide by EI so all terms are O(1) — avoids EI (~167) dominating
    r_r = Wr4 - eta*Wi4 - (w2*rhoA/EI)*Wr - q/EI
    r_i = Wi4 + eta*Wr4 - (w2*rhoA/EI)*Wi
    return (r_r**2 + r_i**2).mean()


def loss_bc(model):
    x0 = torch.zeros(1, 1, device=DEVICE)
    xL = torch.full((1, 1), L, device=DEVICE)

    Wr0, Wi0, Wr10, Wi10, *_                        = all_derivs(model, x0)
    WrL, WiL, _,    _,    Wr2L, Wi2L, Wr3L, Wi3L, *_ = all_derivs(model, xL)

    bc  = (Wr0**2  + Wi0**2 ).mean()
    bc += (Wr10**2 + Wi10**2).mean()
    bc += (Wr2L**2 + Wi2L**2).mean()
    bc += (Wr3L**2 + Wi3L**2).mean()
    return bc


# ── Frequency sweep ───────────────────────────────────────────────────────────
model     = BeamNet1D().to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)  # kept alive across frequencies
H_pinn    = np.zeros(N_FREQ)

near_res  = lambda f: any(abs(f - fn) < RESONANCE_BAND for fn in freq_n[:2])

print(f"Sweeping {N_FREQ} frequencies from {FREQ_MIN:.0f} to {FREQ_MAX:.0f} Hz ...")
print(f"  Cold start: {N_EPOCHS_INIT} epochs  |  warm: {N_EPOCHS_WARM}  |  near resonance: {N_EPOCHS_RES}\n")

for i, freq in enumerate(freq_sweep):
    omega_val = 2 * np.pi * freq
    if i == 0:
        n_ep = N_EPOCHS_INIT
    elif near_res(freq):
        n_ep = N_EPOCHS_RES
    else:
        n_ep = N_EPOCHS_WARM

    for ep in range(n_ep):
        x_col = torch.rand(N_COL, 1, device=DEVICE) * L
        optimizer.zero_grad()
        loss = loss_pde(model, x_col, omega_val) + W_BC * loss_bc(model)
        loss.backward()
        optimizer.step()

    with torch.no_grad():
        xm_n = torch.tensor([[x_m / L]], dtype=torch.float32, device=DEVICE)
        out  = model(xm_n) * W0
        H_pinn[i] = np.sqrt(out[0, 0].item()**2 + out[0, 1].item()**2) / F

    tag = " <-- resonance" if near_res(freq) else ""
    if (i + 1) % 10 == 0 or i == 0 or near_res(freq):
        print(f"  [{i+1:3d}/{N_FREQ}]  {freq:6.1f} Hz  |H| = {H_pinn[i]*1e3:.4f} mm/N{tag}")

print("\nSweep complete.")


# ── Analytical FRF (modal superposition) ─────────────────────────────────────
sigma_ms = (np.cosh(lambda_L) + np.cos(lambda_L)) / (np.sinh(lambda_L) + np.sin(lambda_L))
lam      = lambda_L / L

def phi(x, n):
    lx = lam[n] * x
    return np.cosh(lx) - np.cos(lx) - sigma_ms[n] * (np.sinh(lx) - np.sin(lx))

def analytical_frf(freq_arr, n_modes=5):
    H = np.zeros(len(freq_arr), dtype=complex)
    for n in range(n_modes):
        m_n, _ = quad(lambda x: rhoA * phi(x, n)**2, 0, L)
        rn_sq  = (2*np.pi*freq_arr / omega_n[n])**2
        H     += phi(x_f, n) * phi(x_m, n) / (m_n * omega_n[n]**2 * ((1 - rn_sq) + 1j*eta))
    return np.abs(H)

H_anal = analytical_frf(freq_sweep)

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 5))
ax.semilogy(freq_sweep, H_anal * 1e3, color='steelblue',  linewidth=2,
            label='Modal superposition (analytical)')
ax.semilogy(freq_sweep, H_pinn * 1e3, color='darkorange', linewidth=1.5,
            linestyle='--', marker='o', markersize=3, label='PINN (sweep)')
for i, fn in enumerate(freq_n[:2]):
    ax.axvline(fn, color='gray', linewidth=0.8, linestyle=':', alpha=0.7,
               label=f'Mode {i+1}: {fn:.0f} Hz')
ax.set_xlabel("Frequency (Hz)")
ax.set_ylabel("|H(ω)|  (mm/N, log scale)")
ax.set_title("Cantilever Beam FRF — Frequency-by-Frequency PINN vs Analytical")
ax.legend(fontsize=9)
ax.grid(True, which='both', alpha=0.3)
ax.set_xlim(FREQ_MIN, FREQ_MAX)
plt.tight_layout()
plt.show()

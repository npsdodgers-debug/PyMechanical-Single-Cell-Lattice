"""
beam_frf_pinn.py

PINN for the Frequency Response Function (FRF) of a cantilever beam.
Solves the forced harmonic Euler-Bernoulli equation in the frequency domain:

    EI·(1+iη)·d⁴W/dx⁴  −  ω²·ρA·W  =  F·g(x)

where g(x) is a Gaussian approximating a point force at x_f,
η is the structural damping loss factor, and W = W_real + i·W_imag.

The network learns  (x, ω) → (W_real, W_imag)  over the full spatial
and frequency domain in a single training run.

FRF at tip:  |H(ω)| = sqrt(W_real² + W_imag²) / F  (m/N)

Validates against modal superposition (first 5 modes).

Note: computing 4th-order derivatives through autograd is expensive on CPU.
      Expect ~20–40 min on CPU.  A GPU cuts this to a few minutes.

Requirements: pip install torch numpy matplotlib scipy
"""

import numpy as np
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
from scipy.integrate import quad

# ── Beam parameters ───────────────────────────────────────────────────────────
L    = 0.30           # length (m) — 300 mm, similar to a lattice strut
E    = 200e9          # Young's modulus (Pa) — steel
side = 0.01           # square cross-section side (m)
EI   = E * side**4 / 12          # bending stiffness  166.7 N·m²
rhoA = 7850 * side**2             # mass per unit length  0.785 kg/m
eta  = 0.02                       # structural damping loss factor

F    = 1.0            # excitation force (N)
x_f  = L / 2         # force location (m) — beam midpoint
x_m  = L             # measurement point (m) — beam tip

FREQ_MIN, FREQ_MAX = 1.0, 700.0   # Hz  (captures first two cantilever modes)
sigma_f = L / 25                   # Gaussian width  ≈ 12 mm
W0      = F * L**3 / (3 * EI)     # static tip deflection  ≈ 5.4×10⁻⁵ m

# ── Training settings ─────────────────────────────────────────────────────────
N_COL    = 1000
N_BC     = 200
N_EPOCHS = 15000
LR       = 1e-3
W_BC     = 50.0

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")

ω_lo = 2 * np.pi * FREQ_MIN
ω_hi = 2 * np.pi * FREQ_MAX

# ── Print expected natural frequencies ───────────────────────────────────────
lambda_L = np.array([1.87510, 4.69409, 7.85476, 10.99554, 14.13717])
omega_n  = (lambda_L / L)**2 * np.sqrt(EI / rhoA)
freq_n   = omega_n / (2 * np.pi)
print("Expected natural frequencies:")
for i, f in enumerate(freq_n[:3]):
    print(f"  Mode {i+1}: {f:.1f} Hz")
print()


# ── Network ───────────────────────────────────────────────────────────────────
class FRFNet(nn.Module):
    """Maps normalised (x/L, (ω−ω_lo)/(ω_hi−ω_lo)) → (W_real/W0, W_imag/W0)."""
    def __init__(self, hidden=64, depth=5):
        super().__init__()
        layers = [nn.Linear(2, hidden), nn.Tanh()]
        for _ in range(depth - 1):
            layers += [nn.Linear(hidden, hidden), nn.Tanh()]
        layers.append(nn.Linear(hidden, 2))
        self.net = nn.Sequential(*layers)

    def forward(self, xn, on):
        return self.net(torch.cat([xn, on], dim=-1))   # → [N, 2]


model     = FRFNet().to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)


# ── Forward pass with spatial derivatives ────────────────────────────────────
def all_derivs(x_phys, omega):
    """
    Compute W and all spatial derivatives up to 4th order.
    Returns:  Wr, Wi, Wr1, Wi1, Wr2, Wi2, Wr3, Wi3, Wr4, Wi4  (physical units)
    """
    xn = (x_phys / L).requires_grad_(True)
    on = (omega - ω_lo) / (ω_hi - ω_lo)

    out = model(xn, on) * W0      # un-normalise output
    Wr  = out[:, 0:1]
    Wi  = out[:, 1:2]

    def d(y):
        return torch.autograd.grad(y, xn, grad_outputs=torch.ones_like(y),
                                   create_graph=True)[0] / L  # chain rule

    Wr1 = d(Wr);  Wr2 = d(Wr1);  Wr3 = d(Wr2);  Wr4 = d(Wr3)
    Wi1 = d(Wi);  Wi2 = d(Wi1);  Wi3 = d(Wi2);  Wi4 = d(Wi3)

    return Wr, Wi, Wr1, Wi1, Wr2, Wi2, Wr3, Wi3, Wr4, Wi4


# ── Gaussian point load ───────────────────────────────────────────────────────
def g_load(x):
    return F / (sigma_f * np.sqrt(2*np.pi)) * torch.exp(-0.5 * ((x - x_f) / sigma_f)**2)


# ── Losses ────────────────────────────────────────────────────────────────────
def loss_pde(x, omega):
    Wr, Wi, _, _, _, _, _, _, Wr4, Wi4 = all_derivs(x, omega)
    q  = g_load(x)
    w2 = omega**2

    # Real part:  EI·Wr'''' − η·EI·Wi'''' − ω²·ρA·Wr = q
    # Imag part:  EI·Wi'''' + η·EI·Wr'''' − ω²·ρA·Wi = 0
    r_r = EI * Wr4 - eta * EI * Wi4 - w2 * rhoA * Wr - q
    r_i = EI * Wi4 + eta * EI * Wr4 - w2 * rhoA * Wi

    return (r_r**2 + r_i**2).mean()


def loss_bc(omega):
    n  = omega.shape[0]
    x0 = torch.zeros(n, 1, device=DEVICE)
    xL = torch.full((n, 1), L, device=DEVICE)

    Wr0, Wi0, Wr10, Wi10, *_                        = all_derivs(x0, omega)
    WrL, WiL, _,    _,    Wr2L, Wi2L, Wr3L, Wi3L, *_ = all_derivs(xL, omega)

    bc  = (Wr0**2  + Wi0**2 ).mean()    # W(0)   = 0
    bc += (Wr10**2 + Wi10**2).mean()    # W'(0)  = 0
    bc += (Wr2L**2 + Wi2L**2).mean()    # W''(L) = 0
    bc += (Wr3L**2 + Wi3L**2).mean()    # W'''(L)= 0
    return bc


# ── Training loop ─────────────────────────────────────────────────────────────
print(f"Training for {N_EPOCHS} epochs (this takes a while on CPU) ...")
for ep in range(1, N_EPOCHS + 1):
    x_col = torch.rand(N_COL, 1, device=DEVICE) * L
    w_col = torch.rand(N_COL, 1, device=DEVICE) * (ω_hi - ω_lo) + ω_lo
    w_bc  = torch.rand(N_BC,  1, device=DEVICE) * (ω_hi - ω_lo) + ω_lo

    optimizer.zero_grad()
    loss = loss_pde(x_col, w_col) + W_BC * loss_bc(w_bc)
    loss.backward()
    optimizer.step()

    if ep % 1000 == 0:
        print(f"  Epoch {ep:6d}  |  loss = {loss.item():.4e}")

print("Training complete.\n")


# ── Analytical FRF via modal superposition ────────────────────────────────────
def analytical_frf(freq_arr, x_src, x_rcv, n_modes=5):
    """
    Cantilever beam FRF |H(ω)| in m/N using structural damping.
    Modal superposition over the first n_modes bending modes.
    """
    lam   = lambda_L[:n_modes] / L
    sigma = (np.cosh(lambda_L[:n_modes]) + np.cos(lambda_L[:n_modes])) / \
            (np.sinh(lambda_L[:n_modes]) + np.sin(lambda_L[:n_modes]))

    def phi(x, n):
        lx = lam[n] * x
        return np.cosh(lx) - np.cos(lx) - sigma[n] * (np.sinh(lx) - np.sin(lx))

    H = np.zeros(len(freq_arr), dtype=complex)
    for n in range(n_modes):
        m_n, _ = quad(lambda x: rhoA * phi(x, n)**2, 0, L)
        rn_sq  = (2 * np.pi * freq_arr / omega_n[n])**2
        H     += phi(x_src, n) * phi(x_rcv, n) / (m_n * omega_n[n]**2 * ((1 - rn_sq) + 1j * eta))

    return np.abs(H)


# ── Evaluate PINN FRF ─────────────────────────────────────────────────────────
freq_arr  = np.linspace(FREQ_MIN, FREQ_MAX, 500)
omega_arr = 2 * np.pi * freq_arr

xm_t = torch.full((len(omega_arr), 1), x_m, device=DEVICE)
om_t = torch.tensor(omega_arr, dtype=torch.float32, device=DEVICE).unsqueeze(1)
xn_t = xm_t / L
on_t = (om_t - ω_lo) / (ω_hi - ω_lo)

with torch.no_grad():
    out   = model(xn_t, on_t) * W0
    Wr_np = out[:, 0].cpu().numpy()
    Wi_np = out[:, 1].cpu().numpy()

H_pinn = np.sqrt(Wr_np**2 + Wi_np**2) / F
H_anal = analytical_frf(freq_arr, x_f, x_m, n_modes=5)

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 5))
ax.semilogy(freq_arr, H_anal * 1e3, color='steelblue',  linewidth=2,
            label='Modal superposition (analytical)')
ax.semilogy(freq_arr, H_pinn * 1e3, color='darkorange', linewidth=1.5,
            linestyle='--', label='PINN')
for i, fn in enumerate(freq_n[:2]):
    ax.axvline(fn, color='gray', linewidth=0.8, linestyle=':', alpha=0.6,
               label=f'Mode {i+1}: {fn:.0f} Hz' if i == 0 else f'Mode {i+1}: {fn:.0f} Hz')
ax.set_xlabel("Frequency (Hz)")
ax.set_ylabel("|H(ω)|  (mm/N, log scale)")
ax.set_title("Cantilever Beam FRF — PINN vs Modal Superposition")
ax.legend(fontsize=9)
ax.grid(True, which='both', alpha=0.3)
ax.set_xlim(FREQ_MIN, FREQ_MAX)
plt.tight_layout()
plt.show()

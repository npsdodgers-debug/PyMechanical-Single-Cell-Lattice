"""
beam_pinn.py

Physics-Informed Neural Network for static deflection of a cantilever beam.

Euler-Bernoulli beam equation:   EI * d4w/dx4 = q

Geometry: cantilever, fixed at x=0, free at x=L
Load:     uniform distributed load q (N/m)

Boundary conditions:
    w(0)    = 0   no deflection at fixed end
    w'(0)   = 0   no slope at fixed end
    w''(L)  = 0   no bending moment at free end
    w'''(L) = 0   no shear force at free end

Analytical solution:
    w(x) = q / (24*E*I) * (6*L^2*x^2 - 4*L*x^3 + x^4)

Requirements:
    pip install torch numpy matplotlib
"""

import torch
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt

# ── Beam parameters ───────────────────────────────────────────────────────────
L   = 1.0       # beam length (m)
E   = 200e9     # Young's modulus (Pa) — steel
b   = 0.01      # cross-section width (m)
h   = 0.01      # cross-section height (m)
I   = b * h**3 / 12   # second moment of area (m^4)
EI  = E * I     # bending stiffness (N·m²)
q   = 1000.0    # uniform distributed load (N/m)

# ── Training settings ─────────────────────────────────────────────────────────
N_COLLOC  = 200    # collocation points for physics loss
N_EPOCHS  = 30000
LR        = 1e-3
BC_WEIGHT = 100.0  # weight on boundary condition losses vs physics loss

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {DEVICE}")


# ── Neural network ────────────────────────────────────────────────────────────
class BeamNet(nn.Module):
    def __init__(self, hidden=64, layers=4):
        super().__init__()
        seq = [nn.Linear(1, hidden), nn.Tanh()]
        for _ in range(layers - 1):
            seq += [nn.Linear(hidden, hidden), nn.Tanh()]
        seq += [nn.Linear(hidden, 1)]
        self.net = nn.Sequential(*seq)

    def forward(self, x):
        return self.net(x)


# ── Automatic differentiation helpers ────────────────────────────────────────
def grad(y, x):
    return torch.autograd.grad(y, x, grad_outputs=torch.ones_like(y),
                               create_graph=True)[0]


def derivatives(model, x):
    """Return w, w', w'', w''', w'''' at points x."""
    x  = x.requires_grad_(True)
    w  = model(x)
    w1 = grad(w,  x)
    w2 = grad(w1, x)
    w3 = grad(w2, x)
    w4 = grad(w3, x)
    return w, w1, w2, w3, w4


# ── Losses ────────────────────────────────────────────────────────────────────
def physics_loss(model, x_col):
    _, _, _, _, w4 = derivatives(model, x_col)
    residual = EI * w4 - q
    return (residual ** 2).mean()


def bc_loss(model):
    x0 = torch.zeros(1, 1, device=DEVICE, requires_grad=True)
    xL = torch.full((1, 1), L, device=DEVICE, requires_grad=True)

    w0, w1_0, _,    _,    _ = derivatives(model, x0)
    _,  _,    w2_L, w3_L, _ = derivatives(model, xL)

    loss  = w0   ** 2        # w(0)    = 0
    loss += w1_0 ** 2        # w'(0)   = 0
    loss += w2_L ** 2        # w''(L)  = 0
    loss += w3_L ** 2        # w'''(L) = 0
    return loss.mean()


# ── Analytical solution ───────────────────────────────────────────────────────
def analytical(x_np):
    return q / (24 * EI) * (6*L**2 * x_np**2 - 4*L * x_np**3 + x_np**4)


# ── Training ──────────────────────────────────────────────────────────────────
model = BeamNet().to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)

x_col = torch.rand(N_COLLOC, 1, device=DEVICE) * L

print(f"\nTraining for {N_EPOCHS} epochs...")
for epoch in range(1, N_EPOCHS + 1):
    optimizer.zero_grad()
    loss = physics_loss(model, x_col) + BC_WEIGHT * bc_loss(model)
    loss.backward()
    optimizer.step()

    if epoch % 1000 == 0:
        print(f"  Epoch {epoch:6d}  |  Loss: {loss.item():.4e}")

print("Training complete.")

# ── Evaluate & plot ───────────────────────────────────────────────────────────
x_np    = np.linspace(0, L, 300)
x_test  = torch.tensor(x_np, dtype=torch.float32, device=DEVICE).unsqueeze(1)

with torch.no_grad():
    w_pinn = model(x_test).cpu().numpy().flatten()

w_exact = analytical(x_np)

# Scale factor so both curves are in mm
scale = 1e3

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(x_np * 1e3, w_exact * scale, color='steelblue',  linewidth=2,   label='Analytical')
ax.plot(x_np * 1e3, w_pinn  * scale, color='darkorange', linewidth=1.5,
        linestyle='--', label='PINN')
ax.set_xlabel("Position along beam (mm)")
ax.set_ylabel("Deflection (mm)")
ax.set_title("Cantilever Beam — PINN vs Analytical")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

max_err = np.max(np.abs(w_pinn - w_exact))
print(f"\nMax absolute error: {max_err*1e6:.2f} µm  "
      f"(tip deflection = {w_exact[-1]*1e3:.4f} mm)")

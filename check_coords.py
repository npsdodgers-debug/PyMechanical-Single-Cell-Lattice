import pandas as pd, numpy as np

DATA = r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Missing_Upper_Strut\Sweep"
files = [
    ("center",           15.0, -15.0),
    ("corner(0,0)",       0.0,   0.0),
    ("corner(0.03,0)",   30.0,   0.0),
    ("corner(0,-0.03)",   0.0, -30.0),
    ("corner(0.03,-0.03)", 30.0, -30.0),
]
for label, fx, fy in files:
    df = pd.read_csv(f"{DATA}\\damaged_{label}_complex.csv")
    coords = df.groupby('node_id')[['x','y','z']].first()
    dist = np.sqrt((coords['x']-fx)**2 + (coords['y']-fy)**2 + (coords['z']-31.5)**2)
    node = dist.idxmin()
    row = coords.loc[node]
    print(f"{label}: node {node} at ({row.x:.1f}, {row.y:.1f}, {row.z:.1f}) mm  dist={dist[node]:.1f} mm")

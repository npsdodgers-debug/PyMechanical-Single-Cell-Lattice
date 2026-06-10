from ansys.mechanical.core import launch_mechanical
import os

from Harmonic_Subfunctions import (
    setup_session_and_model,
    check_body_material,
    setup_mesh,
    check_model_info,
    setup_harmonic_analysis,
    setup_material,
    add_remote_force,
    solve_model,
    print_solve_output,
    close_mechanical,
    # run_modal_analysis,
    add_apdl_imaginary_export,
    export_real_displacement,
    merge_real_imag_csv,
)

# ── Excitation locations — must match excitation_sweep.py exactly ─────────────
EXCITATION_LOCATIONS = [
    # Corners
    ("center",              0.015,  -0.015),
    ("corner(0,0)",         0.0,     0.0  ),
    ("corner(0.03,0)",      0.03,    0.0  ),
    ("corner(0,-0.03)",     0.0,    -0.03 ),
    ("corner(0.03,-0.03)",  0.03,   -0.03 ),
    # Edge midpoints
    ("edge(15,0)",          0.015,   0.0  ),
    ("edge(0,-15)",         0.0,    -0.015),
    ("edge(30,-15)",        0.03,   -0.015),
    ("edge(15,-30)",        0.015,  -0.03 ),
]

if __name__ == "__main__":
    base_config = {
        # ── Geometry ──────────────────────────────────────────────────────────
        "geometry_path": r"C:\Users\coetech\Documents\PyMechanical\Thin_beam\30mm Single Unit Cell Missing Lower Strut.x_b",

        # ── Mesh ──────────────────────────────────────────────────────────────
        "element_size": 5e-3,

        # ── Modal analysis ────────────────────────────────────────────────────
        "modal_min_freq_hz": 1.0,
        "modal_max_modes":   20,

        # ── Harmonic analysis ─────────────────────────────────────────────────
        "f_start_hz": 500.0,
        "f_end_hz":   3500.0,
        "n_points":   100,

        # ── Material ──────────────────────────────────────────────────────────
        "material_name":          "Resin",
        "material_E_Pa":          2.35e9,
        "material_nu":            0.3,
        "material_density_kgm3":  1220.0,

        # ── Force ─────────────────────────────────────────────────────────────
        "force_face_id":    680,     # top face ID for missing lower strut geometry
        "force_value_N":   -1.0,
        "force_direction":  "Z",
        "force_x_m":        0.015,   # top face centroid X (default)
        "force_y_m":       -0.015,   # top face centroid Y (default)
        "force_z_m":        0.0315,  # top face Z

        # ── GUI ───────────────────────────────────────────────────────────────
        "show_gui": True,

        # ── Output ────────────────────────────────────────────────────────────
        "output_dir":   r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Missing_Lower_Strut\Sweep",
        "project_name": "lower_strut_excitation_sweep",
    }

    os.makedirs(base_config["output_dir"], exist_ok=True)

    # ── One-time setup ────────────────────────────────────────────────────────
    mech = setup_session_and_model(base_config)
    setup_material(base_config, mech)
    check_body_material(base_config, mech)
    setup_harmonic_analysis(base_config, mech)
    setup_mesh(base_config, mech)
    check_model_info(base_config, mech)

    # ── Free-free: no fixed support applied ──────────────────────────────────

    # ── Modal analysis (once) — comment back in to save modal_frequencies.json
    # run_modal_analysis(base_config, mech)

    # ── Excitation sweep ──────────────────────────────────────────────────────
    for label, fx, fy in EXCITATION_LOCATIONS:
        print(f"\n{'='*60}")
        print(f"Excitation location: {label}  (X={fx}, Y={fy}, Z={base_config['force_z_m']})")
        print(f"{'='*60}")

        config = dict(base_config)
        config["csv_name"]      = f"damaged_{label}_complex.csv"
        config["imag_csv_name"] = f"damaged_{label}_imag_apdl"
        config["real_csv_name"] = f"damaged_{label}_real.csv"
        config["force_x_m"]    = fx
        config["force_y_m"]    = fy

        # Skip if already completed
        complex_csv = os.path.join(config["output_dir"], config["csv_name"])
        if os.path.exists(complex_csv):
            print(f"  Skipping {label} — output already exists")
            continue

        # Clear existing remote forces and APDL snippets
        clear_script = """
harmonic = None
for a in Model.Analyses:
    if "Harmonic" in a.Name:
        harmonic = a
        break
cleared = []
if harmonic is not None:
    for child in list(harmonic.Children):
        if "Force" in child.GetType().Name or "Remote" in child.GetType().Name:
            child.Delete()
            cleared.append(child.GetType().Name)
    for child in list(harmonic.Solution.Children):
        if "Command" in child.GetType().Name:
            child.Delete()
            cleared.append("APDL snippet")
result = "OK: cleared " + str(cleared)
result
"""
        out = mech.run_python_script(clear_script)
        print(f"  Mechanical says (clear): {out}")

        # Apply remote force and solve
        add_remote_force(config, mech)
        add_apdl_imaginary_export(config, mech)
        solve_model(config, mech)
        export_real_displacement(config, mech)
        merge_real_imag_csv(config)
        print_solve_output(mech)

        print(f"  Done: {config['csv_name']}")

    # ── Done ──────────────────────────────────────────────────────────────────
    input("\nAll locations complete. Press Enter to close Mechanical...")
    close_mechanical(base_config, mech)

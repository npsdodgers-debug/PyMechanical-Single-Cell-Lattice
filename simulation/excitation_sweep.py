from ansys.mechanical.core import launch_mechanical
import os

from Harmonic_Subfunctions import (
    setup_session_and_model,
    check_body_material,
    setup_mesh,
    check_model_info,
    export_geometry_image,
    setup_harmonic_analysis,
    setup_material,
    add_remote_force,
    export_bc_view,
    solve_model,
    print_solve_output,
    close_mechanical,
    run_modal_analysis,
    add_apdl_imaginary_export,
    export_real_displacement,
    merge_real_imag_csv,
)

# ── Excitation locations on the top face ──────────────────────────────────────
# Each entry: (label, force_x_m, force_y_m)
# None falls back to the centroid values set in base_config (force_x_m, force_y_m).
# Centroid of the middle unit top face: (0.015, -0.015, 0.0315) — confirmed in Mechanical.
# Fill in corner coordinates after first run (check Mechanical coordinate readout).
EXCITATION_LOCATIONS = [
    ("center",  0.015,  -0.015),
    ("corner0", 0,   0  ),   # update: (min_x, min_y) of top face
    #("corner1", None,   None  ),   # update: (max_x, min_y) of top face
    #("corner2", None,   None  ),   # update: (min_x, max_y) of top face
    #("corner3", None,   None  ),   # update: (max_x, max_y) of top face
]

if __name__ == "__main__":
    base_config = {
        # ── Geometry ──────────────────────────────────────────────────────────
        "geometry_path": r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PyMechanical\PyMechanical-Single-Cell-Lattice\Single_Cell_30mm.stp",

        # ── Mesh ──────────────────────────────────────────────────────────────
        "element_size": 5e-3,

        # ── Modal analysis ────────────────────────────────────────────────────
        "modal_min_freq_hz": 1.0,
        "modal_max_modes":   20,

        # ── Harmonic analysis ─────────────────────────────────────────────────
        "f_start_hz": 500.0,
        "f_end_hz":   3500.0,
        "n_points":   50,

        # ── Material ──────────────────────────────────────────────────────────
        "material_name":          "Resin",
        "material_E_Pa":          2.35e9,
        "material_nu":            0.3,
        "material_density_kgm3":  1220.0,

        # ── Force ─────────────────────────────────────────────────────────────
        "force_face_id":        744,    # geometry entity ID of middle unit face
        "force_value_N":        1.0,
        "force_direction":      "Z",
        "force_x_m":            0.015,   # top face centroid X (default)
        "force_y_m":           -0.015,   # top face centroid Y (default)
        "force_z_m":            0.0315,  # top face Z

        # ── GUI ───────────────────────────────────────────────────────────────
        "show_gui": True,

        # ── Output ────────────────────────────────────────────────────────────
        "output_dir":    r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Sweep",
        "project_name":  "lattice_excitation_sweep",
        "image_name":    "lattice_sweep_meshed.png",
        "bc_image_name": "lattice_sweep_bc.png",
    }

    # ── One-time setup ────────────────────────────────────────────────────────
    mech = setup_session_and_model(base_config)
    setup_material(base_config, mech)
    check_body_material(base_config, mech)
    setup_harmonic_analysis(base_config, mech)
    setup_mesh(base_config, mech)
    check_model_info(base_config, mech)
    export_geometry_image(base_config, mech)

    # ── Free-free: no fixed support applied ──────────────────────────────────

    # ── Modal analysis (once) ─────────────────────────────────────────────────
    run_modal_analysis(base_config, mech)

    # ── Excitation sweep ──────────────────────────────────────────────────────
    for label, fx, fy in EXCITATION_LOCATIONS:
        print(f"\n{'='*60}")
        print(f"Excitation location: {label}  (X={fx}, Y={fy}, Z={base_config['force_z_m']})")
        print(f"{'='*60}")

        # Build per-location config
        config = dict(base_config)
        config["csv_name"]      = f"healthy_{label}_complex.csv"
        config["imag_csv_name"] = f"healthy_{label}_imag_apdl"
        config["real_csv_name"] = f"healthy_{label}_real.csv"
        config["bc_image_name"]       = f"healthy_{label}_bc.png"

        config["force_x_m"] = fx if fx is not None else base_config["force_x_m"]
        config["force_y_m"] = fy if fy is not None else base_config["force_y_m"]

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
        export_bc_view(config, mech)
        add_apdl_imaginary_export(config, mech)
        solve_model(config, mech)
        export_real_displacement(config, mech)
        merge_real_imag_csv(config)
        print_solve_output(mech)

        print(f"  Done: {config['csv_name']}")

    # ── Done ──────────────────────────────────────────────────────────────────
    input("\nAll locations complete. Press Enter to close Mechanical...")
    close_mechanical(base_config, mech)

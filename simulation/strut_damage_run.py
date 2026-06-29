"""
strut_damage_run.py

Runs the healthy lattice geometry but reduces the stiffness of ONE target
strut to simulate partial (graded) damage, instead of physically removing
a strut. Sweep DAMAGE_SEVERITY across runs to build a graded training set.

Add new strut entries to STRUT_GEOMETRY_IDS as you identify their geometry
IDs in Mechanical (right-click a body -> the ID shows in the status bar,
or record a macro like the one used to discover these).
"""

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
    apply_damage_to_strut,
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

# ── Strut label -> Mechanical geometry entity ID ──────────────────────────────
STRUT_GEOMETRY_IDS = {
    "11": 327,
    "12": 712,
    "13": 490,
    "14": 610,
    "21": 511,
    "22": 639,
    "23": 558,
    "24": 786,
}

if __name__ == "__main__":
    TARGET_STRUT     = "11"     # which strut to damage — must be a key in STRUT_GEOMETRY_IDS
    DAMAGE_SEVERITY  = 0.25     # fraction of E to remove (0.25 = 25% reduction)

    config = {
        # ── Geometry ──────────────────────────────────────────────────────────
        "geometry_path": r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PyMechanical\PyMechanical-Single-Cell-Lattice\Single_Cell_30mm.stp",

        # ── Mesh ──────────────────────────────────────────────────────────────
        "element_size": 5e-3,

        # ── Modal analysis ────────────────────────────────────────────────────
        "modal_min_freq_hz": 1.0,
        "modal_max_modes":   10,

        # ── Harmonic analysis ─────────────────────────────────────────────────
        "f_start_hz": 500.0,
        "f_end_hz":   3500.0,
        "n_points":   200,

        # ── Material (base, applied to all bodies) ──────────────────────────────
        "material_name":           "Resin",
        "material_E_Pa":           2.35e9,
        "material_nu":             0.3,
        "material_density_kgm3":   1220.0,

        # ── Strut damage ──────────────────────────────────────────────────────
        "strut_geometry_id": STRUT_GEOMETRY_IDS[TARGET_STRUT],
        "damage_severity":   DAMAGE_SEVERITY,

        # ── Force ─────────────────────────────────────────────────────────────
        "force_face_id":           744,
        "force_value_N":           -1.0,
        "force_direction":         "Z",
        "force_x_m": 0.01,
        "force_y_m": -0.01,
        "force_z_m": 0.0315,

        # ── GUI ───────────────────────────────────────────────────────────────
        "show_gui": True,

        # ── Output ────────────────────────────────────────────────────────────
        "output_dir":    rf"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Strut_{TARGET_STRUT}_Damage_{int(DAMAGE_SEVERITY*100)}",
        "project_name":  f"strut_{TARGET_STRUT}_damage_{int(DAMAGE_SEVERITY*100)}_harmonic",
        "image_name":    "meshed_beam.png",
        "bc_image_name": "bc_view.png",
        "csv_name":      "nodal_displacement_complex.csv",
        "imag_csv_name": "strut_damage_imag_apdl",
        "real_csv_name": "strut_damage_displacement_real.csv",
    }

    # ── Setup ─────────────────────────────────────────────────────────────────
    mech = setup_session_and_model(config)
    setup_material(config, mech)
    check_body_material(config, mech)

    # ── Reduce stiffness of the target strut only ────────────────────────────
    apply_damage_to_strut(config, mech)

    setup_harmonic_analysis(config, mech)
    setup_mesh(config, mech)
    check_model_info(config, mech)
    export_geometry_image(config, mech)

    # ── Free-free: no fixed support applied ──────────────────────────────────

    # ── Modal analysis to find natural frequencies ────────────────────────────
    run_modal_analysis(config, mech)

    # ── Apply remote force on top face ────────────────────────────────────────
    add_remote_force(config, mech)
    export_bc_view(config, mech)

    # ── Solve and export ──────────────────────────────────────────────────────
    add_apdl_imaginary_export(config, mech)
    solve_model(config, mech)
    export_real_displacement(config, mech)
    merge_real_imag_csv(config)
    print_solve_output(mech)

    input("Press Enter to close Mechanical when you are done inspecting...")
    close_mechanical(config, mech)

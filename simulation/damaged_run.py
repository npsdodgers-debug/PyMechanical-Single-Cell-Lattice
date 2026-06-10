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

if __name__ == "__main__":
    config = {
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
        "n_points":   200,

        # ── Material ──────────────────────────────────────────────────────────
        "material_name":          "Resin",
        "material_E_Pa":          2.35e9,
        "material_nu":            0.3,
        "material_density_kgm3":  1220.0,

        # ── Force ─────────────────────────────────────────────────────────────
        "force_face_id":    952,
        "force_value_N":   -1.0,
        "force_direction":  "Z",
        "force_x_m":        0.01,
        "force_y_m":       -0.01,
        "force_z_m":        0.0315,

        # ── GUI ───────────────────────────────────────────────────────────────
        "show_gui": True,

        # ── Output ────────────────────────────────────────────────────────────
        "output_dir":    r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice\Missing_Upper_Strut",
        "project_name":  "missing_strut_harmonic",
        "image_name":    "missing_strut_meshed.png",
        "bc_image_name": "missing_strut_bc.png",
        "csv_name":      "damaged_displacement_complex.csv",
        "imag_csv_name": "damaged_imag_apdl",
        "real_csv_name": "damaged_displacement_real.csv",
    }

    # ── Setup ─────────────────────────────────────────────────────────────────
    mech = setup_session_and_model(config)
    setup_material(config, mech)
    check_body_material(config, mech)
    setup_harmonic_analysis(config, mech)
    setup_mesh(config, mech)
    check_model_info(config, mech)
    export_geometry_image(config, mech)

    # ── Free-free: no fixed support applied ───────────────────────────────────

    # ── Modal analysis ────────────────────────────────────────────────────────
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

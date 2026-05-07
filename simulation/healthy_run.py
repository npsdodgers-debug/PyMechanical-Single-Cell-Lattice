from ansys.mechanical.core import launch_mechanical
import os, shutil, textwrap

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
    save_project,
    close_mechanical,
    run_modal_analysis,
    add_apdl_imaginary_export,
    export_real_displacement,
    merge_real_imag_csv,
)

if __name__ == "__main__":
    config = {
        # ── Geometry ──────────────────────────────────────────────────────────
        "geometry_path": r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PyMechanical\PyMechanical-Single-Cell-Lattice\Single_Cell_30mm.stp",

        # ── Mesh ──────────────────────────────────────────────────────────────
        "element_size": 5e-3,          # meters

        # ── Modal analysis ────────────────────────────────────────────────────
        "modal_min_freq_hz": 1.0,
        "modal_max_modes":   10,

        # ── Harmonic analysis ─────────────────────────────────────────────────
        "f_start_hz": 500.0,
        "f_end_hz":   3500.0,
        "n_points":   200,

        # ── Material ──────────────────────────────────────────────────────────
        "material_name":           "Resin",
        "material_E_Pa":           2.35e9,
        "material_nu":             0.3,
        "material_density_kgm3":   1220.0,

        # ── Force ─────────────────────────────────────────────────────────────
        "force_face_id":           744,                        # geometry entity ID of middle unit face
        "force_value_N":           -1.0,
        "force_direction":         "Z",   # X, Y, or Z
        # Remote force location — defaults to top face centroid if not set.
        # Run once to see corner coordinates printed, then uncomment to target a corner:
         "force_x_m": 0.01,
         "force_y_m": -0.01,
         "force_z_m": 0.0315,
        

        # ── GUI ───────────────────────────────────────────────────────────────
        "show_gui": True,                # set to False to run headless

        # ── Output ────────────────────────────────────────────────────────────
        "output_dir":    r"C:\Users\coetech\Documents\PyMechanical\Single Cell Lattice",
        "project_name":  "cantilever_harmonic",
        "image_name":    "meshed_beam.png",
        "bc_image_name": "bc_view.png",
        "csv_name":      "nodal_displacement_complex.csv",
        "imag_csv_name": "healthy_imag_apdl",
        "real_csv_name": "healthy_displacement_real.csv",

    }

    # ── Setup (runs once) ─────────────────────────────────────────────────────
    mech = setup_session_and_model(config)
    setup_material(config, mech)
    check_body_material(config, mech)
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
    add_apdl_imaginary_export(config, mech)         # APDL snippet for imaginary export
    solve_model(config, mech)
    export_real_displacement(config, mech)
    merge_real_imag_csv(config)
    print_solve_output(mech)

    # ── Inspect in Mechanical GUI before closing ──────────────────────────────
    input("Press Enter to close Mechanical when you are done inspecting...")

    # ── Save and close ────────────────────────────────────────────────────────
    # save_project(config, mech)  # uncomment after PC restart clears lock
    close_mechanical(config, mech)

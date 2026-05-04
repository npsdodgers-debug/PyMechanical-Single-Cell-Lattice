from ansys.mechanical.core import launch_mechanical
import os
import json

from Harmonic_Subfunctions import (
    setup_session_and_model,
    check_body_material,
    setup_mesh,
    check_model_info,
    export_geometry_image,
    setup_harmonic_analysis,
    add_fixed_on_support_face,
    add_nodal_force,
    export_bc_view,
    solve_model,
    print_solve_output,
    close_mechanical,
    export_centerline_displacement,
    export_aggregate_frf,
    get_top_face_nodes,
    select_node_by_id,
    run_modal_analysis,
    add_apdl_imaginary_export,
    export_real_displacement,
    merge_real_imag_csv,
)

# ── Excitation locations (fraction of beam length) ────────────────────────────
EXCITATION_LOCATIONS = [0.50, 1.00]   # 50% and 100% of beam length

if __name__ == "__main__":
    base_config = {
        # ── Geometry ──────────────────────────────────────────────────────────
        "geometry_path": r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PyMechanical\Thin_beam\Thin_Beam.SLDPRT",

        # ── Mesh ──────────────────────────────────────────────────────────────
        "element_size": 1.6e-3,

        # ── Harmonic analysis ─────────────────────────────────────────────────
        "f_start_hz": 1.0,
        "f_end_hz":   1000.0,
        "n_points":   200,

        # ── Force ─────────────────────────────────────────────────────────────
        "force_value_N":          1.0,
        "remote_named_selection": "FORCE_NODE",

        # ── GUI ───────────────────────────────────────────────────────────────
        "show_gui": True,

        # ── Output ────────────────────────────────────────────────────────────
        "output_dir":    r"C:\Users\coetech\Documents\PyMechanical\Outputs",
        "project_name":  "cantilever_excitation_sweep",
        "image_name":    "excitation_sweep_beam.png",
        "bc_image_name": "excitation_sweep_bc.png",
    }

    # ── One-time setup ────────────────────────────────────────────────────────
    mech = setup_session_and_model(base_config)
    check_body_material(base_config, mech)
    setup_harmonic_analysis(base_config, mech)
    setup_mesh(base_config, mech)
    check_model_info(base_config, mech)
    export_geometry_image(base_config, mech)

    # ── Fixed support ─────────────────────────────────────────────────────────
    fix_support_script = """
import json
mesh_data = Model.Analyses[0].MeshData
all_nodes = mesh_data.Nodes
min_z = min(n.Z for n in all_nodes)
support_node_ids = [n.Id for n in all_nodes if abs(n.Z - min_z) < 1e-6]
result = json.dumps(support_node_ids)
result
"""
    out = mech.run_python_script(fix_support_script)
    support_node_ids = json.loads(out)
    print(f"Found {len(support_node_ids)} nodes on support face (z=0)")

    create_support_ns_script = f"""
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum
model = Model
mesh_data = model.Analyses[0].MeshData
selection_manager = ExtAPI.SelectionManager
sel_info = selection_manager.CreateSelectionInfo(SelectionTypeEnum.MeshNodes)
sel_info.Ids = {support_node_ids}
selection_manager.ClearSelection()
selection_manager.NewSelection(sel_info)

ns_container = model.NamedSelections
if ns_container is None:
    dummy = model.AddNamedSelection()
    dummy.Delete()
    ns_container = model.NamedSelections

for ns in list(ns_container.Children):
    if ns.Name == "NS_SUPPORT_FACE":
        ns.Delete()

ns = model.AddNamedSelection()
ns.Name = "NS_SUPPORT_FACE"
ns.Location = sel_info
ns.Generate()
result = "OK: NS_SUPPORT_FACE created with " + str(len(support_node_ids)) + " nodes"
result
"""
    out = mech.run_python_script(create_support_ns_script)
    print("Mechanical says (support NS):", out)
    add_fixed_on_support_face(base_config, mech)

    # ── Modal analysis (once) ─────────────────────────────────────────────────
    run_modal_analysis(base_config, mech)

    # ── Get top face nodes and beam length (once) ─────────────────────────────
    top_nodes = get_top_face_nodes(mech)

    beam_info_script = f"""
import json
mesh_data = Model.Analyses[0].MeshData
node_ids = {top_nodes}
all_z = [mesh_data.NodeById(nid).Z for nid in node_ids]
result = json.dumps({{"z_min": min(all_z), "z_max": max(all_z)}})
result
"""
    out = mech.run_python_script(beam_info_script)
    beam_info = json.loads(out)
    z_min = beam_info["z_min"]
    z_max = beam_info["z_max"]
    beam_length = z_max - z_min
    print(f"Beam length from mesh: {beam_length:.4f} mm  (z_min={z_min:.4f}, z_max={z_max:.4f})")

    # ── Excitation sweep ──────────────────────────────────────────────────────
    for frac in EXCITATION_LOCATIONS:
        target_z = z_min + frac * beam_length
        label = f"exc{int(frac*100):03d}pct"
        print(f"\n{'='*60}")
        print(f"Excitation location: {frac*100:.0f}% of beam  (target Z = {target_z:.2f} mm)")
        print(f"{'='*60}")

        # Find top-face node closest to target Z
        find_exc_node_script = f"""
import json
mesh_data = Model.Analyses[0].MeshData
node_ids = {top_nodes}
target_z = {target_z}
exc_node_id = min(node_ids, key=lambda nid: abs(mesh_data.NodeById(nid).Z - target_z))
exc_node = mesh_data.NodeById(exc_node_id)
result = json.dumps({{"id": exc_node_id, "x": exc_node.X, "y": exc_node.Y, "z": exc_node.Z}})
result
"""
        out = mech.run_python_script(find_exc_node_script)
        exc_info = json.loads(out)
        exc_node_id = exc_info["id"]
        print(f"  Force node: ID={exc_node_id}, Z={exc_info['z']:.4f} mm  "
              f"(requested {target_z:.2f} mm)")

        # Remove any existing nodal forces and APDL snippets from the harmonic analysis
        clear_force_script = """
harmonic = None
for a in Model.Analyses:
    if "Harmonic" in a.Name:
        harmonic = a
        break
cleared = []
if harmonic is not None:
    # Clear forces from analysis children
    for child in list(harmonic.Children):
        type_name = child.GetType().Name
        if "Force" in type_name:
            child.Delete()
            cleared.append("Force")
    # Clear APDL snippets from solution children
    for child in list(harmonic.Solution.Children):
        type_name = child.GetType().Name
        if "Command" in type_name:
            child.Delete()
            cleared.append("APDL snippet")
result = "OK: cleared " + str(cleared)
result
"""
        out = mech.run_python_script(clear_force_script)
        print(f"  Mechanical says (clear force): {out}")

        # Build per-location config for output filenames
        config = dict(base_config)
        config["csv_name"]            = f"healthy_{label}_complex.csv"
        config["centerline_csv_name"] = f"healthy_{label}_centerline.csv"
        config["aggregate_csv_name"]  = f"healthy_{label}_aggregate.csv"
        config["imag_csv_name"]       = f"healthy_{label}_imag_apdl"
        config["real_csv_name"]       = f"healthy_{label}_real.csv"
        config["bc_image_name"]       = f"healthy_{label}_bc.png"
        # Skip if already completed
        complex_csv = os.path.join(config["output_dir"], config["csv_name"])
        if os.path.exists(complex_csv):
            print(f"  Skipping {label} — output already exists: {config['csv_name']}")
            continue

        # Apply force and solve
        select_node_by_id(mech, exc_node_id, "FORCE_NODE")
        add_nodal_force(config, mech)
        export_bc_view(config, mech)
        add_apdl_imaginary_export(config, mech)
        solve_model(config, mech)
        export_real_displacement(config, mech)
        export_centerline_displacement(config, mech)
        export_aggregate_frf(config, mech)
        merge_real_imag_csv(config)
        print_solve_output(mech)

        print(f"  Done: {config['csv_name']}")

    # ── Done ──────────────────────────────────────────────────────────────────
    input("\nAll locations complete. Press Enter to close Mechanical...")
    close_mechanical(base_config, mech)

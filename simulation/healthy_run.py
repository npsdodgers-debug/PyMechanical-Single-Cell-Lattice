from ansys.mechanical.core import launch_mechanical
import os, shutil, textwrap
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
    select_face_by_centroid_generic,
    export_bc_view,
    solve_model,
    print_solve_output,
    save_project,
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

if __name__ == "__main__":
    config = {
        # ── Geometry ──────────────────────────────────────────────────────────
        "geometry_path": r"C:\Users\coetech\OneDrive - Texas A&M University\Research\PyMechanical\Thin_beam\Thin_Beam.SLDPRT",

        # ── Mesh ──────────────────────────────────────────────────────────────
        "element_size": 1.6e-3,          # meters

        # ── Harmonic analysis ─────────────────────────────────────────────────
        "f_start_hz": 10.0,
        "f_end_hz":   5000.0,
        "n_points":   150,

        # ── Force ─────────────────────────────────────────────────────────────
        "force_value_N":           1.0,  # amplitude, Y-direction
        "remote_named_selection":  "FORCE_NODE",
        

        # ── GUI ───────────────────────────────────────────────────────────────
        "show_gui": True,                # set to False to run headless

        # ── Output ────────────────────────────────────────────────────────────
        "output_dir":    r"C:\Users\coetech\Documents\PyMechanical\Outputs",
        "project_name":  "cantilever_harmonic",
        "image_name":    "meshed_beam.png",
        "bc_image_name": "bc_view.png",
        "csv_name":              "nodal_displacement_complex.csv",
        "centerline_csv_name":   "nodal_displacement_centerline.csv",
        "aggregate_csv_name":    "frf_aggregate.csv",
        "imag_csv_name":         "healthy_imag_apdl",
        "real_csv_name":         "healthy_displacement_real.csv",

    }

    # ── Setup (runs once) ─────────────────────────────────────────────────────
    mech = setup_session_and_model(config)
    check_body_material(config, mech)
    setup_harmonic_analysis(config, mech)
    setup_mesh(config, mech)
    check_model_info(config, mech)
    export_geometry_image(config, mech)

    # ── Fixed support: select all nodes at z=0 ────────────────────────────────
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

# Create NamedSelections branch if it doesn't exist
ns_container = model.NamedSelections
if ns_container is None:
    dummy = model.AddNamedSelection()
    dummy.Delete()
    ns_container = model.NamedSelections

# Delete existing NS with same name if present
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
    add_fixed_on_support_face(config, mech)

    # ── Modal analysis to find natural frequencies ────────────────────────────
    run_modal_analysis(config, mech)

    # ── Pick the tip node on the top face (max Z) ─────────────────────────────
    top_nodes = get_top_face_nodes(mech)

    find_tip_script = f"""
import json
mesh_data = Model.Analyses[0].MeshData
node_ids = {top_nodes}
tip_node_id = max(node_ids, key=lambda nid: mesh_data.NodeById(nid).Z)
tip_node = mesh_data.NodeById(tip_node_id)
result = json.dumps({{"id": tip_node_id, "x": tip_node.X, "y": tip_node.Y, "z": tip_node.Z}})
result
"""
    out = mech.run_python_script(find_tip_script)
    tip_info = json.loads(out)
    tip_node_id = tip_info["id"]
    print(f"Tip node selected: ID={tip_node_id}, X={tip_info['x']:.6f}, Y={tip_info['y']:.6f}, Z={tip_info['z']:.6f} m")


    # ── Apply force at tip node ───────────────────────────────────────────────
    select_node_by_id(mech, tip_node_id, "FORCE_NODE")
    add_nodal_force(config, mech)
    export_bc_view(config, mech)

    # ── Solve and export ──────────────────────────────────────────────────────
    add_apdl_imaginary_export(config, mech)         # APDL snippet for imaginary export
    solve_model(config, mech)
    export_real_displacement(config, mech)          # real part via DPF
    export_centerline_displacement(config, mech)    # top centerline nodes only
    export_aggregate_frf(config, mech)              # one row per frequency
    merge_real_imag_csv(config)                     # combine real + imaginary into complex CSV
    print_solve_output(mech)

    # ── Inspect in Mechanical GUI before closing ──────────────────────────────
    input("Press Enter to close Mechanical when you are done inspecting...")

    # ── Save and close ────────────────────────────────────────────────────────
    # save_project(config, mech)  # uncomment after PC restart clears lock
    close_mechanical(config, mech)

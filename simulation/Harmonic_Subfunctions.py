from ansys.mechanical.core import launch_mechanical  # pyMechanical
import os
import shutil
import textwrap

# =============================================================================
#
# =============================================================================

def setup_session_and_model(config):
    geometry_path = config["geometry_path"]

    # show_gui=True opens the Mechanical GUI; False runs headless (batch mode)
    show_gui = config.get("show_gui", False)
    mechanical = launch_mechanical(batch=not show_gui)
    proj_dir = mechanical.project_directory

    source_geom = geometry_path
    target_geom = os.path.join(proj_dir, os.path.basename(source_geom))
    if not os.path.exists(target_geom):
        shutil.copy(source_geom, target_geom)

    script = textwrap.dedent(
        f"""
        from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory, GeometryImportPreference
        from Ansys.ACT.Mechanical.Utilities import GeometryImportPreferences

        model = Model

        geom_import = model.GeometryImportGroup.AddGeometryImport()
        geom_prefs = GeometryImportPreferences()
        geom_prefs.ProcessNamedSelections = True
        geom_format = GeometryImportPreference.Format.Automatic
        geom_import.Import(r"{target_geom}", geom_format, geom_prefs)

        bodies = model.GetChildren(DataModelObjectCategory.Body, True)
        result = "OK: bodies = " + str(bodies.Count)
        result
        """
    )

    out = mechanical.run_python_script(script)
    print("Mechanical says (common):", out)
    return mechanical

# =============================================================================
#
# =============================================================================

def check_body_material(config, mechanical):
    """
    Query and print the material assigned to the first body.
    """
    script = """
from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory

bodies = Model.GetChildren(DataModelObjectCategory.Body, True)
if bodies.Count == 0:
    result = "No bodies found"
else:
    body = bodies[0]
    mat_name = str(body.Material)
    result = "Body 0 material = " + mat_name
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (material check):", out)

# =============================================================================
#
# =============================================================================

def setup_mesh(config, mechanical):
    element_size = config["element_size"]

    script = f"""
from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory

model = Model
mesh = model.Mesh
mesh.ElementSize = Quantity("{element_size} [m]")
mesh.GenerateMesh()

if model.Analyses.Count > 0:
    mesh_data = model.Analyses[0].MeshData
    elem_count = mesh_data.ElementCount
    node_count = mesh_data.NodeCount
    result = "OK: mesh generated with element size = {element_size} m, elements=" + str(elem_count) + ", nodes=" + str(node_count)
else:
    result = "OK: mesh generated with element size = {element_size} m (no analyses yet)"

result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (mesh):", out)

# =============================================================================
#
# =============================================================================

def save_project(config, mechanical):
    """
    Save the current Mechanical project to the given folder, overwriting if it exists.
    """
    out_dir = config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")
    base_name = config.get("project_name", "cantilever_harmonic")

    script = f"""
import os
import glob

out_dir = r"{out_dir}"
base_name = r"{base_name}"

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

pattern = os.path.join(out_dir, base_name + "*")
for f in glob.glob(pattern):
    try:
        os.remove(f)
    except Exception:
        pass

full_path = os.path.join(out_dir, base_name + ".mechdb")
ExtAPI.DataModel.Project.SaveAs(full_path)

"OK: project saved to " + full_path
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (save):", out)

# =============================================================================
#
# =============================================================================

def close_mechanical(config, mechanical):
    mechanical.exit(force=True)

# =============================================================================
#
# =============================================================================

def check_model_info(config, mechanical):
    """
    Print basic info: body, element, and node counts.
    """
    script = """
from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory

model = Model
bodies = model.GetChildren(DataModelObjectCategory.Body, True)
body_count = bodies.Count

if model.Analyses.Count == 0:
    result = "bodies=" + str(body_count) + ", elements=0, nodes=0 (no analyses found)"
else:
    mesh_data = model.Analyses[0].MeshData
    elem_count = mesh_data.ElementCount
    node_count = mesh_data.NodeCount
    result = "bodies=" + str(body_count) + ", elements=" + str(elem_count) + ", nodes=" + str(node_count)

result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (info):", out)

# =============================================================================
#
# =============================================================================

def export_geometry_image(config, mechanical):
    out_dir = config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")
    img_name = config.get("image_name", "model_view.png")

    script = f"""
import os

out_dir = r"{out_dir}"
img_name = r"{img_name}"

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

full_path = os.path.join(out_dir, img_name)

model = Model
mesh = model.Mesh
mesh.ElementSize = mesh.ElementSize
mesh.GenerateMesh()

Graphics = ExtAPI.Graphics
Graphics.Camera.SetFit()
Graphics.ExportImage(full_path)

"OK: image exported to " + full_path
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (image):", out)

# =============================================================================
#
# =============================================================================

def select_face_by_centroid_generic(mechanical, target_point, ns_name):
    script = f"""
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum
import math

target = ({target_point[0]}, {target_point[1]}, {target_point[2]})

model = Model
selection_manager = ExtAPI.SelectionManager
sel_info = selection_manager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)

closest_face = None
closest_dist = None

for assembly in ExtAPI.DataModel.GeoData.Assemblies:
    for part in assembly.AllParts:
        for body in part.Bodies:
            for face in body.Faces:
                cx, cy, cz = face.Centroid
                dx = cx - target[0]
                dy = cy - target[1]
                dz = cz - target[2]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if closest_dist is None or dist < closest_dist:
                    closest_dist = dist
                    closest_face = face

if closest_face is None:
    result = "ERROR: no faces found in model"
else:
    sel_info.Entities = [closest_face]
    selection_manager.ClearSelection()
    selection_manager.NewSelection(sel_info)

    ns_container = model.NamedSelections
    if ns_container is None:
        ns_container = model.AddNamedSelection()
        ns_container.Name = "TEMP_CONTAINER"
        ns_container.Delete()
        ns_container = model.NamedSelections

    existing = []
    if ns_container is not None:
        for ns in ns_container.Children:
            if ns.Name == "{ns_name}":
                existing.append(ns)
    for ns in existing:
        ns.Delete()

    ns = model.AddNamedSelection()
    ns.Name = "{ns_name}"
    ns.Location = sel_info
    ns.Generate()

    result = "OK: {ns_name} created (closest_dist = " + str(closest_dist) + " m)"

result
"""
    out = mechanical.run_python_script(script)
    print(f"Mechanical says ({ns_name}):", out)

# =============================================================================
#
# =============================================================================

def add_nodal_force(config, mechanical):
    F_amp     = float(config.get("force_value_N", 1.0))
    direction = config.get("force_direction", "Y").upper()
    ns_name   = config.get("remote_named_selection", "FORCE_NODE")

    fx = F_amp if direction == "X" else 0.0
    fy = F_amp if direction == "Y" else 0.0
    fz = F_amp if direction == "Z" else 0.0

    script = f"""
model = Model
harmonic = model.Analyses[0]
harmonic.Activate()

ns = None
for child in model.NamedSelections.Children:
    if child.Name == "{ns_name}":
        ns = child
        break

if ns is None:
    raise RuntimeError("Named selection '{ns_name}' not found")

force = harmonic.AddNodalForce()
force.Location = ns
force.XComponent.Output.DiscreteValues = [Quantity("{fx} [N]")]
force.YComponent.Output.DiscreteValues = [Quantity("{fy} [N]")]
force.ZComponent.Output.DiscreteValues = [Quantity("{fz} [N]")]

result = "OK: nodal force {F_amp} N ({direction}-direction) applied to NS '{ns_name}'"
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (nodal force):", out)

# =============================================================================
#
# =============================================================================

def setup_harmonic_analysis(config, mechanical):
    f_start = float(config.get("f_start_hz", 8000.0))
    f_end   = float(config.get("f_end_hz",   12000.0))
    n_steps = int(config.get("n_points", 10))

    script = f"""
from System.Collections.Generic import List

model = Model

for a in list(model.Analyses):
    if a.Name.startswith("Harmonic"):
        a.Delete()

harmonic = model.AddHarmonicResponseAnalysis()
settings = harmonic.AnalysisSettings

settings.SolutionMethod = HarmonicMethod.Full

settings.RangeMinimum = Quantity("{f_start} [Hz]")
settings.RangeMaximum = Quantity("{f_end} [Hz]")
settings.SolutionIntervals = {n_steps}

settings.StructuralDampingCoefficient = 0.01

result = "OK: harmonic reset range {f_start}-{f_end} Hz, steps={n_steps}, damping=1%"
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (harmonic setup):", out)

# =============================================================================
#
# =============================================================================

def add_apdl_imaginary_export(config, mechanical):
    """
    Adds an APDL Commands snippet to the Harmonic Response solution that
    exports imaginary nodal displacements to CSV after solving.
    Frequencies are derived from the config to match the harmonic analysis.
    """
    f_start  = float(config.get("f_start_hz", 10.0))
    f_end    = float(config.get("f_end_hz", 5000.0))
    n_points = int(config.get("n_points", 100))
    out_dir  = config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")
    csv_stem = config.get("imag_csv_name", "nodal_imag_apdl")

    # Step size matching the harmonic analysis spacing
    freq_step = (f_end - f_start) / max(n_points - 1, 1)
    csv_path  = out_dir.replace("\\", "/") + "/" + csv_stem

    apdl = f"""
/POST1
FREQ_MIN = {f_start}
FREQ_MAX = {f_end}
FREQ_STEP = {freq_step:.4f}

*CFOPEN,'{csv_path}','csv',,
*VWRITE,'Freq(Hz)','Node','X-Coord','Y-Coord','Z-Coord','X-Disp.','Y-Disp.','Z-Disp.'
(A15,A15,A15,A15,A15,A15,A15,A15)

*GET,NNODES,NODE,0,COUNT

*DO,FREQ,FREQ_MIN,FREQ_MAX,FREQ_STEP
    set,,,,IMAG,FREQ
    *DO,N,1,NNODES,1
        *GET,XCOORD,NODE,N,LOC,X
        *GET,YCOORD,NODE,N,LOC,Y
        *GET,ZCOORD,NODE,N,LOC,Z
        *GET,XDISP,NODE,N,U,X
        *GET,YDISP,NODE,N,U,Y
        *GET,ZDISP,NODE,N,U,Z
        *VWRITE,FREQ,N,XCOORD,YCOORD,ZCOORD,XDISP,YDISP,ZDISP
        (G15.5,',',G15.5,',',G15.5,',',G15.5,',',G15.5,',',E15.7,',',E15.7,',',E15.7)
    *ENDDO
*ENDDO

*CFCLOS
"""

    script = f"""
for analysis in Model.Analyses:
    if analysis.Name.startswith("Harmonic"):
        snippet = analysis.Solution.AddCommandSnippet()
        snippet.Input = {repr(apdl)}
        result = "OK: APDL imaginary export snippet added"
        break
else:
    result = "ERROR: No harmonic analysis found"
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (APDL snippet):", out)

# =============================================================================
#
# =============================================================================

def solve_model(config, mechanical):
    script = """
analysis = Model.Analyses[0]
analysis.Solution.Solve()
result = "OK: analysis solved, status = " + str(analysis.Solution.Status)
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (solve):", out)

# =============================================================================
#
# =============================================================================

def add_fixed_on_support_face(config, mechanical):
    """
    Add a fixed support on the cantilever root for the harmonic analysis.
    Requires a Named Selection called 'NS_SUPPORT_FACE' on the clamped end.
    """
    script = """
from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory

model = Model

harmonic = model.Analyses[0]
harmonic.Activate()

ns = None
for n in model.NamedSelections.Children:
    if n.Name == "NS_SUPPORT_FACE":
        ns = n
        break

if ns is None:
    raise RuntimeError("Named selection 'NS_SUPPORT_FACE' not found")

fixed = harmonic.AddFixedSupport()
fixed.Location = ns

result = "OK: fixed support applied to NS_SUPPORT_FACE in harmonic analysis"
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (fixed support):", out)

# =============================================================================
#
# =============================================================================

def export_bc_view(config, mechanical):
    """
    Activate the analysis (with BC symbols visible) and export an image.
    """
    out_dir = config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")
    img_name = config.get("bc_image_name", "bc_view.png")

    script = f"""
import os

out_dir = r"{out_dir}"
img_name = r"{img_name}"

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

full_path = os.path.join(out_dir, img_name)

analysis = Model.Analyses[0]
analysis.Activate()

Graphics = ExtAPI.Graphics
Graphics.Camera.SetFit()
Graphics.ExportImage(full_path)

"OK: BC view image exported to " + full_path
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (BC view):", out)

# =============================================================================
#
# =============================================================================

def print_solve_output(mechanical):
    """
    Print the tail of the Mechanical solve output file (solve.out).
    """
    script = """
import os

analysis = Model.Analyses[0]
solve_dir = analysis.WorkingDir
solve_out = os.path.join(solve_dir, "solve.out")

if os.path.isfile(solve_out):
    with open(solve_out, "r") as f:
        lines = f.readlines()
    tail = "".join(lines[-50:])
    result = tail
else:
    result = "No solve.out file found in " + str(solve_dir)

result
"""
    out = mechanical.run_python_script(script)
    print("=== solve.out tail ===")
    print(out)

# =============================================================================
#
# =============================================================================

def export_complex_displacement(config, mechanical):
    """
    Export complex nodal displacements at every harmonic frequency to a CSV.
    In Ansys harmonic results, real and imaginary parts are stored as separate
    consecutive sets: set 2k-1 = real, set 2k = imaginary for frequency k.
    One row per (frequency, node):
      freq_Hz,node_id,x,y,z,ux_real,ux_imag,uy_real,uy_imag,uz_real,uz_imag
    """
    script = r"""
def extract_all_freq_nodal_displacement(analysis, out_dir, csv_name):
    import mech_dpf
    import Ans.DataProcessing as dpf
    import os

    def get_field_data(dataSource, set_id):
        time_scoping = dpf.Scoping()
        time_scoping.Location = ""
        time_scoping.Ids = [set_id]
        u_op = dpf.operators.result.displacement()
        u_op.inputs.data_sources.Connect(dataSource)
        u_op.inputs.time_scoping.Connect(time_scoping)
        u_fc = u_op.outputs.fields_container.GetData()
        if not u_fc:
            return None, None
        u_field = u_fc[0]
        if not hasattr(u_field, "Scoping") or not hasattr(u_field, "Data"):
            return None, None
        return u_field.Scoping.Ids, u_field.Data

    try:
        mech_dpf.setExtAPI(ExtAPI)
        dataSource = dpf.DataSources(analysis.ResultFileName)

        model = dpf.Model(dataSource)
        tfs = model.TimeFreqSupport
        n_sets = tfs.NumberSets
        if n_sets == 0:
            return "ERROR: No frequency sets in result file"

        # Diagnostic: print set layout to understand real/imag ordering
        diag = "n_sets={} | ".format(n_sets)
        for i in range(min(6, n_sets)):
            diag += "set{}={}Hz ".format(i+1, round(tfs.GetTimeFreq(i), 2))
        print(diag)

        # Ansys harmonic: all real sets first, then all imaginary sets
        # Sets 1..n_freqs = real parts, sets n_freqs+1..2*n_freqs = imaginary parts
        n_freqs = n_sets // 2
        freqs = [tfs.GetTimeFreq(i) for i in range(n_freqs)]

        mesh_data = analysis.MeshData

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        csv_path = os.path.join(out_dir, csv_name)

        with open(csv_path, "w") as f:
            f.write("freq_Hz,node_id,x,y,z,ux_real,ux_imag,uy_real,uy_imag,uz_real,uz_imag\n")

            for freq_idx in range(n_freqs):
                freq_hz = freqs[freq_idx]
                real_set = freq_idx + 1            # 1-based: 1, 2, 3 ... n_freqs
                imag_set = freq_idx + 1 + n_freqs  # 1-based: n_freqs+1, n_freqs+2 ...

                real_ids, real_data = get_field_data(dataSource, real_set)
                imag_ids, imag_data = get_field_data(dataSource, imag_set)

                if real_ids is None:
                    continue

                # Build imaginary lookup dict for fast access
                imag_lookup = {}
                if imag_ids is not None and imag_data is not None:
                    for i, nid in enumerate(imag_ids):
                        imag_lookup[nid] = (
                            imag_data[i * 3],
                            imag_data[i * 3 + 1],
                            imag_data[i * 3 + 2],
                        )

                for i, nid in enumerate(real_ids):
                    try:
                        node = mesh_data.NodeById(nid)
                    except:
                        continue

                    ux_r = real_data[i * 3]
                    uy_r = real_data[i * 3 + 1]
                    uz_r = real_data[i * 3 + 2]

                    ux_im, uy_im, uz_im = imag_lookup.get(nid, (0.0, 0.0, 0.0))

                    f.write("{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10}\n".format(
                        freq_hz,
                        nid,
                        node.X, node.Y, node.Z,
                        ux_r, ux_im,
                        uy_r, uy_im,
                        uz_r, uz_im,
                    ))

        return "OK: complex nodal displacements exported to {}".format(csv_path)

    except Exception as e:
        return "ERROR in DPF displacement extraction: {}".format(e)

analysis = DataModel.AnalysisList[0]
out_dir = r""" + repr(config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")) + r"""
csv_name = r""" + repr(config.get("csv_name", "nodal_displacement_complex.csv")) + r"""
result = extract_all_freq_nodal_displacement(analysis, out_dir, csv_name)
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (export all freq complex displacements):", out)

# =============================================================================
#
# =============================================================================

def export_real_displacement(config, mechanical):
    """
    Export real-part-only nodal displacements to a separate CSV.
    Uses same DPF extraction as export_complex_displacement but writes
    only the real components.
    Schema: freq_Hz, node_id, x, y, z, ux_real, uy_real, uz_real
    """
    script = r"""
def extract_real_displacement(analysis, out_dir, csv_name):
    import mech_dpf
    import Ans.DataProcessing as dpf
    import os

    def get_field_data(dataSource, set_id):
        time_scoping = dpf.Scoping()
        time_scoping.Location = ""
        time_scoping.Ids = [set_id]
        u_op = dpf.operators.result.displacement()
        u_op.inputs.data_sources.Connect(dataSource)
        u_op.inputs.time_scoping.Connect(time_scoping)
        u_fc = u_op.outputs.fields_container.GetData()
        if not u_fc:
            return None, None
        u_field = u_fc[0]
        if not hasattr(u_field, "Scoping") or not hasattr(u_field, "Data"):
            return None, None
        return u_field.Scoping.Ids, u_field.Data

    try:
        mech_dpf.setExtAPI(ExtAPI)
        dataSource = dpf.DataSources(analysis.ResultFileName)
        model = dpf.Model(dataSource)
        tfs = model.TimeFreqSupport
        n_sets = tfs.NumberSets
        if n_sets == 0:
            return "ERROR: No frequency sets found"

        n_freqs = n_sets
        freqs = [tfs.GetTimeFreq(i) for i in range(n_freqs)]
        mesh_data = analysis.MeshData

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        csv_path = os.path.join(out_dir, csv_name)
        with open(csv_path, "w") as f:
            f.write("freq_Hz,node_id,x,y,z,ux_real,uy_real,uz_real\n")
            for freq_idx in range(n_freqs):
                freq_hz = freqs[freq_idx]
                real_set = freq_idx + 1
                real_ids, real_data = get_field_data(dataSource, real_set)
                if real_ids is None:
                    continue
                for i, nid in enumerate(real_ids):
                    try:
                        node = mesh_data.NodeById(nid)
                    except:
                        continue
                    f.write("{},{},{},{},{},{},{},{}\n".format(
                        freq_hz, nid, node.X, node.Y, node.Z,
                        real_data[i*3], real_data[i*3+1], real_data[i*3+2]
                    ))
        return "OK: real displacement exported to {}".format(csv_path)
    except Exception as e:
        return "ERROR: {}".format(e)

analysis = DataModel.AnalysisList[0]
out_dir = r""" + repr(config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")) + r"""
csv_name = r""" + repr(config.get("real_csv_name", "nodal_displacement_real.csv")) + r"""
result = extract_real_displacement(analysis, out_dir, csv_name)
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (export real displacements):", out)

# =============================================================================
#
# =============================================================================

def merge_real_imag_csv(config):
    """
    Merges the real-only CSV (from DPF) and imaginary-only CSV (from APDL)
    into a single combined CSV matched on node_id and nearest frequency.
    Output schema: freq_Hz, node_id, x, y, z, ux_real, uy_real, uz_real,
                   ux_imag, uy_imag, uz_imag
    """
    import pandas as pd
    import os

    out_dir      = config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")
    real_name    = config.get("real_csv_name", "nodal_displacement_real.csv")
    imag_name    = config.get("imag_csv_name", "notch_imag_apdl") + ".csv"
    combined_name = config.get("csv_name", "notch_displacement_complex.csv")

    real_path    = os.path.join(out_dir, real_name)
    imag_path    = os.path.join(out_dir, imag_name)
    combined_path = os.path.join(out_dir, combined_name)

    real_df = pd.read_csv(real_path)
    imag_df = pd.read_csv(imag_path, skiprows=1, header=None, sep=',',
                          names=['freq_Hz','node_id','x','y','z','ux_imag','uy_imag','uz_imag'])
    imag_df = imag_df.apply(lambda col: pd.to_numeric(col.astype(str).str.strip(), errors='coerce'))
    imag_df = imag_df.dropna(subset=['freq_Hz','node_id'])

    # Map each real frequency to the nearest APDL frequency
    real_freqs = sorted(real_df['freq_Hz'].unique())
    imag_freqs = sorted(imag_df['freq_Hz'].dropna().unique())

    freq_map = {}
    for rf in real_freqs:
        closest = min(imag_freqs, key=lambda x: abs(x - rf))
        freq_map[rf] = closest

    print(f"Matched {len(freq_map)} of {len(real_freqs)} frequencies")

    rows = []
    for real_freq, imag_freq in freq_map.items():
        r  = real_df[real_df['freq_Hz'] == real_freq].set_index('node_id')
        im = imag_df[abs(imag_df['freq_Hz'] - imag_freq) < 0.01].set_index('node_id')
        # Use APDL x,y,z (model units = mm); DPF returns meters which breaks
        # the driving-point node lookup in load_frf_pipeline.
        r_vals = r.drop(columns=['x', 'y', 'z'])
        merged = r_vals.join(im[['x', 'y', 'z', 'ux_imag', 'uy_imag', 'uz_imag']], how='inner')
        merged['freq_Hz'] = real_freq
        rows.append(merged.reset_index())

    combined = pd.concat(rows, ignore_index=True)
    combined = combined[['freq_Hz','node_id','x','y','z',
                          'ux_real','uy_real','uz_real',
                          'ux_imag','uy_imag','uz_imag']]
    combined.to_csv(combined_path, index=False)
    print(f"Combined CSV saved: {combined_path} ({len(combined):,} rows)")

# =============================================================================
#
# =============================================================================

def export_centerline_displacement(config, mechanical):
    """
    Export complex nodal displacements for centerline nodes only.
    Centerline = nodes at max Y (top face) and center X.
    Same schema as export_complex_displacement:
      freq_Hz,node_id,x,y,z,ux_real,ux_imag,uy_real,uy_imag,uz_real,uz_imag
    Produces a much smaller file (~50-100 nodes vs 4000+) capturing the
    full mode shape along the beam length.
    """
    script = r"""
def export_centerline(analysis, out_dir, csv_name):
    import mech_dpf
    import Ans.DataProcessing as dpf
    import os

    def get_field_data(dataSource, set_id):
        time_scoping = dpf.Scoping()
        time_scoping.Location = ""
        time_scoping.Ids = [set_id]
        u_op = dpf.operators.result.displacement()
        u_op.inputs.data_sources.Connect(dataSource)
        u_op.inputs.time_scoping.Connect(time_scoping)
        u_fc = u_op.outputs.fields_container.GetData()
        if not u_fc:
            return None, None
        u_field = u_fc[0]
        if not hasattr(u_field, "Scoping") or not hasattr(u_field, "Data"):
            return None, None
        return u_field.Scoping.Ids, u_field.Data

    try:
        mech_dpf.setExtAPI(ExtAPI)
        dataSource = dpf.DataSources(analysis.ResultFileName)
        model_dpf = dpf.Model(dataSource)
        tfs = model_dpf.TimeFreqSupport
        n_sets = tfs.NumberSets
        if n_sets == 0:
            return "ERROR: No frequency sets in result file"

        n_freqs = n_sets // 2
        freqs = [tfs.GetTimeFreq(i * 2) for i in range(n_freqs)]

        mesh_data = analysis.MeshData
        all_nodes = mesh_data.Nodes

        # Identify centerline nodes: max Y and center X
        max_y   = max(n.Y for n in all_nodes)
        min_x   = min(n.X for n in all_nodes)
        max_x   = max(n.X for n in all_nodes)
        center_x = (min_x + max_x) / 2.0
        tol = 0.01  # mm tolerance

        centerline_ids = set(
            n.Id for n in all_nodes
            if abs(n.Y - max_y) < tol and abs(n.X - center_x) < tol
        )

        if not centerline_ids:
            return "ERROR: No centerline nodes found (check tolerance)"

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        csv_path = os.path.join(out_dir, csv_name)

        with open(csv_path, "w") as f:
            f.write("freq_Hz,node_id,x,y,z,ux_real,ux_imag,uy_real,uy_imag,uz_real,uz_imag\n")

            for freq_idx in range(n_freqs):
                freq_hz = freqs[freq_idx]
                real_set = freq_idx * 2 + 1
                imag_set = freq_idx * 2 + 2

                real_ids, real_data = get_field_data(dataSource, real_set)
                imag_ids, imag_data = get_field_data(dataSource, imag_set)

                if real_ids is None:
                    continue

                imag_lookup = {}
                if imag_ids is not None and imag_data is not None:
                    for i, nid in enumerate(imag_ids):
                        imag_lookup[nid] = (
                            imag_data[i * 3],
                            imag_data[i * 3 + 1],
                            imag_data[i * 3 + 2],
                        )

                for i, nid in enumerate(real_ids):
                    if nid not in centerline_ids:
                        continue
                    try:
                        node = mesh_data.NodeById(nid)
                    except:
                        continue

                    ux_r = real_data[i * 3]
                    uy_r = real_data[i * 3 + 1]
                    uz_r = real_data[i * 3 + 2]
                    ux_im, uy_im, uz_im = imag_lookup.get(nid, (0.0, 0.0, 0.0))

                    f.write("{0},{1},{2},{3},{4},{5},{6},{7},{8},{9},{10}\n".format(
                        freq_hz, nid,
                        node.X, node.Y, node.Z,
                        ux_r, ux_im,
                        uy_r, uy_im,
                        uz_r, uz_im,
                    ))

        return "OK: centerline displacements exported to {} ({} nodes)".format(csv_path, len(centerline_ids))

    except Exception as e:
        return "ERROR in centerline export: {}".format(e)

analysis = DataModel.AnalysisList[0]
out_dir  = r""" + repr(config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")) + r"""
csv_name = r""" + repr(config.get("centerline_csv_name", "nodal_displacement_centerline.csv")) + r"""
result = export_centerline(analysis, out_dir, csv_name)
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (export centerline displacements):", out)

# =============================================================================
#
# =============================================================================

def export_aggregate_frf(config, mechanical):
    """
    Export per-frequency aggregate statistics across all centerline nodes.
    One row per frequency — much smaller than node-level exports.
    Schema:
      freq_Hz, uy_tip_real, uy_tip_imag, uy_tip_amplitude,
      uy_max_amplitude, uy_mean_amplitude
    Where:
      - tip = centerline node at max Z (beam free end)
      - amplitude = sqrt(real^2 + imag^2)
      - max/mean computed across all centerline nodes at that frequency
    """
    script = r"""
def export_aggregate(analysis, out_dir, csv_name):
    import mech_dpf
    import Ans.DataProcessing as dpf
    import os
    import math

    def get_field_data(dataSource, set_id):
        time_scoping = dpf.Scoping()
        time_scoping.Location = ""
        time_scoping.Ids = [set_id]
        u_op = dpf.operators.result.displacement()
        u_op.inputs.data_sources.Connect(dataSource)
        u_op.inputs.time_scoping.Connect(time_scoping)
        u_fc = u_op.outputs.fields_container.GetData()
        if not u_fc:
            return None, None
        u_field = u_fc[0]
        if not hasattr(u_field, "Scoping") or not hasattr(u_field, "Data"):
            return None, None
        return u_field.Scoping.Ids, u_field.Data

    try:
        mech_dpf.setExtAPI(ExtAPI)
        dataSource = dpf.DataSources(analysis.ResultFileName)
        model_dpf = dpf.Model(dataSource)
        tfs = model_dpf.TimeFreqSupport
        n_sets = tfs.NumberSets
        if n_sets == 0:
            return "ERROR: No frequency sets in result file"

        n_freqs = n_sets
        freqs = [tfs.GetTimeFreq(i) for i in range(n_freqs)]

        mesh_data = analysis.MeshData
        all_nodes = mesh_data.Nodes

        # Identify centerline nodes and tip node
        max_y    = max(n.Y for n in all_nodes)
        min_x    = min(n.X for n in all_nodes)
        max_x    = max(n.X for n in all_nodes)
        center_x = (min_x + max_x) / 2.0
        tol = 0.01  # mm

        centerline_nodes = [
            n for n in all_nodes
            if abs(n.Y - max_y) < tol and abs(n.X - center_x) < tol
        ]

        if not centerline_nodes:
            return "ERROR: No centerline nodes found"

        tip_node = max(centerline_nodes, key=lambda n: n.Z)
        tip_id   = tip_node.Id
        centerline_ids = set(n.Id for n in centerline_nodes)

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        csv_path = os.path.join(out_dir, csv_name)

        with open(csv_path, "w") as f:
            f.write("freq_Hz,uy_tip_real,uy_tip_imag,uy_tip_amplitude,uy_max_amplitude,uy_mean_amplitude\n")

            for freq_idx in range(n_freqs):
                freq_hz  = freqs[freq_idx]
                real_set = freq_idx + 1
                imag_set = None  # imaginary handled by APDL pipeline

                real_ids, real_data = get_field_data(dataSource, real_set)
                imag_ids, imag_data = None, None

                if real_ids is None:
                    continue

                imag_lookup = {}
                if imag_ids is not None and imag_data is not None:
                    for i, nid in enumerate(imag_ids):
                        imag_lookup[nid] = (
                            imag_data[i * 3 + 1],  # uy only
                        )

                uy_tip_real = uy_tip_imag = 0.0
                amplitudes = []

                for i, nid in enumerate(real_ids):
                    if nid not in centerline_ids:
                        continue
                    uy_r  = real_data[i * 3 + 1]
                    uy_im = imag_lookup.get(nid, (0.0,))[0]
                    amp   = math.sqrt(uy_r * uy_r + uy_im * uy_im)
                    amplitudes.append(amp)

                    if nid == tip_id:
                        uy_tip_real = uy_r
                        uy_tip_imag = uy_im

                uy_tip_amp  = math.sqrt(uy_tip_real**2 + uy_tip_imag**2)
                uy_max_amp  = max(amplitudes) if amplitudes else 0.0
                uy_mean_amp = sum(amplitudes) / len(amplitudes) if amplitudes else 0.0

                f.write("{0},{1},{2},{3},{4},{5}\n".format(
                    freq_hz,
                    uy_tip_real, uy_tip_imag, uy_tip_amp,
                    uy_max_amp, uy_mean_amp,
                ))

        return "OK: aggregate FRF exported to {} ({} centerline nodes, {} freqs)".format(
            csv_path, len(centerline_ids), n_freqs)

    except Exception as e:
        return "ERROR in aggregate FRF export: {}".format(e)

analysis = DataModel.AnalysisList[0]
out_dir  = r""" + repr(config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")) + r"""
csv_name = r""" + repr(config.get("aggregate_csv_name", "frf_aggregate.csv")) + r"""
result = export_aggregate(analysis, out_dir, csv_name)
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (export aggregate FRF):", out)

# =============================================================================
#
# =============================================================================

def get_top_face_nodes(mechanical):
    """
    Returns a list of node IDs on the top face (max Y) of the beam.
    """
    script = """
import json

mesh_data = Model.Analyses[0].MeshData
all_nodes = mesh_data.Nodes

max_z = max(n.Z for n in all_nodes)
tolerance = 1e-4

top_nodes = [n.Id for n in all_nodes if abs(n.Z - max_z) < tolerance]

result = json.dumps(top_nodes)
result
"""
    out = mechanical.run_python_script(script)
    import json
    node_ids = json.loads(out)
    print(f"Found {len(node_ids)} nodes on top face (max Z)")
    return node_ids

# =============================================================================
#
# =============================================================================

def select_node_by_id(mechanical, node_id, ns_name):
    """
    Create a named selection from a single node ID.
    """
    script = f"""
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum

model = Model
mesh_data = model.Analyses[0].MeshData
selection_manager = ExtAPI.SelectionManager
sel_info = selection_manager.CreateSelectionInfo(SelectionTypeEnum.MeshNodes)

node = mesh_data.NodeById({node_id})
sel_info.Ids = [{node_id}]

selection_manager.ClearSelection()
selection_manager.NewSelection(sel_info)

ns_container = model.NamedSelections
if ns_container is not None:
    for ns in list(ns_container.Children):
        if ns.Name == "{ns_name}":
            ns.Delete()

ns = model.AddNamedSelection()
ns.Name = "{ns_name}"
ns.Location = sel_info
ns.Generate()

result = "OK: NS '{ns_name}' created for node {node_id} at (" + str(node.X) + ", " + str(node.Y) + ", " + str(node.Z) + ")"
result
"""
    out = mechanical.run_python_script(script)
    print(f"Mechanical says ({ns_name}):", out)

def run_modal_analysis(config, mechanical):
    """
    Run a modal analysis, print the natural frequencies, and save them to
    modal_frequencies.json in the output directory so plot_frf.py can read them.
    """
    min_freq   = float(config.get("modal_min_freq_hz", 1.0))
    max_modes  = int(config.get("modal_max_modes", 10))

    script = f"""
import json
from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory

model = Model

# Add modal analysis — extra 6 modes to skip free-free rigid body modes
modal = model.AddModalAnalysis()
settings = modal.AnalysisSettings
settings.MaximumModesToFind = {max_modes} + 6

modal.Activate()

# Apply fixed support if NS_SUPPORT_FACE exists; skip for free-free
ns = None
if model.NamedSelections is not None:
    for n in model.NamedSelections.Children:
        if n.Name == "NS_SUPPORT_FACE":
            ns = n
            break

if ns is not None:
    fixed = modal.AddFixedSupport()
    fixed.Location = ns

# Add a TotalDeformation result for each mode so frequencies are accessible
for mode in range(1, settings.MaximumModesToFind + 1):
    td = modal.Solution.AddTotalDeformation()
    td.Mode = mode

# Solve
modal.Solution.Solve()

# Extract frequencies from the TotalDeformation results
freq_results = modal.Solution.GetChildren(
    DataModelObjectCategory.TotalDeformation, True
)

freq_values = []
lines = []
for i in range(freq_results.Count):
    freq = freq_results[i].ReportedFrequency.Value
    freq_values.append(freq)
    lines.append("Mode " + str(i+1) + ": " + str(freq) + " Hz")

result = json.dumps({{"frequencies_hz": freq_values, "lines": lines}})
result
"""
    out = mechanical.run_python_script(script)
    data = __import__("json").loads(out)

    print("Mechanical says (modal):")
    for line in data["lines"]:
        print(" ", line)

    import json, os
    min_freq = float(config.get("modal_min_freq_hz", 1.0))
    structural = [f for f in data["frequencies_hz"] if f >= min_freq]
    json_path = os.path.join(config["output_dir"], "modal_frequencies.json")
    with open(json_path, "w") as f:
        json.dump({"frequencies_hz": structural}, f, indent=4)
    print(f"Structural modes saved: {[round(f,2) for f in structural]}")
    print(f"Modal frequencies saved to {json_path}")

# =============================================================================
#
# =============================================================================

def setup_material(config, mechanical):
    """
    Create a custom material from config properties, import it into Mechanical,
    and assign it to all bodies. Uses the Structural Steel XML as a template.
    """
    import os
    import xml.etree.ElementTree as ET

    E       = float(config.get("material_E_Pa",          2.35e9))
    nu      = float(config.get("material_nu",            0.3))
    rho     = float(config.get("material_density_kgm3",  1220.0))
    mat_name = config.get("material_name", "Resin")
    out_dir  = config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")

    K = E / (3.0 * (1.0 - 2.0 * nu))
    G = E / (2.0 * (1.0 + nu))

    lib_path = r"C:\Program Files\ANSYS Inc\v252\Addins\EngineeringData\Samples\General_Materials.xml"
    lib_tree = ET.parse(lib_path)
    lib_root = lib_tree.getroot()
    matml_doc = lib_root.find(".//MatML_Doc")

    ss_material = None
    for mat_elem in matml_doc.findall("Material"):
        name_elem = mat_elem.find("BulkDetails/Name")
        if name_elem is not None and name_elem.text == "Structural Steel":
            ss_material = mat_elem
            break
    if ss_material is None:
        raise RuntimeError("Structural Steel not found in General_Materials.xml")

    ss_material.find("BulkDetails/Name").text = mat_name

    for prop in ss_material.findall("BulkDetails/PropertyData"):
        for pv in prop.findall("ParameterValue"):
            pid  = pv.get("parameter")
            data = pv.find("Data")
            if data is None:
                continue
            if pid == "pa6":   data.text = str(rho)
            elif pid == "pa19": data.text = str(E)
            elif pid == "pa20": data.text = str(nu)
            elif pid == "pa21": data.text = str(K)
            elif pid == "pa22": data.text = str(G)

    new_root = ET.Element("EngineeringData")
    new_root.set("version",     lib_root.get("version",     "19.4.0.79"))
    new_root.set("versiondate", lib_root.get("versiondate", "6/9/2017 12:12:00 PM"))
    ET.SubElement(new_root, "Notes").text = "\n  "
    materials_elem = ET.SubElement(new_root, "Materials")
    new_matml = ET.SubElement(materials_elem, "MatML_Doc")
    new_matml.append(ss_material)
    metadata = matml_doc.find("Metadata")
    if metadata is not None:
        new_matml.append(metadata)

    ET.indent(new_root, space="  ")
    xml_path = os.path.join(out_dir, f"{mat_name}.xml")
    ET.ElementTree(new_root).write(xml_path, encoding="unicode", xml_declaration=True)
    print(f"Material XML written: {mat_name}, E={E:.3e} Pa, nu={nu}, rho={rho} kg/m³")

    script = f"""
from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum

Model.Materials.Import(r"{xml_path}")

# Get geometry entity IDs of all bodies
body_ids = []
for assembly in ExtAPI.DataModel.GeoData.Assemblies:
    for part in assembly.AllParts:
        for body in part.Bodies:
            body_ids.append(body.Id)

# Remove existing assignment if present
for ma in list(Model.Materials.GetChildren(DataModelObjectCategory.MaterialAssignment, True)):
    if ma.Name == "{mat_name}Assignment":
        ma.Delete()

selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = body_ids

ma = Model.Materials.AddMaterialAssignment()
ma.Name = "{mat_name}Assignment"
ma.Location = selection
ma.Material = "{mat_name}"

result = "OK: {mat_name} assigned to body IDs " + str(body_ids)
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (material setup):", out)

# =============================================================================
#
# =============================================================================

def add_remote_force(config, mechanical):
    """
    Select the top face (max centroid Z), create NS_TOP_FACE, and apply a
    remote force at the coordinates specified in config.
    If force_x_m / force_y_m / force_z_m are not set, defaults to the
    centroid of the top face. Corner coordinates are printed so you can
    copy them into config.
    """
    import json

    F_amp     = float(config.get("force_value_N", 1.0))
    direction = config.get("force_direction", "Z").upper()
    fx = F_amp if direction == "X" else 0.0
    fy = F_amp if direction == "Y" else 0.0
    fz = F_amp if direction == "Z" else 0.0

    face_id = config.get("force_face_id", None)

    # Step 1: create NS_TOP_FACE from the geometry entity ID
    face_script = f"""
import json
from Ansys.ACT.Interfaces.Common import SelectionTypeEnum

model = Model

ns_container = model.NamedSelections
if ns_container is not None:
    for ns in list(ns_container.Children):
        if ns.Name == "NS_TOP_FACE":
            ns.Delete()

selection = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
selection.Ids = [{face_id}]

ns = model.AddNamedSelection()
ns.Name = "NS_TOP_FACE"
ns.Location = selection

result = json.dumps({{"ok": True}})
result
"""
    out = mechanical.run_python_script(face_script)
    info = json.loads(out)
    if "error" in info:
        raise RuntimeError(info["error"])
    print("Mechanical says (NS_TOP_FACE): created from face ID", face_id)

    loc_x = float(config["force_x_m"])
    loc_y = float(config["force_y_m"])
    loc_z = float(config["force_z_m"])
    print(f"Applying remote force at: ({loc_x:.4f}, {loc_y:.4f}, {loc_z:.4f}) m")

    # Step 2: apply remote force
    force_script = f"""
model = Model
harmonic = model.Analyses[0]
harmonic.Activate()

ns = None
for child in model.NamedSelections.Children:
    if child.Name == "NS_TOP_FACE":
        ns = child
        break

if ns is None:
    raise RuntimeError("NS_TOP_FACE not found")

rf = harmonic.AddRemoteForce()
rf.Location = ns
rf.DefineBy = LoadDefineBy.Components
rf.XComponent.Output.DiscreteValues = [Quantity("{fx} [N]")]
rf.YComponent.Output.DiscreteValues = [Quantity("{fy} [N]")]
rf.ZComponent.Output.DiscreteValues = [Quantity("{fz} [N]")]
rf.XCoordinate = Quantity("{loc_x} [m]")
rf.YCoordinate = Quantity("{loc_y} [m]")
rf.ZCoordinate = Quantity("{loc_z} [m]")

result = "OK: remote force ({fx}, {fy}, {fz}) N at ({loc_x}, {loc_y}, {loc_z}) m on NS_TOP_FACE"
result
"""
    out = mechanical.run_python_script(force_script)
    print("Mechanical says (remote force):", out)

# =============================================================================
# Damage simulation helpers
# =============================================================================

def apply_damage_apdl(config, mechanical):
    """
    Simulate damage by:
      1. Exporting Structural Steel XML from Mechanical (guaranteed correct format)
      2. Modifying name and Young's modulus in Python, then saving as DamageMaterial.xml
      3. Creating a Named Selection of damage zone elements via GenerationCriteria worksheet
      4. Importing DamageMaterial and assigning it to the Named Selection

    Config keys:
      - damage_location_frac: center of damage as fraction of beam length (e.g. 0.75)
      - damage_zone_frac:     width of damage zone as fraction of beam length (e.g. 0.05)
      - damage_severity:      fraction of E to REMOVE (e.g. 0.25 = 25% reduction)
    """
    import os

    damage_location_frac = float(config.get("damage_location_frac", 0.75))
    damage_zone_frac     = float(config.get("damage_zone_frac", 0.05))
    damage_severity      = float(config.get("damage_severity", 0.25))

    E_original = 200e9
    E_reduced  = E_original * (1.0 - damage_severity)
    nu         = 0.3
    K_reduced  = E_reduced / (3.0 * (1.0 - 2.0 * nu))
    G_reduced  = E_reduced / (2.0 * (1.0 + nu))
    out_dir    = config.get("output_dir", r"C:\Users\coetech\Documents\PyMechanical\Outputs")

    # Use a unique material name per run to avoid "Unable to import" errors
    # when Mechanical already has a DamageMaterial from a previous run.
    mat_label  = f"DamageMaterial_loc{int(damage_location_frac*100):03d}_sev{int(damage_severity*100):03d}"
    xml_path   = os.path.join(out_dir, f"{mat_label}.xml")

    # ── Build DamageMaterial XML by extracting Structural Steel from the
    #    official Ansys material library (guarantees correct import format) ────
    import xml.etree.ElementTree as ET

    lib_path = (
        r"C:\Program Files\ANSYS Inc\v252\Addins\EngineeringData\Samples\General_Materials.xml"
    )
    lib_tree = ET.parse(lib_path)
    lib_root = lib_tree.getroot()
    matml_doc = lib_root.find(".//MatML_Doc")

    # Find the Structural Steel <Material> element
    ss_material = None
    for mat_elem in matml_doc.findall("Material"):
        name_elem = mat_elem.find("BulkDetails/Name")
        if name_elem is not None and name_elem.text == "Structural Steel":
            ss_material = mat_elem
            break
    if ss_material is None:
        raise RuntimeError("Structural Steel not found in General_Materials.xml")

    # Change name to a unique label for this run
    ss_material.find("BulkDetails/Name").text = mat_label

    # Change Young's Modulus (pa19), Bulk Modulus (pa21), Shear Modulus (pa22)
    # in the Isotropic Elasticity PropertyData (the one with "Derive from" qualifier)
    for prop in ss_material.findall("BulkDetails/PropertyData"):
        derive_from = any(
            q.get("name") == "Derive from" for q in prop.findall("Qualifier")
        )
        if derive_from:
            for pv in prop.findall("ParameterValue"):
                pid = pv.get("parameter")
                data = pv.find("Data")
                if pid == "pa19" and data is not None:
                    data.text = str(E_reduced)
                elif pid == "pa21" and data is not None:
                    data.text = str(K_reduced)
                elif pid == "pa22" and data is not None:
                    data.text = str(G_reduced)
            break

    # Build new minimal XML: one material + full Metadata
    new_root = ET.Element("EngineeringData")
    new_root.set("version",     lib_root.get("version",     "19.4.0.79"))
    new_root.set("versiondate", lib_root.get("versiondate", "6/9/2017 12:12:00 PM"))
    ET.SubElement(new_root, "Notes").text = "\n  "
    materials_elem = ET.SubElement(new_root, "Materials")
    new_matml = ET.SubElement(materials_elem, "MatML_Doc")
    new_matml.append(ss_material)
    metadata = matml_doc.find("Metadata")
    if metadata is not None:
        new_matml.append(metadata)

    ET.indent(new_root, space="  ")
    new_tree = ET.ElementTree(new_root)
    new_tree.write(xml_path, encoding="unicode", xml_declaration=True)
    print(f"DamageMaterial XML written: E={E_reduced:.3e} Pa, K={K_reduced:.3e} Pa, G={G_reduced:.3e} Pa")

    # ── Step 3 & 4: Create NS, import material, assign ───────────────────────
    script = f"""
import json
from Ansys.Mechanical.DataModel.Enums import (
    DataModelObjectCategory, GeometryDefineByType,
    SelectionActionType, SelectionCriterionType,
    SelectionOperatorType, SelectionType
)

# Compute damage zone bounds from mesh (coordinates are in mm)
mesh_data = Model.Analyses[0].MeshData
all_nodes = mesh_data.Nodes
z_vals = [n.Z for n in all_nodes]
z_min_beam = min(z_vals)
z_max_beam = max(z_vals)
beam_length = z_max_beam - z_min_beam

damage_center = z_min_beam + {damage_location_frac} * beam_length
half_width    = 0.5 * {damage_zone_frac} * beam_length
z_dmg_min     = damage_center - half_width
z_dmg_max     = damage_center + half_width

# Create Named Selection via GenerationCriteria worksheet
ns_container = Model.NamedSelections
for ns in list(ns_container.Children):
    if ns.Name == "NS_DAMAGE_ELEMENTS":
        ns.Delete()

ns_dmg = ns_container.AddNamedSelection()
ns_dmg.Name = "NS_DAMAGE_ELEMENTS"
ns_dmg.ScopingMethod = GeometryDefineByType.Worksheet

ns_dmg.GenerationCriteria.Add(None)
ns_dmg.GenerationCriteria[0].Action     = SelectionActionType.Add
ns_dmg.GenerationCriteria[0].EntityType = SelectionType.MeshElement
ns_dmg.GenerationCriteria[0].Criterion  = SelectionCriterionType.LocationZ
ns_dmg.GenerationCriteria[0].Operator   = SelectionOperatorType.GreaterThanOrEqual
ns_dmg.GenerationCriteria[0].Value      = Quantity(str(z_dmg_min) + " [mm]")

ns_dmg.GenerationCriteria.Add(None)
ns_dmg.GenerationCriteria[1].Action     = SelectionActionType.Filter
ns_dmg.GenerationCriteria[1].EntityType = SelectionType.MeshElement
ns_dmg.GenerationCriteria[1].Criterion  = SelectionCriterionType.LocationZ
ns_dmg.GenerationCriteria[1].Operator   = SelectionOperatorType.LessThanOrEqual
ns_dmg.GenerationCriteria[1].Value      = Quantity(str(z_dmg_max) + " [mm]")

ns_dmg.Generate()
n_damaged = ns_dmg.Entities.Count if hasattr(ns_dmg, "Entities") else -1

# Each run uses a unique material name so there are no import collisions.
Model.Materials.Import(r"{xml_path}")

# Assign the material to NS_DAMAGE_ELEMENTS
existing_mas = Model.Materials.GetChildren(DataModelObjectCategory.MaterialAssignment, True)
for ma in list(existing_mas):
    if ma.Name == "DamageMaterialAssignment":
        ma.Delete()

dm_name = "{mat_label}"
mat_assign = Model.Materials.AddMaterialAssignment()
mat_assign.Name = "DamageMaterialAssignment"
mat_assign.Location = ns_dmg
mat_assign.Material = dm_name

result = json.dumps({{
    "beam_length_mm":     round(beam_length, 3),
    "damage_center_mm":   round(damage_center, 3),
    "z_dmg_min_mm":       round(z_dmg_min, 3),
    "z_dmg_max_mm":       round(z_dmg_max, 3),
    "n_damaged_elements": n_damaged,
    "E_reduced_Pa":       {E_reduced},
    "material_name":      dm_name
}})
result
"""
    out = mechanical.run_python_script(script)
    import json
    info = json.loads(out)
    print(f"Damage applied: center={info['damage_center_mm']:.1f} mm, "
          f"zone=[{info['z_dmg_min_mm']:.1f}, {info['z_dmg_max_mm']:.1f}] mm, "
          f"material='{info['material_name']}', E_reduced={info['E_reduced_Pa']:.3e} Pa")
    return info


def remove_damage_apdl(mechanical):
    """
    Remove the DamageMaterialAssignment and NS_DAMAGE_ELEMENTS named selection,
    reverting elements to Structural Steel.
    Note: Material.Delete() is not available in PyMechanical 0.11.0, so
    DamageMaterial entries accumulate in the materials list but are harmless
    once the assignment is removed.
    """
    script = """
from Ansys.Mechanical.DataModel.Enums import DataModelObjectCategory
existing_mas = Model.Materials.GetChildren(DataModelObjectCategory.MaterialAssignment, True)
for ma in list(existing_mas):
    if ma.Name == "DamageMaterialAssignment":
        ma.Delete()

for ns in list(Model.NamedSelections.Children):
    if ns.Name == "NS_DAMAGE_ELEMENTS":
        ns.Delete()

result = "OK: damage assignment and named selection removed"
result
"""
    out = mechanical.run_python_script(script)
    print("Mechanical says (remove damage):", out)


def append_to_dataset(config, temp_csv_name, dataset_csv_path, damage_location_mm, damage_severity, label):
    """
    Read a single-run CSV (written by export_complex_displacement) and append
    its rows to the combined dataset CSV, adding label columns.
    If the dataset CSV does not exist yet, write the header first.
    """
    import csv, os

    temp_csv = os.path.join(config["output_dir"], temp_csv_name)

    write_header = not os.path.exists(dataset_csv_path)

    with open(temp_csv, newline="") as src, open(dataset_csv_path, "a", newline="") as dst:
        reader = csv.DictReader(src)
        fieldnames = reader.fieldnames + ["damage_location_mm", "damage_severity", "label"]
        writer = csv.DictWriter(dst, fieldnames=fieldnames)

        if write_header:
            writer.writeheader()

        for row in reader:
            row["damage_location_mm"] = damage_location_mm
            row["damage_severity"]    = damage_severity
            row["label"]              = label
            writer.writerow(row)

    print(f"Appended {label} data (damage_loc={damage_location_mm} mm) to dataset: {dataset_csv_path}")
# -*- coding: utf-8 -*-
"""
=============================================================================
ABAQUS Python Script - Stochastic Mesoscale Laminate Partitioning (2D)
=============================================================================
Article: "Unraveling Transverse Crack Multiplication in Thin-Ply Orthotropic
          Laminates: A Stochastic Finite Element Study"
Journal: Mechanics of Advanced Materials and Structures (2025)

This script uses the SAME proven approach as build_mesoscale_model.py:
  - PartitionFaceBySketch (NOT DatumPlane) for partitioning
  - findAt with 3D tuples for face selection
  - getByBoundingBox for set creation

Compatibility: ABAQUS Python 2.7
  - NO f-strings (uses .format() and % formatting)
  - NO Python 3-only features

Stage: Geometry creation + Partitioning ONLY
       (Materials, mesh, BC, analysis come in next stages)
=============================================================================
"""

from abaqus import *
from abaqusConstants import *
import part
import mesh
import regionToolset
import logging
import random
import os
import sys
import inspect

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from laminate_partitioning_core import (
    build_layup as core_build_layup,
    ply_ranges,
    total_90_thickness,
    ninety_subcell_size,
    partition_x_bounds,
    crack_count_from_density,
    gauge_candidate_boundaries,
    uniform_sample,
    crack_edge_find_points,
    coverage_percent,
)
# ============================================================
# USER INPUTS - ویرایش این مقادیر
# ============================================================

# --- ورودی‌های هندسی (Geometry inputs) - 2D ---
L = 80.0            # طول نمونه [mm] (محور X)
L_gauge = 70.0      # طول gauge [mm] (ناحیه قرارگیری cohesive columns)

# --- ورودی‌های لایه (Ply inputs) ---
t0 = 0.250          # ضخامت هر لایه 0° [mm]
t90 = 0.250         # ضخامت هر لایه 90° [mm]
n90 = 1             # تعداد لایه‌های 90°

# --- نوع لایه‌چینی (Layup type) ---
# 'symmetric'  => [0/90n]s = 0 / 90*n / 90*n / 0
# 'asymmetric' => [0/90/0] = 0 / 90*n90 / 0
layup_type = 'symmetric'

# --- نوع تحلیل 2D (2D analysis type) ---
# 'PLANE_STRAIN'  => CPE4R elements
# 'PLANE_STRESS'  => CPS4R elements
analysis_type = 'PLANE_STRAIN'

# --- پارامترهای Stochastic ---
n_cells_thickness = 5    # تعداد زیرسلول‌های هر لایه 90° در ضخامت
rho = 0.5                # normalized crack saturation rho=N*L/t90 [-]

# --- تنظیمات مدل ---
model_name = 'Laminate_Model'
part_name = 'Laminate'



# ============================================================
# تنظیمات توزیع کسر حجمی (درصدی) و تعداد ست‌ها
# ============================================================
VF_LEVELS_initial = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0]

TARGET_VF = 45.0           # میانگین درصدی الیاف که باید به دست بیاید
NUM_MATERIAL_SETS = 10     # تعداد ست‌های متریال مورد نیاز (تولید بازه‌های مساوی بین 0 تا 90)

# تولید لیست مقادیر Vf به صورت اتوماتیک
VF_LEVELS = []
if NUM_MATERIAL_SETS==7:
    VF_LEVELS = VF_LEVELS_initial
else:
    if NUM_MATERIAL_SETS > 1:
        step_vf = 90.0 / float(NUM_MATERIAL_SETS - 1)
        for i in range(NUM_MATERIAL_SETS):
            VF_LEVELS.append(i * step_vf)
    else:
        VF_LEVELS = [TARGET_VF]
# ============================================================
# COMPUTE LAYUP SEQUENCE
# ============================================================

def build_layup(layup_type, n90, t0, t90):
    """ساخت دنباله لایه‌چینی از پایین به بالا."""
    layup = []
    if layup_type == 'symmetric':
        layup.append((0, t0))
        for i in range(n90):
            layup.append((90, t90))
        for i in range(n90):
            layup.append((90, t90))
        layup.append((0, t0))
    elif layup_type == 'asymmetric':
        layup.append((0, t0))
        for i in range(n90):
            layup.append((90, t90))
        layup.append((0, t0))
    else:
        raise ValueError("layup_type must be 'symmetric' or 'asymmetric'")
    return layup


def print_layup_info(layup, t0, t90, n90, layup_type):
    """نمایش اطلاعات لایه‌چینی."""
    print("")
    print("=" * 70)
    print("LAYUP INFORMATION - 2D Cross-section Analysis")
    print("=" * 70)
    print("Layup type: {}".format(layup_type))
    print("Analysis type: {}".format(analysis_type))
    print("Number of 90 plies (input n90): {}".format(n90))

    if layup_type == 'symmetric':
        n90_total = 2 * n90
        if n90 > 1:
            symbol = "[0/90{}]s".format(n90)
        else:
            symbol = "[0/90]s"
    else:
        n90_total = n90
        if n90 > 1:
            symbol = "[0/90{}/0]".format(n90)
        else:
            symbol = "[0/90/0]"
    print("Layup symbol: {}".format(symbol))
    print("Total 90 plies: {}".format(n90_total))
    print("Total 0 plies: 2")
    print("")
    print("Layup sequence (bottom to top):")
    print("-" * 50)
    for i in range(len(layup)):
        angle = layup[i][0]
        t = layup[i][1]
        if angle == 0:
            direction = " longitudinal (fiber dir.)"
        else:
            direction = " transverse"
        print("  Ply {:2d}: {:3d} deg | t = {:.3f} mm |{}".format(i+1, angle, t, direction))
    print("-" * 50)
    total_t = 0.0
    for item in layup:
        total_t += item[1]
    print("Total thickness: {:.3f} mm".format(total_t))
    print("Specimen length: {:.3f} mm".format(L))
    print("Gauge length: {:.3f} mm".format(L_gauge))
    print("=" * 70)
    print("")


# ============================================================
# CREATE 2D BASE GEOMETRY - ساخت هندسه پایه 2D
# ============================================================

def create_base_geometry_2d(model_name, part_name, L, total_thickness):
    """ساخت پارت پایه به صورت 2D planar (سطح مقطع)."""
    # اگر مدل وجود دارد، حذف کن
    model_keys = mdb.models.keys()
    if model_name in model_keys:
        del mdb.models[model_name]
    mdb.Model(model_name)

    # ساخت اسکچ پروفایل (مستطیل در صفحه X-Y)
    sketch = mdb.models[model_name].ConstrainedSketch(
        name='profile',
        sheetSize=200.0)
    sketch.rectangle(point1=(0.0, 0.0), point2=(L, total_thickness))

    # ساخت پارت 2D planar
    p = mdb.models[model_name].Part(
        name=part_name,
        dimensionality=TWO_D_PLANAR,
        type=DEFORMABLE_BODY)
    p.BaseShell(sketch=sketch)

    print("[OK] Created 2D part '{}': L={} mm x t={:.4f} mm".format(
        part_name, L, total_thickness))
    return p


# ============================================================
# PARTITION USING SKETCH (proven method from build_mesoscale_model.py)
# ============================================================

def partition_with_sketch(p, model, L, total_thickness, layup, n_cells_thickness,
                          L_gauge, rho):
    print("")
    print("--- Partitioning with Sketch method (Square Elements, Entire Model) ---")

    ply_y_boundaries = []
    y_ranges_90 = []
    y_start = 0.0
    
    for i in range(len(layup)):
        angle = layup[i][0]
        t = layup[i][1]
        y_end = y_start + t
        if i < len(layup) - 1:
            ply_y_boundaries.append(y_end)
        if angle == 90:
            y_ranges_90.append((y_start, y_end))
        y_start = y_end

    subcell_y = []
    y_start = 0.0
    t90_sample = 0.0
    for item in layup:
        angle = item[0]
        t = item[1]
        y_end = y_start + t
        if angle == 90:
            t90_sample = t
            dy = t / float(n_cells_thickness)
            for j in range(1, n_cells_thickness):
                subcell_y.append(y_start + j * dy)
        y_start = y_end

    dy = ninety_subcell_size(layup, n_cells_thickness)
    dx = dy

    # Build a regular rectangular grid.  The x pitch equals the 90-ply
    # through-thickness subcell size, so stochastic cells in the target plies
    # are square and independent of crack spacing.
    x_bounds = partition_x_bounds(L, dx)
    cohesive_x = x_bounds[1:-1]

    n_cohesive = len(cohesive_x)

    # مرحله 1: پارتیشن‌های افقی
    print("  Creating horizontal sketch...")
    horiz_sketch = model.ConstrainedSketch(name='partition_horizontal', sheetSize=200.0)
    for y in ply_y_boundaries:
        horiz_sketch.Line(point1=(0.0, y), point2=(L, y))
    for y in subcell_y:
        horiz_sketch.Line(point1=(0.0, y), point2=(L, y))
    p.PartitionFaceBySketch(faces=p.faces, sketch=horiz_sketch)

    # مرحله 2: پارتیشن‌های عمودی (فقط در لایه‌های 90 درجه)
    print("  Creating vertical sketch (restricted to 90 deg plies)...")
    vert_sketch = model.ConstrainedSketch(name='partition_vertical', sheetSize=200.0)
    
    for x in cohesive_x:
        vert_sketch.Line(point1=(x, -total_thickness), point2=(x, 2.0 * total_thickness))
            
    tol = 1e-4
    for y_min, y_max in y_ranges_90:
        faces_to_cut = p.faces.getByBoundingBox(
            xMin=-tol, yMin=y_min-tol, zMin=-tol,
            xMax=L+tol, yMax=y_max+tol, zMax=tol)
        
        if len(faces_to_cut) > 0:
            p.PartitionFaceBySketch(faces=faces_to_cut, sketch=vert_sketch)
            
    print("  [OK] Vertical partitions applied to the entire length successfully")

    return n_cohesive

# ============================================================
# CREATE FACE SETS - استفاده از findAt و getByBoundingBox
# ============================================================

def create_face_sets(p, layup, L, n_cells_thickness):
    print("")
    print("--- Stage 4: Creating face sets (Dynamic Stochastic Vf) ---")

    y_min_0, y_max_0 = 1e10, -1e10
    y_min_90, y_max_90 = 1e10, -1e10

    y_start = 0.0
    for item in layup:
        angle = item[0]
        t = item[1]
        y_end = y_start + t
        if angle == 0:
            y_min_0 = min(y_min_0, y_start)
            y_max_0 = max(y_max_0, y_end)
        else:
            y_min_90 = min(y_min_90, y_start)
            y_max_90 = max(y_max_90, y_end)
        y_start = y_end

    tol = 1e-4

    faces_0 = []

    y_start = 0.0

    for angle, t in layup:

        y_end = y_start + t

        if angle == 0:

            y_mid = 0.5 * (y_start + y_end)

            try:
                f = p.faces.findAt(((L * 0.5, y_mid, 0.0),))

                if f not in faces_0:
                    faces_0.append(f)

            except:
                pass

        y_start = y_end

    if len(faces_0) > 0:
        p.Set(faces=faces_0, name='Ply_0_Set')

    # ============================================================
    # تخصیص استوکستیک متریال‌ها برای کل طول مدل
    # ============================================================
    faces_by_mat = {i: [] for i in range(len(VF_LEVELS))}
    all_cells_data = []

    # محاسبه مرزهای X برای تمام طول مدل.  This must match the partition
    # grid exactly; crack positions are sampled from these existing boundaries.
    dy = ninety_subcell_size(layup, n_cells_thickness)
    dx = dy
    x_bounds = partition_x_bounds(L, dx)

    x_centers = []
    for k in range(len(x_bounds) - 1):
        x_centers.append((x_bounds[k] + x_bounds[k+1]) / 2.0)

    y_start = 0.0
    for ply_idx, item in enumerate(layup):
        angle = item[0]
        t = item[1]
        y_end = y_start + t

        if angle == 90:
            y_mid_ply = y_start + (t / 2.0)
            for j in range(n_cells_thickness):
                y_cell_center = y_start + (j + 0.5) * dy
                normalized_dist = abs(y_cell_center - y_mid_ply) / (t / 2.0)
                deterministic_score = (1.0 - (normalized_dist ** 2)) * 90.0
                
                for x_cell_center in x_centers:
                    noise = random.uniform(-15.0, 15.0)
                    raw_score = deterministic_score + noise
                    
                    all_cells_data.append({
                        'x': x_cell_center,
                        'y': y_cell_center,
                        'score': raw_score
                    })

        y_start = y_end

    # اعمال میانگین کل
    mean_score = sum([cell['score'] for cell in all_cells_data]) / float(len(all_cells_data))
    
    for cell in all_cells_data:
        shifted_vf = cell['score'] - mean_score + TARGET_VF
        shifted_vf = max(0.0, min(90.0, shifted_vf))
        
        best_idx = 0
        min_diff = 1000.0
        for idx, vf_val in enumerate(VF_LEVELS):
            diff = abs(shifted_vf - vf_val)
            if diff < min_diff:
                min_diff = diff
                best_idx = idx
                
        try:
            face_obj = p.faces.findAt(((cell['x'], cell['y'], 0.0),))
            if face_obj is not None:
                faces_by_mat[best_idx].append(face_obj)
        except: pass

    # ایجاد ست‌ها در آباکوس (نام‌ها تا دو رقم اعشار با _ جدا می‌شوند تا دقیق باشند)
    for idx, vf_val in enumerate(VF_LEVELS):
        face_list = faces_by_mat[idx]
        if len(face_list) > 0:
            # مثال خروجی: Set_90deg_Vf_14_50
            str_vf = "{:.2f}".format(vf_val).replace('.', '_')
            set_name = 'Set_90deg_Vf_{}'.format(str_vf)
            p.Set(faces=face_list, name=set_name)
            print("  [OK] Created {} with {} cells".format(set_name, len(face_list)))

    # ============================================================
    # ساخت ست لبه‌های ترک (تنها محدود به ناحیه Gauge)
    # ============================================================
    print("")
    print("  Creating Potential_Crack_Edges set...")

    x_gauge_start = (L - L_gauge) / 2.0
    x_gauge_end = x_gauge_start + L_gauge
    
    # فیلتر کردن خطوط عمودی که فقط داخل محدوده گیج هستند
    ##########
    # -----------------------------------------------
    # Select only the required crack edges
    # -----------------------------------------------

    # تمام مرزهای سلول داخل ناحیه Gauge.  End boundaries of the whole part are
    # excluded because cohesive seams must be internal crack paths.
    candidate_edges = gauge_candidate_boundaries(x_bounds, L, L_gauge, include_ends=False)

    # Crack-density convention: the paper/reference reports a normalized
    # saturation value rho = N*L/t90, so N = rho*t90/L.  This is dimensionless;
    # if rho is instead a physical density [cracks/mm], use N=rho*L.
    t90_total = total_90_thickness(layup)
    n_cracks, n_cracks_raw = crack_count_from_density(
        rho, t90_total, L_gauge, rounding='nearest', minimum=1)

    # بیشتر از تعداد مرزهای موجود نشود
    n_cracks = min(n_cracks, len(candidate_edges))
    crack_x_positions = uniform_sample(candidate_edges, n_cracks)

    crack_edge_points = crack_edge_find_points(crack_x_positions, layup, n_cells_thickness)
    expected_segments = len(crack_x_positions) * len(ply_ranges(layup, 90)) * int(n_cells_thickness)

    print("  Number of cracks: {} (raw={:.6f})".format(n_cracks, n_cracks_raw))
    print("  90 ply total thickness: {:.6f} mm".format(t90_total))
    print("  Crack positions: {}".format([round(x, 6) for x in crack_x_positions]))

    if len(crack_edge_points) > 0:
        try:
            crack_edges = p.edges.findAt(*crack_edge_points)
            p.Set(edges=crack_edges, name='Potential_Crack_Edges')
            selected = len(crack_edges)
            coverage = coverage_percent(selected, expected_segments)
            print("  [OK] Created 'Potential_Crack_Edges' with {} edges".format(selected))
            print("  Crack-set thickness coverage = {:.1f}% ({} / {} segments)".format(
                coverage, selected, expected_segments))
            if selected != expected_segments:
                print("  WARNING: crack edge selection is incomplete; check partition tolerance/geometry")
        except Exception as err:
            print("  ERROR: failed to create Potential_Crack_Edges: {}".format(err))
    else:
        print("  WARNING: no crack edges requested/available in gauge section")

# ============================================================
# PRINT FINAL SUMMARY
# ============================================================

def print_summary(p, layup, n_cohesive, n_cells_thickness):
    """نمایش خلاصه نهایی پارت."""
    print("")
    print("=" * 70)
    print("PARTITIONING COMPLETE - 2D Model")
    print("=" * 70)
    print("Part name: {}".format(p.name))
    print("Total faces:    {:4d}".format(len(p.faces)))
    print("Total edges:    {:4d}".format(len(p.edges)))
    print("Total vertices: {:4d}".format(len(p.vertices)))
    print("Total datums:   {:4d}".format(len(p.datums)))

    n_plies = len(layup)
    n_90_plies = 0
    n_0_plies = 0
    for item in layup:
        if item[0] == 90:
            n_90_plies += 1
        elif item[0] == 0:
            n_0_plies += 1
    print("")
    print("Layup: {} plies ({} x 0 deg + {} x 90 deg)".format(
        n_plies, n_0_plies, n_90_plies))
    print("  90 sub-cells through thickness: {} per ply".format(n_cells_thickness))
    print("  Cohesive columns along length: {}".format(n_cohesive))
    print("  Analysis type: 2D {}".format(analysis_type))

    print("")
    print("=" * 70)
    print("NEXT STEPS - 2D Analysis")
    print("=" * 70)
    print("1. Assign materials (Section assignment):")
    print("   - Ply_0_Set  -> orthotropic elastic (2D)")
    if analysis_type == 'PLANE_STRAIN':
        print("   - Element type: CPE4R (4-node plane strain quadrilateral)")
    else:
        print("   - Element type: CPS4R (4-node plane stress quadrilateral)")
    print("   - Ply_90_Set -> orthotropic elastic with stochastic Vf per face")
    print("2. Insert cohesive elements:")
    print("   - Use 'Insert cohesive seams' tool with Potential_Crack_Edges set")
    print("   - Element type: COH2D4")
    print("3. Mesh the part")
    print("4. Apply boundary conditions and loads")
    print("5. Submit job and post-process")
    print("=" * 70)


# ============================================================
# MAIN SCRIPT
# ============================================================

def main():
    """تابع اصلی - اجرای تمام مراحل پارتیشن‌بندی 2D."""

    print("")
    print("#" * 70)
    print("# ABAQUS SCRIPT: Stochastic Mesoscale Laminate (2D)")
    print("# Article: Transverse Crack Multiplication in Thin-Ply Laminates")
    print("# Analysis: 2D Cross-section (X-Y plane)")
    print("# Python 2.7 Compatible")
    print("#" * 70)

    # مرحله 0: ساخت لایه‌چینی
    layup = core_build_layup(layup_type, n90, t0, t90)
    print_layup_info(layup, t0, t90, n90, layup_type)

    # محاسبه ضخامت کل
    total_thickness = 0.0
    for item in layup:
        total_thickness += item[1]

    # مرحله 1: ساخت هندسه پایه 2D
    print(">>> Stage 0: Creating 2D base geometry...")
    p = create_base_geometry_2d(model_name, part_name, L, total_thickness)

    # دریافت مدل
    model = mdb.models[model_name]

    # مرحله 2: پارتیشن‌بندی با Sketch (روش اثبات‌شده)
    print(">>> Stage 1-3: Partitioning with Sketch method...")
    n_cohesive = partition_with_sketch(p, model, L, total_thickness, layup,
                                        n_cells_thickness, L_gauge, rho)

    # مرحله 3: ساخت face sets
    print(">>> Stage 4: Creating face sets...")
    create_face_sets(p, layup, L, n_cells_thickness)

    # مرحله 4: خلاصه نهایی
    print_summary(p, layup, n_cohesive, n_cells_thickness)

    print("")
    print("[SUCCESS] 2D Script completed successfully!")


# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    main()

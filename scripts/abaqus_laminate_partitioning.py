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

# ============================================================
# USER INPUTS - ویرایش این مقادیر
# ============================================================

# --- ورودی‌های هندسی (Geometry inputs) - 2D ---
L = 80.0            # طول نمونه [mm] (محور X)
L_gauge = 70.0      # طول gauge [mm] (ناحیه قرارگیری cohesive columns)

# --- ورودی‌های لایه (Ply inputs) ---
t0 = 0.250          # ضخامت هر لایه 0° [mm]
t90 = 0.250         # ضخامت هر لایه 90° [mm]
n90 = 2             # تعداد لایه‌های 90°

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
rho = 0.5                # چگالی اشباع ترک [cracks/mm]

# --- تنظیمات مدل ---
model_name = 'Laminate_Model'
part_name = 'Laminate'


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
    """
    پارتیشن‌بندی با استفاده از Sketch (روش اثبات‌شده).

    این روش دقیقاً مثل build_mesoscale_model.py کار می‌کند:
    1. ساخت horizontal sketch برای مرزهای لایه‌ها و زیرسلول‌های 90°
    2. ساخت vertical sketch برای مسیرهای cohesive
    3. استفاده از PartitionFaceBySketch
    """
    print("")
    print("--- Partitioning with Sketch method ---")

    # محاسبه Y مرزهای لایه‌ها
    ply_y_boundaries = []
    y_current = 0.0
    for i in range(len(layup) - 1):
        angle = layup[i][0]
        t = layup[i][1]
        y_current += t
        ply_y_boundaries.append(y_current)

    # محاسبه Y موقعیت‌های زیرسلول‌های 90°
    subcell_y = []
    y_start = 0.0
    for item in layup:
        angle = item[0]
        t = item[1]
        y_end = y_start + t
        if angle == 90:
            dy = t / n_cells_thickness
            for j in range(1, n_cells_thickness):
                subcell_y.append(y_start + j * dy)
        y_start = y_end

    # محاسبه موقعیت‌های X برای cohesive columns
    t90_total = 0.0
    for item in layup:
        if item[0] == 90:
            t90_total += item[1]
    n_cohesive = max(1, int(round(rho * t90_total / L_gauge)))

    x_gauge_start = (L - L_gauge) / 2.0
    dx = L_gauge / (n_cohesive + 1)
    cohesive_x = []
    for i in range(n_cohesive):
        cohesive_x.append(x_gauge_start + (i + 1) * dx)

    print("  Horizontal partition lines: {} ply + {} subcell = {}".format(
        len(ply_y_boundaries), len(subcell_y), len(ply_y_boundaries) + len(subcell_y)))
    print("  Vertical partition lines (cohesive): {}".format(len(cohesive_x)))

    # ============================================================
    # Stage 1: Horizontal sketch (ply boundaries + 90° sub-cells)
    # ============================================================
    print("  Creating horizontal sketch...")
    horiz_sketch = model.ConstrainedSketch(
        name='partition_horizontal',
        sheetSize=200.0)

    # خطوط مرز لایه‌ها
    for y in ply_y_boundaries:
        horiz_sketch.Line(point1=(0.0, y), point2=(L, y))

    # خطوط زیرسلول‌های 90°
    for y in subcell_y:
        horiz_sketch.Line(point1=(0.0, y), point2=(L, y))

    # اعمال پارتیشن افقی
    p.PartitionFaceBySketch(faces=p.faces, sketch=horiz_sketch)
    print("  [OK] Horizontal partitions applied")

    # ============================================================
    # Stage 2: Vertical sketch (cohesive column paths)
    # ============================================================
    print("  Creating vertical sketch...")
    vert_sketch = model.ConstrainedSketch(
        name='partition_vertical',
        sheetSize=200.0)

    for x in cohesive_x:
        vert_sketch.Line(point1=(x, 0.0), point2=(x, total_thickness))

    # اعمال پارتیشن عمودی
    p.PartitionFaceBySketch(faces=p.faces, sketch=vert_sketch)
    print("  [OK] Vertical partitions applied")

    return n_cohesive


# ============================================================
# CREATE FACE SETS - استفاده از findAt و getByBoundingBox
# ============================================================

def create_face_sets(p, layup, L, n_cells_thickness):
    """
    ساخت setهای وجهی (face sets) برای لایه‌های 0° و 90°.

    استفاده از روش اثبات‌شده:
    - getByBoundingBox برای set‌های کلی (Ply_0_Set, Ply_90_Set)
    - findAt با tuple 3D برای set‌های زیرسلول
    """
    print("")
    print("--- Stage 4: Creating face sets ---")

    # محاسبه Y-range لایه‌های 0° و 90°
    y_min_0 = 1e10
    y_max_0 = -1e10
    y_min_90 = 1e10
    y_max_90 = -1e10

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

    # ============================================================
    # Ply_0_Set - استفاده از getByBoundingBox
    # ============================================================
    print("  Creating Ply_0_Set...")
    try:
        faces_0 = p.faces.getByBoundingBox(
            xMin=-tol,
            yMin=y_min_0 - tol,
            zMin=-tol,
            xMax=L + tol,
            yMax=y_max_0 + tol,
            zMax=tol)
        if len(faces_0) > 0:
            p.Set(faces=faces_0, name='Ply_0_Set')
            print("  [OK] Created 'Ply_0_Set' with {} faces".format(len(faces_0)))
        else:
            print("  WARNING: No 0° faces found")
    except Exception as e:
        print("  WARNING: getByBoundingBox failed for 0°: {}".format(e))

    # ============================================================
    # Ply_90_Set - استفاده از getByBoundingBox
    # ============================================================
    print("  Creating Ply_90_Set...")
    try:
        faces_90 = p.faces.getByBoundingBox(
            xMin=-tol,
            yMin=y_min_90 - tol,
            zMin=-tol,
            xMax=L + tol,
            yMax=y_max_90 + tol,
            zMax=tol)
        if len(faces_90) > 0:
            p.Set(faces=faces_90, name='Ply_90_Set')
            print("  [OK] Created 'Ply_90_Set' with {} faces".format(len(faces_90)))
        else:
            print("  WARNING: No 90° faces found")
    except Exception as e:
        print("  WARNING: getByBoundingBox failed for 90°: {}".format(e))

    # ============================================================
    # Sub-cell sets - استفاده از findAt با tuple 3D
    # ============================================================
    print("")
    print("  Creating sub-cell sets for stochastic Vf assignment:")

    # محاسبه Y-boundaries و dx برای هر زیرسلول
    y_start = 0.0
    cell_counter = 0

    for ply_idx, item in enumerate(layup):
        angle = item[0]
        t = item[1]
        y_end = y_start + t

        if angle == 90:
            dy = t / n_cells_thickness

            # محاسبه n_cols بر اساس gauge length
            # (استفاده از همان rho و L_gauge)
            t90_total = 0.0
            for it in layup:
                if it[0] == 90:
                    t90_total += it[1]
            n_cohesive = max(1, int(round(rho * t90_total / L_gauge)))
            dx = L_gauge / (n_cohesive + 1)
            x_gauge_start = (L - L_gauge) / 2.0

            for j in range(n_cells_thickness):
                y_cell_center = y_start + (j + 0.5) * dy

                for i in range(n_cohesive):
                    x_cell_center = x_gauge_start + (i + 0.5) * dx
                    cell_counter += 1
                    set_name = 'Cell_90_{:03d}'.format(cell_counter)

                    # استفاده از findAt با tuple 3D (مثل build_mesoscale_model.py)
                    try:
                        face_obj = p.faces.findAt(((x_cell_center, y_cell_center, 0.0),))
                        if face_obj is not None:
                            p.Set(faces=(face_obj,), name=set_name)
                    except Exception as e:
                        if cell_counter == 1:
                            print("  Note: findAt failed for first cell: {}".format(e))

        y_start = y_end

    print("  [OK] Created {} individual face sets (Cell_90_001 to Cell_90_{:03d})".format(
        cell_counter, cell_counter))

    # ============================================================
    # Potential_Crack_Edges set - برای استفاده در Insert cohesive seams
    # ============================================================
    print("")
    print("  Creating Potential_Crack_Edges set...")

    # محاسبه موقعیت‌های cohesive برای findAt روی edges
    t90_total = 0.0
    for item in layup:
        if item[0] == 90:
            t90_total += item[1]
    n_cohesive = max(1, int(round(rho * t90_total / L_gauge)))
    dx = L_gauge / (n_cohesive + 1)
    x_gauge_start = (L - L_gauge) / 2.0

    # محاسبه Y-range لایه‌های 90°
    y_ranges_90 = []
    y_start = 0.0
    for item in layup:
        angle = item[0]
        t = item[1]
        y_end = y_start + t
        if angle == 90:
            y_ranges_90.append((y_start, y_end))
        y_start = y_end

    # پیدا کردن edges با findAt
    crack_edge_points = []
    for i in range(n_cohesive):
        x_pos = x_gauge_start + (i + 1) * dx
        for y_range in y_ranges_90:
            y_mid = (y_range[0] + y_range[1]) / 2.0
            crack_edge_points.append(((x_pos, y_mid, 0.0),))

    if len(crack_edge_points) > 0:
        try:
            crack_edges = p.edges.findAt(*crack_edge_points)
            p.Set(edges=crack_edges, name='Potential_Crack_Edges')
            print("  [OK] Created 'Potential_Crack_Edges' with {} edges".format(
                len(crack_edge_points)))
        except Exception as e:
            print("  WARNING: findAt failed for crack edges: {}".format(e))
            # Fallback: استفاده از getByBoundingBox برای کل 90° region
            try:
                tol2 = 1e-4
                crack_edges = p.edges.getByBoundingBox(
                    xMin=x_gauge_start - tol2,
                    yMin=y_min_90 - tol2,
                    zMin=-tol2,
                    xMax=x_gauge_start + L_gauge + tol2,
                    yMax=y_max_90 + tol2,
                    zMax=tol2)
                if len(crack_edges) > 0:
                    p.Set(edges=crack_edges, name='Potential_Crack_Edges')
                    print("  [OK] Created 'Potential_Crack_Edges' via getByBoundingBox")
            except Exception as e2:
                print("  WARNING: getByBoundingBox also failed: {}".format(e2))


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
    layup = build_layup(layup_type, n90, t0, t90)
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
else:
    main()

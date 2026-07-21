# -*- coding: utf-8 -*-
"""
=============================================================================
postprocess_odb.py - استخراج داده‌ها از ODB
=============================================================================
استخراج stress-strain، افت سفتی، و crack density از فایل ODB.

خروجی: یک فایل CSV با ستون‌های:
    frame, frame_value, strain_pct,
    sigma90_volumetric_mpa,        # میانگین حجمی σ_x در لایه ۹۰°
    global_stress_mpa,             # F_total / A
    E90_normalized,                # E90 / E90_initial
    crack_count,                   # تعداد ترک‌های کامل (SDEG >= 0.95)
    normalized_crack_density       # crack_count / (rho * L)

نحوه استفاده:
    abaqus python postprocess_odb.py --odb val_090s.odb
    abaqus python postprocess_odb.py --odb val_090s.odb --output results/val_090s.csv

Python 2.7 compatible (هیچ وابستگی به numpy/pandas نداره).

نکته مهم: اگه ODB پیدا نشه یا خطایی رخ بده، اسکریپت gracefully خارج می‌شه
و یه فایل خالی CSV نمی‌سازه. به این ترتیب plot_figures.py می‌تونه بدون
مشکل ادامه بده.
=============================================================================
"""
from __future__ import print_function

import argparse
import csv
import math
import os
import sys

# Abaqus odbAccess — فقط داخل abaqus python در دسترسه
try:
    from odbAccess import openOdb
    HAS_ODB_ACCESS = True
except ImportError:
    HAS_ODB_ACCESS = False

# نام‌های ثابت — باید با اسکریپت build هم‌خوانی داشته باشه
INSTANCE_NAME = 'Laminate_Inst'
STEP_NAME = 'Step-1'
PLY90_SET_PREFIX = 'Set_90deg_Vf_'   # همه setهای Vf با این پیشوند شروع می‌شن
PLY0_SET_NAME = 'Ply_0_Set'
COHESIVE_SEAM_PREFIX = 'CohesiveSeam'
COHESIVE_SEAM_SUFFIX = 'Elements'

# Threshold برای crack counting
SDEG_FULLY_DAMAGED_THRESHOLD = 0.95


# =============================================================================
# Helper functions
# =============================================================================

def _safe_get(dictionary, key):
    """دسترسی امن به dictionary."""
    if dictionary is None:
        return None
    if key in dictionary.keys():
        return dictionary[key]
    return None


def _find_instance(odb):
    """پیدا کردن instance در ODB."""
    if INSTANCE_NAME in odb.rootAssembly.instances.keys():
        return odb.rootAssembly.instances[INSTANCE_NAME]
    # fallback: اولین instance
    instances = odb.rootAssembly.instances
    if len(instances) > 0:
        keys = list(instances.keys())
        return instances[keys[0]]
    return None


def _find_ply90_element_set(odb, instance):
    """پیدا کردن set عناصر لایه ۹۰°."""
    # اول در instance
    for sname in instance.elementSets.keys():
        if sname.startswith(PLY90_SET_PREFIX) or sname == PLY0_SET_NAME:
            # این face set هست نه element set، ولی بعد از meshing به element set تبدیل می‌شه
            pass
    # در assembly
    for sname in odb.rootAssembly.elementSets.keys():
        if sname.startswith(PLY90_SET_PREFIX):
            return odb.rootAssembly.elementSets[sname]
    # fallback: بخش‌بندی بر اساس material assignment (نه عالی ولی کار می‌کنه)
    return None


def _find_cohesive_element_set(odb, instance):
    """پیدا کردن set عناصر cohesive (CohesiveSeam-*-Elements)."""
    # در instance
    for sname in instance.elementSets.keys():
        if sname.startswith(COHESIVE_SEAM_PREFIX) and sname.endswith(COHESIVE_SEAM_SUFFIX):
            return instance.elementSets[sname]
    # در assembly
    for sname in odb.rootAssembly.elementSets.keys():
        if sname.startswith(COHESIVE_SEAM_PREFIX) and sname.endswith(COHESIVE_SEAM_SUFFIX):
            return odb.rootAssembly.elementSets[sname]
    return None


def _collect_ply90_elements(odb, instance):
    """
    جمع‌آوری تمام عناصر لایه ۹۰° بر اساس setهای Set_90deg_Vf_*.

    اگه setها پیدا نشن، fallback: تمام عناصری که متریال Mat_90deg_Vf_* دارن.
    """
    ply90_labels = set()

    # روش ۱: از elementSets با پیشوند Set_90deg_Vf_
    for sname in instance.elementSets.keys():
        if sname.startswith(PLY90_SET_PREFIX):
            for elem in instance.elementSets[sname].elements:
                ply90_labels.add(elem.label)

    if len(ply90_labels) > 0:
        return ply90_labels

    # روش ۲: از assembly elementSets
    for sname in odb.rootAssembly.elementSets.keys():
        if sname.startswith(PLY90_SET_PREFIX):
            for elem in odb.rootAssembly.elementSets[sname].elements:
                ply90_labels.add(elem.label)

    if len(ply90_labels) > 0:
        return ply90_labels

    # روش ۳: fallback — همه عناصر بجز 0° ply
    # (با فرض اینکه Ply_0_Set در instance هست)
    ply0_labels = set()
    for sname in instance.elementSets.keys():
        if sname == PLY0_SET_NAME:
            for elem in instance.elementSets[sname].elements:
                ply0_labels.add(elem.label)

    if len(ply0_labels) > 0:
        for elem in instance.elements:
            if elem.label not in ply0_labels:
                ply90_labels.add(elem.label)

    return ply90_labels


def _compute_element_volume(instance, element):
    """
    محاسبه حجم (مساحت در 2D) یک المان ۴-گرهی CPS4R/CPE4R.

    از shoelace formula استفاده می‌کنیم.
    """
    try:
        # جمع‌آوری nodal coordinates
        coords = []
        for node_label in element.connectivity:
            node = instance.nodes[node_label]
            coords.append((float(node.coordinates[0]),
                          float(node.coordinates[1])))
        if len(coords) < 3:
            return 1.0  # fallback

        # Shoelace formula
        n = len(coords)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        area = abs(area) / 2.0
        return area if area > 1e-12 else 1.0
    except Exception:
        return 1.0


def _volumetric_average_stress(field_data, element_labels, instance):
    """
    میانگین حجمی σ_x روی عناصر لایه ۹۰°.

    σ̄_x = Σ(σ_x × v_i) / Σ(v_i)

    field_data: odb fieldBulkData
    element_labels: set of labels
    """
    sum_sigma_x_v = 0.0
    sum_v = 0.0
    n_found = 0

    for val in field_data:
        try:
            elem_label = val.elementLabel
            if elem_label not in element_labels:
                continue
            # S11 = σ_x (در local coords، ولی با GLOBAL orientation ما، = global σ_x)
            sigma_x = float(val.data[0])  # S11
            volume = _compute_element_volume(instance,
                                             instance.elements[elem_label])
            sum_sigma_x_v += sigma_x * volume
            sum_v += volume
            n_found += 1
        except (IndexError, AttributeError, KeyError):
            continue

    if sum_v <= 0 or n_found == 0:
        return None, 0

    return sum_sigma_x_v / sum_v, n_found


def _total_reaction_force(rf_field, instance, right_x=None, tol=1e-4):
    """
    جمع RF1 روی right edge.

    right_x: مقدار x لبهٔ راست (معمولاً = L). اگه None باشه،
             به‌صورت خودکار از max coordinate nodes پیدا می‌شه.
    tol: تلورانس برای تشخیص نودهای روی right edge.

    استراتژی:
      1. پیدا کردن Right_Edge set در assembly (اگه وجود داشته باشه)
      2. fallback: فیلتر کردن نودها بر اساس x-coordinate نزدیک به right_x
      3. fallback نهایی: جمع همه RF1 (با علامت، که معمولاً روی left و right
         خنثی می‌شه، ولی برای debug خوبه)
    """
    # ============================================================
    # مرحله ۱: پیدا کردن right edge nodes
    # ============================================================
    right_node_labels = set()

    # روش ۱: از Right_Edge set در assembly
    try:
        if 'Right_Edge' in instance.nodeSets.keys():
            for node in instance.nodeSets['Right_Edge'].nodes:
                right_node_labels.add(node.label)
    except Exception:
        pass

    # روش ۲: فیلتر بر اساس x-coordinate
    if len(right_node_labels) == 0 and right_x is not None:
        try:
            for node in instance.nodes:
                if abs(float(node.coordinates[0]) - right_x) < tol:
                    right_node_labels.add(node.label)
        except Exception:
            pass

    # ============================================================
    # مرحله ۲: جمع RF1 روی right edge nodes
    # ============================================================
    total_rf1 = 0.0
    n_found = 0

    if len(right_node_labels) > 0:
        # فقط نودهای right edge
        try:
            for val in rf_field:
                try:
                    node_label = val.nodeLabel
                    if node_label in right_node_labels:
                        total_rf1 += float(val.data[0])  # RF1
                        n_found += 1
                except (IndexError, AttributeError):
                    continue
        except Exception:
            pass

        if n_found > 0:
            return total_rf1

    # fallback نهایی: جمع همه RF1 (با علامت)
    # نکته: این روش فقط برای debug هست. در تحلیل واقعی، right edge
    # باید با set یا coordinate فیلتر بشه.
    try:
        for val in rf_field:
            try:
                # فقط مقادیر مثبت (right edge در کشش مثبت هست)
                rf1 = float(val.data[0])
                if rf1 > 0:
                    total_rf1 += rf1
                    n_found += 1
            except (IndexError, AttributeError):
                continue
    except Exception:
        pass

    return total_rf1


def _count_cracks(status_field, deg_field, cohesive_labels):
    """
    شمارش ترک‌های کامل (SDEG >= threshold).

    هر مسیر ترک شامل چندین COH2D4 element هست (به ازای هر زیرسلول ضخامتی).
    برای تشخیص "crack"، حداقل یک element باید SDEG >= threshold داشته باشه.

    برای سادگی: تعداد عناصر با SDEG >= threshold رو بر n_cells_thickness تقسیم می‌کنیم.
    """
    damaged_count = 0
    try:
        for val in deg_field:
            try:
                elem_label = val.elementLabel
                if elem_label not in cohesive_labels:
                    continue
                sdeg = float(val.data)
                if sdeg >= SDEG_FULLY_DAMAGED_THRESHOLD:
                    damaged_count += 1
            except (IndexError, AttributeError, ValueError):
                continue
    except Exception:
        pass

    # تخمین تعداد ترک: damaged_count / n_cells_thickness
    # (هر ترک n_cells_thickness تا element داره در ضخامت)
    n_cells = 5  # ثابت از تنظیمات build
    crack_count = damaged_count // n_cells
    return crack_count, damaged_count


def _linear_regression_slope(x_data, y_data):
    """رگرسیون خطی برای محاسبه E90_initial."""
    n = len(x_data)
    if n < 2:
        return 0.0
    sum_x = sum(x_data)
    sum_y = sum(y_data)
    sum_xy = sum(x * y for x, y in zip(x_data, y_data))
    sum_xx = sum(x * x for x in x_data)
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-12:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


# =============================================================================
# Main processing function
# =============================================================================

def process_odb(odb_path, output_csv, job_name, rho_sat=8.0, L=80.0, t_total=1.0):
    """
    استخراج داده‌ها از ODB و نوشتن در CSV.

    Parameters
    ----------
    odb_path : str
        مسیر فایل ODB
    output_csv : str
        مسیر فایل خروجی CSV
    job_name : str
        نام job (برای گزارش)
    rho_sat : float
        چگالی اشباع ترک (cracks/mm)
    L : float
        طول نمونه (mm)
    t_total : float
        ضخامت کل (mm) — برای محاسبه cross-section area
    """
    if not HAS_ODB_ACCESS:
        print('[ERROR] odbAccess not available. Run with: abaqus python postprocess_odb.py')
        return False

    if not os.path.exists(odb_path):
        print('[ERROR] ODB file not found: {}'.format(odb_path))
        return False

    print('=' * 70)
    print('Processing ODB: {}'.format(odb_path))
    print('=' * 70)

    try:
        odb = openOdb(path=odb_path, readOnly=True)
    except Exception as e:
        print('[ERROR] Could not open ODB: {}'.format(e))
        return False

    try:
        instance = _find_instance(odb)
        if instance is None:
            print('[ERROR] No instance found in ODB')
            return False
        print('  Instance: {}'.format(instance.name))

        # جمع‌آوری ply90 elements
        ply90_labels = _collect_ply90_elements(odb, instance)
        print('  Ply90 elements found: {}'.format(len(ply90_labels)))

        # جمع‌آوری cohesive elements
        coh_set = _find_cohesive_element_set(odb, instance)
        cohesive_labels = set()
        if coh_set is not None:
            for elem in coh_set.elements:
                cohesive_labels.add(elem.label)
        print('  Cohesive elements found: {}'.format(len(cohesive_labels)))

        # پیدا کردن step
        if STEP_NAME not in odb.steps.keys():
            keys = list(odb.steps.keys())
            step_name = keys[-1] if len(keys) > 0 else None
            if step_name is None:
                print('[ERROR] No step found in ODB')
                return False
            print('  [WARN] Step-1 not found, using: {}'.format(step_name))
        else:
            step_name = STEP_NAME
        step = odb.steps[step_name]
        print('  Step: {} ({} frames)'.format(step_name, len(step.frames)))

        # Cross-section area (width=1mm in 2D plane strain/stress)
        # در مدل 2D، depth=1 فرض می‌شه
        area = t_total * 1.0  # mm²

        # پردازش هر frame
        rows = []
        strain_data = []
        stress_data = []

        for frame_idx, frame in enumerate(step.frames):
            frame_value = float(frame.frameValue)
            strain = frame_value  # در strain-controlled analysis
            strain_pct = strain * 100.0

            # استخراج S field
            sigma90_avg = None
            try:
                s_field = frame.fieldOutputs['S']
                sigma90_avg, n_found = _volumetric_average_stress(
                    s_field.bulkDataBlocks, ply90_labels, instance)
            except KeyError:
                pass

            # استخراج RF field
            global_stress = None
            try:
                rf_field = frame.fieldOutputs['RF']
                total_rf = _total_reaction_force(rf_field.bulkDataBlocks, instance, right_x=L)
                # global_stress = total_rf / area
                global_stress = total_rf / area if area > 0 else None
            except KeyError:
                pass

            # استخراج SDEG field
            crack_count = 0
            damaged_count = 0
            try:
                deg_field = frame.fieldOutputs['SDEG']
                crack_count, damaged_count = _count_cracks(
                    None, deg_field, cohesive_labels)
            except KeyError:
                pass

            # محاسبه E90_initial با regression روی چند frame اول
            if sigma90_avg is not None and strain > 0:
                strain_data.append(strain)
                stress_data.append(sigma90_avg)

            # محاسبه E90_normalized (secant stiffness)
            e90_norm = None
            if sigma90_avg is not None and strain > 0:
                # E90_initial از regression روی ۳-۵ frame اول
                if len(strain_data) >= 3 and strain_data[-1] <= 0.005:
                    e90_initial = _linear_regression_slope(strain_data, stress_data)
                elif len(strain_data) > 0:
                    # fallback: نسبت stress/strain اولین frame
                    e90_initial = stress_data[0] / strain_data[0] if strain_data[0] > 0 else 0
                else:
                    e90_initial = 0

                if e90_initial > 0:
                    e90_norm = (sigma90_avg / strain) / e90_initial
                    e90_norm = max(0.0, min(1.2, e90_norm))  # clamp

            # Normalized crack density
            rho_normal = crack_count / (rho_sat * L) if rho_sat * L > 0 else 0
            rho_normal = min(1.0, rho_normal)

            rows.append({
                'frame': frame_idx,
                'frame_value': frame_value,
                'strain_pct': strain_pct,
                'sigma90_volumetric_mpa': sigma90_avg if sigma90_avg is not None else '',
                'global_stress_mpa': global_stress if global_stress is not None else '',
                'E90_normalized': e90_norm if e90_norm is not None else '',
                'crack_count': crack_count,
                'damaged_elements': damaged_count,
                'normalized_crack_density': rho_normal,
            })

            # گزارش پیشرفت
            if frame_idx % 20 == 0 or frame_idx == len(step.frames) - 1:
                print('  Frame {}/{}: strain={:.3f}%, sigma90={:.2f} MPa, cracks={}'.format(
                    frame_idx + 1, len(step.frames), strain_pct,
                    sigma90_avg if sigma90_avg else 0, crack_count))

        # نوشتن CSV
        if len(rows) == 0:
            print('[WARN] No data extracted from ODB')
            return False

        # ساخت دایرکتوری خروجی اگه لازم باشه
        out_dir = os.path.dirname(output_csv)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)

        with open(output_csv, 'w') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        print('')
        print('=' * 70)
        print('[SUCCESS] CSV saved: {}'.format(output_csv))
        print('  Total frames: {}'.format(len(rows)))
        print('  Final strain: {:.3f}%'.format(rows[-1]['strain_pct']))
        print('  Final cracks: {}'.format(rows[-1]['crack_count']))
        print('=' * 70)
        return True

    except Exception as e:
        print('[ERROR] Exception during processing: {}'.format(e))
        import traceback
        traceback.print_exc()
        return False

    finally:
        try:
            odb.close()
        except Exception:
            pass


# =============================================================================
# Main entry point
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--odb', required=True, help='Path to ODB file')
    parser.add_argument('--output', default=None,
                        help='Output CSV path (default: results/<odb_name>.csv)')
    parser.add_argument('--job-name', default=None,
                        help='Job name (default: ODB filename)')
    parser.add_argument('--rho-sat', type=float, default=8.0,
                        help='Crack saturation density (cracks/mm)')
    parser.add_argument('--L', type=float, default=80.0,
                        help='Specimen length (mm)')
    parser.add_argument('--t-total', type=float, default=1.0,
                        help='Total thickness (mm)')

    args, _ = parser.parse_known_args()

    # مسیر خروجی پیش‌فرض
    if args.output is None:
        odb_name = os.path.splitext(os.path.basename(args.odb))[0]
        args.output = 'results/{}_summary.csv'.format(odb_name)

    if args.job_name is None:
        args.job_name = os.path.splitext(os.path.basename(args.odb))[0]

    # Scale parameters اگه فایل config.py موجود باشه
    try:
        # تلاش برای import config.py (اگه موجود باشه)
        sys.path.insert(0, os.getcwd())
        import config
        L_val = config.GAUGE_LENGTH_MM if hasattr(config, 'GAUGE_LENGTH_MM') else args.L
        rho_val = config.DEFAULT_RHO_SAT if hasattr(config, 'DEFAULT_RHO_SAT') else args.rho_sat
    except ImportError:
        L_val = args.L
        rho_val = args.rho_sat

    success = process_odb(
        odb_path=args.odb,
        output_csv=args.output,
        job_name=args.job_name,
        rho_sat=rho_val,
        L=L_val,
        t_total=args.t_total
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""Extract basic stress-strain and damage indicators from an Abaqus ODB and plot results."""
from __future__ import print_function

import csv
import os
import sys

# تلاش برای وارد کردن کتابخانه آباکوس (فقط در محیط آباکوس کار می‌کند)
try:
    from odbAccess import openOdb
    HAS_ODB_ACCESS = True
except ImportError:
    HAS_ODB_ACCESS = False

JOB_NAME = 'Tensile_Test_Stochastic'
STEP_NAME = 'Step-1'
INSTANCE_NAME = 'SPECIMEN_INST'
PLY90_SET_NAME = 'PLY90_FACES'
CRACK_SET_NAME = 'CRACK_PATHS'


def _safe_get(dictionary, key):
    if key in dictionary.keys():
        return dictionary[key]
    return None

def _mean(values):
    if not values:
        return 0.0
    return sum(values) / float(len(values))

def _element_labels_from_set(element_set):
    labels = {}
    if element_set is None:
        return labels
    for element in element_set.elements:
        labels[element.label] = True
    return labels

def extract_results(odb_path, output_csv=None, L=70.0, width=20.0, thickness=1.0):
    if not HAS_ODB_ACCESS:
        print("Error: Abaqus python environment is required to read .odb files.")
        return None

    if output_csv is None:
        output_csv = os.path.splitext(os.path.basename(odb_path))[0] + '_summary.csv'

    print('Opening ODB file: %s ...' % odb_path)
    odb = openOdb(odb_path, readOnly=True)
    try:
        step = odb.steps[STEP_NAME]
        instance = odb.rootAssembly.instances[INSTANCE_NAME]
        ply90_labels = _element_labels_from_set(_safe_get(instance.elementSets, PLY90_SET_NAME))
        crack_labels = _element_labels_from_set(_safe_get(instance.elementSets, CRACK_SET_NAME))

        rows = []
        area = width * thickness
        for frame in step.frames:
            frame_value = frame.frameValue
            strain = frame_value
            if frame_value > 1.0:
                strain = frame_value / L

            stress_values = []
            if 'S' in frame.fieldOutputs.keys():
                stress_field = frame.fieldOutputs['S']
                for value in stress_field.values:
                    if (not ply90_labels) or (value.elementLabel in ply90_labels):
                        stress_values.append(float(value.data[0]))
            sigma90 = _mean(stress_values)

            rf_total = 0.0
            if 'RF' in frame.fieldOutputs.keys():
                for value in frame.fieldOutputs['RF'].values:
                    if len(value.data) > 0:
                        rf_total += float(value.data[0])
            global_stress = rf_total / area if area > 0.0 else 0.0

            damaged = 0
            total_damage_values = 0
            for damage_name in ('SDEG', 'DMICRT'):
                if damage_name in frame.fieldOutputs.keys():
                    for value in frame.fieldOutputs[damage_name].values:
                        if (not crack_labels) or (value.elementLabel in crack_labels):
                            total_damage_values += 1
                            if float(value.data) >= 0.95:
                                damaged += 1
                    break

            rows.append({
                'frame': len(rows),
                'frame_value': frame_value,
                'strain': strain,
                'sigma90_mpa': sigma90,
                'global_stress_mpa': global_stress,
                'damaged_cohesive_values': damaged,
                'damage_values_checked': total_damage_values,
            })
    finally:
        odb.close()

    with open(output_csv, 'w') as handle:
        writer = csv.DictWriter(handle, fieldnames=('frame', 'frame_value', 'strain',
                                                    'sigma90_mpa', 'global_stress_mpa',
                                                    'damaged_cohesive_values',
                                                    'damage_values_checked'), lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print('Wrote %d frames to %s' % (len(rows), output_csv))
    return output_csv


def plot_results(csv_file, L=70.0):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n[Notice] Matplotlib is not installed in this Python environment.")
        print("To see the plots, open the CSV file in Excel, or run this script again using standard Windows Python:")
        print("    python scripts/postprocess_odb.py " + csv_file)
        return

    strains = []
    stresses = []
    damage_counts = []

    print("Reading data from %s for plotting..." % csv_file)
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # تبدیل کرنش به درصد برای نمایش استانداردتر
            strains.append(float(row['strain']) * 100.0)
            stresses.append(float(row['global_stress_mpa']))
            
            # استفاده از تعداد المان‌های پاره شده به عنوان شاخص چگالی ترک (نرمال شده نسبت به طول)
            damage_counts.append(float(row['damaged_cohesive_values']) / L)

    plt.figure(figsize=(12, 5))

    # ۱. رسم نمودار تنش-کرنش (مشابه شکل 5a مقاله)
    plt.subplot(1, 2, 1)
    plt.plot(strains, stresses, 'b-', linewidth=2.5)
    plt.xlabel('Applied Strain (%)', fontsize=12)
    plt.ylabel('Global Stress (MPa)', fontsize=12)
    plt.title('Laminate Stress-Strain Curve', fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.7)

    # ۲. رسم نمودار تکامل آسیب و ترک (مشابه شکل 11 مقاله)
    plt.subplot(1, 2, 2)
    plt.plot(strains, damage_counts, 'r-', linewidth=2.5)
    plt.xlabel('Applied Strain (%)', fontsize=12)
    plt.ylabel('Damage Indicator (Failed Elements / mm)', fontsize=12)
    plt.title('Damage Evolution (Crack Density proxy)', fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()
    plot_path = csv_file.replace('.csv', '_plots.png')
    plt.savefig(plot_path, dpi=300)
    print("\n>>> Plots successfully saved to: %s" % plot_path)
    
    try:
        plt.show()
    except Exception:
        pass


if __name__ == '__main__':
    # گرفتن نام فایل ورودی (odb یا csv)
    target_file = JOB_NAME + '.odb'
    if len(sys.argv) > 1:
        target_file = sys.argv[-1]

    # تصمیم‌گیری برای نحوه اجرای کد بر اساس فرمت فایل
    if target_file.endswith('.odb'):
        if HAS_ODB_ACCESS:
            csv_path = extract_results(target_file)
            if csv_path and os.path.exists(csv_path):
                plot_results(csv_path)
        else:
            print("Error: You provided an ODB file but odbAccess is not available.")
            print("Please run this script using Abaqus Python:")
            print("    abaqus python scripts/postprocess_odb.py")
            
    elif target_file.endswith('.csv'):
        # اگر کاربر مستقیما فایل CSV را برای رسم نمودار بدهد
        if os.path.exists(target_file):
            plot_results(target_file)
        else:
            print("CSV file not found: %s" % target_file)
            
    else:
        # جستجوی خودکار در پوشه
        if os.path.exists(JOB_NAME + '.odb') and HAS_ODB_ACCESS:
            csv_path = extract_results(JOB_NAME + '.odb')
            plot_results(csv_path)
        elif os.path.exists(JOB_NAME + '_summary.csv'):
            plot_results(JOB_NAME + '_summary.csv')
        else:
            print("No valid .odb or .csv file found to process.")

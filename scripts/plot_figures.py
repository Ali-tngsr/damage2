# -*- coding: utf-8 -*-
"""
=============================================================================
plot_figures.py - رسم نمودارهای مقاله با داده‌های موجود
=============================================================================
این اسکریپت داده‌های CSV از postprocess_odb.py رو می‌خونه و نمودارهای
مقاله رو رسم می‌کنه. مهم‌ترین ویژگی:

  ✅ اگه یکی از فایل‌های CSV موجود نباشه، نمودارها با هر چی که موجوده رسم می‌شن
  ✅ اگه هیچ داده‌ای موجود نباشه، warning چاپ می‌شه ولی error نمی‌ده
  ✅ هر نمودار مستقل هست — اگه یکی fail بشه، بقیه رسم می‌شن

نمودارهای تولیدشده:
  - figure_05_stress_strain.png      : σ vs ε برای ۳ validation layup
  - figure_09_ply_number.png         : σ̄ₓ⁹⁰ و E90/E90° برای ply number study
  - figure_10_ply_thickness.png      : σ̄ₓ⁹⁰ و E90/E90° برای ply thickness study
  - figure_11_crack_density.png      : crack density vs strain

نحوه استفاده:
    python plot_figures.py
    python plot_figures.py --results-dir results --output-dir figures
    python plot_figures.py --figures 5,9,10,11

Python 3 compatible (نیاز به matplotlib داره).
=============================================================================
"""
from __future__ import print_function

import argparse
import csv
import os
import sys

try:
    import matplotlib
    matplotlib.use('Agg')  # non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print('[ERROR] matplotlib not available. Install with: pip install matplotlib')
    sys.exit(1)

# تنظیمات font برای جلوگیری از warning
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False


# =============================================================================
# Job definitions — باید با JOB_PROFILES در اسکریپت build هم‌خوانی داشته باشه
# =============================================================================

# Validation jobs (Fig 5, 6, 8) — [0/90]s, [0/902]s, [0/904]s
VALIDATION_JOBS = {
    'val_090s':  {'label': '[0/90]s',   'color': '#0072B2', 'marker': 'o', 'linestyle': '-'},
    'val_0902s': {'label': '[0/902]s',  'color': '#D55E00', 'marker': 's', 'linestyle': '-'},
    'val_0904s': {'label': '[0/904]s',  'color': '#009E73', 'marker': '^', 'linestyle': '-'},
}

# Ply number study (Fig 9, 11a)
PLY_NUMBER_JOBS = {
    'pn_090n0':   {'label': '[0/90/0]',   'color': '#0072B2', 'marker': 'o', 'linestyle': '--'},
    'val_090s':   {'label': '[0/90]s',    'color': '#D55E00', 'marker': 's', 'linestyle': '-'},
    'val_0902s':  {'label': '[0/902]s',   'color': '#009E73', 'marker': '^', 'linestyle': '-'},
}

# Ply thickness study (Fig 10, 11b)
PLY_THICKNESS_JOBS = {
    'pt_t90_020': {'label': 't90=20 µm',  'color': '#0072B2', 'marker': 'o', 'linestyle': '-'},
    'pt_t90_060': {'label': 't90=60 µm',  'color': '#56B4E9', 'marker': 's', 'linestyle': '-'},
    'pt_t90_100': {'label': 't90=100 µm', 'color': '#D55E00', 'marker': '^', 'linestyle': '-'},
    'pt_t90_140': {'label': 't90=140 µm', 'color': '#CC79A7', 'marker': 'D', 'linestyle': '-'},
}


# =============================================================================
# CSV reader
# =============================================================================

def read_csv(csv_path):
    """خواندن فایل CSV. اگه فایل نبود یا خطا داد، None برمی‌گردونه."""
    if not os.path.exists(csv_path):
        print('[WARN] CSV not found: {}'.format(csv_path))
        return None

    try:
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if len(rows) == 0:
            print('[WARN] CSV is empty: {}'.format(csv_path))
            return None
        print('[OK] Loaded: {} ({} rows)'.format(csv_path, len(rows)))
        return rows
    except Exception as e:
        print('[WARN] Could not read CSV {}: {}'.format(csv_path, e))
        return None


def extract_column(rows, col_name, cast_func=float):
    """استخراج یک ستون از rows. مقادیر نامعتبر رو skip می‌کنه."""
    x_vals = []
    y_vals = []
    for row in rows:
        try:
            val = row.get(col_name, '')
            if val == '' or val is None:
                continue
            y_vals.append(cast_func(val))
            x_vals.append(float(row.get('strain_pct', 0)))
        except (ValueError, TypeError):
            continue
    return x_vals, y_vals


def smooth(data, window=5):
    """میانگین متحرک برای smooth کردن curve."""
    if len(data) < window:
        return data
    result = []
    for i in range(len(data)):
        start = max(0, i - window // 2)
        end = min(len(data), i + window // 2 + 1)
        chunk = data[start:end]
        result.append(sum(chunk) / len(chunk))
    return result


# =============================================================================
# Figure 5: Stress-Strain for validation layups
# =============================================================================

def plot_figure_5(results_dir, output_dir):
    """Fig 5: σ vs ε برای ۳ validation layup."""
    print('')
    print('=' * 60)
    print('Plotting Figure 5: Stress-Strain (validation layups)')
    print('=' * 60)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    n_plotted = 0
    for job_name, style in VALIDATION_JOBS.items():
        csv_path = os.path.join(results_dir, '{}_summary.csv'.format(job_name))
        rows = read_csv(csv_path)
        if rows is None:
            continue

        # (a) Stress-strain
        x1, y1 = extract_column(rows, 'global_stress_mpa')
        if len(x1) > 0:
            ax1.plot(x1, y1, label=style['label'],
                     color=style['color'], marker=style['marker'],
                     linestyle=style['linestyle'], markersize=4,
                     linewidth=1.5, markevery=max(1, len(x1)//15))

        # (b) E90 normalized
        x2, y2 = extract_column(rows, 'E90_normalized')
        if len(x2) > 0:
            y2_smooth = smooth(y2, window=7)
            ax2.plot(x2, y2_smooth, label=style['label'],
                     color=style['color'], marker=style['marker'],
                     linestyle=style['linestyle'], markersize=4,
                     linewidth=1.5, markevery=max(1, len(x2)//15))

        n_plotted += 1

    if n_plotted == 0:
        print('[WARN] No data available for Figure 5. Skipping.')
        plt.close(fig)
        return False

    # تنظیمات ax1
    ax1.set_xlabel('Strain [%]', fontsize=12)
    ax1.set_ylabel('Stress [MPa]', fontsize=12)
    ax1.set_title('(a) Stress-Strain', fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best', fontsize=10)
    ax1.set_xlim(0, 2.5)

    # تنظیمات ax2
    ax2.set_xlabel('Strain [%]', fontsize=12)
    ax2.set_ylabel('E90 / E90° [-]', fontsize=12)
    ax2.set_title('(b) Normalized Stiffness', fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', fontsize=10)
    ax2.set_xlim(0, 2.5)
    ax2.set_ylim(0, 1.1)

    plt.tight_layout()
    out_path = os.path.join(output_dir, 'figure_05_stress_strain.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('[OK] Saved: {}'.format(out_path))
    return True


# =============================================================================
# Figure 9: Ply number study
# =============================================================================

def plot_figure_9(results_dir, output_dir):
    """Fig 9: σ̄ₓ⁹⁰ و E90 برای ply number study."""
    print('')
    print('=' * 60)
    print('Plotting Figure 9: Ply number study')
    print('=' * 60)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    n_plotted = 0
    for job_name, style in PLY_NUMBER_JOBS.items():
        csv_path = os.path.join(results_dir, '{}_summary.csv'.format(job_name))
        rows = read_csv(csv_path)
        if rows is None:
            continue

        # (a) σ̄ₓ⁹⁰
        x1, y1 = extract_column(rows, 'sigma90_volumetric_mpa')
        if len(x1) > 0:
            ax1.plot(x1, y1, label=style['label'],
                     color=style['color'], marker=style['marker'],
                     linestyle=style['linestyle'], markersize=4,
                     linewidth=1.5, markevery=max(1, len(x1)//15))

        # (b) E90 normalized
        x2, y2 = extract_column(rows, 'E90_normalized')
        if len(x2) > 0:
            y2_smooth = smooth(y2, window=7)
            ax2.plot(x2, y2_smooth, label=style['label'],
                     color=style['color'], marker=style['marker'],
                     linestyle=style['linestyle'], markersize=4,
                     linewidth=1.5, markevery=max(1, len(x2)//15))

        n_plotted += 1

    if n_plotted == 0:
        print('[WARN] No data available for Figure 9. Skipping.')
        plt.close(fig)
        return False

    ax1.set_xlabel('Strain [%]', fontsize=12)
    ax1.set_ylabel('σ̄ₓ⁹⁰ [MPa]', fontsize=12)
    ax1.set_title('(a) Volumetric Avg Stress in 90° Ply', fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best', fontsize=10)
    ax1.set_xlim(0, 2.5)

    ax2.set_xlabel('Strain [%]', fontsize=12)
    ax2.set_ylabel('E90 / E90° [-]', fontsize=12)
    ax2.set_title('(b) Normalized Stiffness', fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', fontsize=10)
    ax2.set_xlim(0, 2.5)
    ax2.set_ylim(0, 1.1)

    plt.tight_layout()
    out_path = os.path.join(output_dir, 'figure_09_ply_number.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('[OK] Saved: {}'.format(out_path))
    return True


# =============================================================================
# Figure 10: Ply thickness study
# =============================================================================

def plot_figure_10(results_dir, output_dir):
    """Fig 10: σ̄ₓ⁹⁰ و E90 برای ply thickness study."""
    print('')
    print('=' * 60)
    print('Plotting Figure 10: Ply thickness study')
    print('=' * 60)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    n_plotted = 0
    for job_name, style in PLY_THICKNESS_JOBS.items():
        csv_path = os.path.join(results_dir, '{}_summary.csv'.format(job_name))
        rows = read_csv(csv_path)
        if rows is None:
            continue

        # (a) σ̄ₓ⁹⁰
        x1, y1 = extract_column(rows, 'sigma90_volumetric_mpa')
        if len(x1) > 0:
            ax1.plot(x1, y1, label=style['label'],
                     color=style['color'], marker=style['marker'],
                     linestyle=style['linestyle'], markersize=4,
                     linewidth=1.5, markevery=max(1, len(x1)//15))

        # (b) E90 normalized
        x2, y2 = extract_column(rows, 'E90_normalized')
        if len(x2) > 0:
            y2_smooth = smooth(y2, window=7)
            ax2.plot(x2, y2_smooth, label=style['label'],
                     color=style['color'], marker=style['marker'],
                     linestyle=style['linestyle'], markersize=4,
                     linewidth=1.5, markevery=max(1, len(x2)//15))

        n_plotted += 1

    if n_plotted == 0:
        print('[WARN] No data available for Figure 10. Skipping.')
        plt.close(fig)
        return False

    ax1.set_xlabel('Strain [%]', fontsize=12)
    ax1.set_ylabel('σ̄ₓ⁹⁰ [MPa]', fontsize=12)
    ax1.set_title('(a) Volumetric Avg Stress in 90° Ply', fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best', fontsize=10)
    ax1.set_xlim(0, 2.5)

    ax2.set_xlabel('Strain [%]', fontsize=12)
    ax2.set_ylabel('E90 / E90° [-]', fontsize=12)
    ax2.set_title('(b) Normalized Stiffness', fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', fontsize=10)
    ax2.set_xlim(0, 2.5)
    ax2.set_ylim(0, 1.1)

    plt.tight_layout()
    out_path = os.path.join(output_dir, 'figure_10_ply_thickness.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('[OK] Saved: {}'.format(out_path))
    return True


# =============================================================================
# Figure 11: Crack density
# =============================================================================

def plot_figure_11(results_dir, output_dir):
    """Fig 11: crack density vs strain."""
    print('')
    print('=' * 60)
    print('Plotting Figure 11: Crack density')
    print('=' * 60)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    n_plotted_a = 0
    n_plotted_b = 0

    # (a) Ply number study
    for job_name, style in PLY_NUMBER_JOBS.items():
        csv_path = os.path.join(results_dir, '{}_summary.csv'.format(job_name))
        rows = read_csv(csv_path)
        if rows is None:
            continue
        x, y = extract_column(rows, 'normalized_crack_density')
        if len(x) > 0:
            ax1.plot(x, y, label=style['label'],
                     color=style['color'], marker=style['marker'],
                     linestyle=style['linestyle'], markersize=5,
                     linewidth=1.5, markevery=max(1, len(x)//15))
            n_plotted_a += 1

    # (b) Ply thickness study
    for job_name, style in PLY_THICKNESS_JOBS.items():
        csv_path = os.path.join(results_dir, '{}_summary.csv'.format(job_name))
        rows = read_csv(csv_path)
        if rows is None:
            continue
        x, y = extract_column(rows, 'normalized_crack_density')
        if len(x) > 0:
            ax2.plot(x, y, label=style['label'],
                     color=style['color'], marker=style['marker'],
                     linestyle=style['linestyle'], markersize=5,
                     linewidth=1.5, markevery=max(1, len(x)//15))
            n_plotted_b += 1

    if n_plotted_a == 0 and n_plotted_b == 0:
        print('[WARN] No data available for Figure 11. Skipping.')
        plt.close(fig)
        return False

    ax1.set_xlabel('Strain [%]', fontsize=12)
    ax1.set_ylabel('Normalized Crack Density [-]', fontsize=12)
    ax1.set_title('(a) Ply Number Study', fontsize=13)
    ax1.grid(True, alpha=0.3)
    if n_plotted_a > 0:
        ax1.legend(loc='best', fontsize=10)
    ax1.set_xlim(0, 2.5)
    ax1.set_ylim(0, 1.1)

    ax2.set_xlabel('Strain [%]', fontsize=12)
    ax2.set_ylabel('Normalized Crack Density [-]', fontsize=12)
    ax2.set_title('(b) Ply Thickness Study', fontsize=13)
    ax2.grid(True, alpha=0.3)
    if n_plotted_b > 0:
        ax2.legend(loc='best', fontsize=10)
    ax2.set_xlim(0, 2.5)
    ax2.set_ylim(0, 1.1)

    plt.tight_layout()
    out_path = os.path.join(output_dir, 'figure_11_crack_density.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('[OK] Saved: {}'.format(out_path))
    return True


# =============================================================================
# Summary report
# =============================================================================

def print_summary(results_dir):
    """چاپ خلاصه‌ای از داده‌های موجود."""
    print('')
    print('=' * 60)
    print('DATA AVAILABILITY SUMMARY')
    print('=' * 60)

    all_jobs = list(VALIDATION_JOBS.keys()) + list(PLY_NUMBER_JOBS.keys()) + list(PLY_THICKNESS_JOBS.keys())
    all_jobs = list(set(all_jobs))  # unique

    found = []
    missing = []
    for job in sorted(all_jobs):
        csv_path = os.path.join(results_dir, '{}_summary.csv'.format(job))
        if os.path.exists(csv_path):
            try:
                with open(csv_path, 'r') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                found.append((job, len(rows)))
            except Exception:
                missing.append(job)
        else:
            missing.append(job)

    print('Found CSVs ({}):'.format(len(found)))
    for job, n_rows in found:
        print('  [OK] {} ({} rows)'.format(job, n_rows))

    print('')
    print('Missing CSVs ({}):'.format(len(missing)))
    for job in missing:
        print('  [MISS] {} - run postprocess_odb.py on the .odb file'.format(job))

    print('')
    print('=' * 60)
    return len(found)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results-dir', default='results',
                        help='Directory containing CSV files')
    parser.add_argument('--output-dir', default='figures',
                        help='Output directory for PNG files')
    parser.add_argument('--figures', default='5,9,10,11',
                        help='Comma-separated list of figures to plot')
    args = parser.parse_args()

    # ساخت دایرکتوری خروجی
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # چاپ خلاصه
    n_found = print_summary(args.results_dir)

    if n_found == 0:
        print('[ERROR] No CSV files found in {}'.format(args.results_dir))
        print('[INFO] Run postprocess_odb.py first to extract data from ODB files.')
        sys.exit(1)

    # رسم نمودارها
    figures = [f.strip() for f in args.figures.split(',')]
    plotted = 0
    failed = 0

    for fig_num in figures:
        try:
            if fig_num == '5':
                if plot_figure_5(args.results_dir, args.output_dir):
                    plotted += 1
                else:
                    failed += 1
            elif fig_num == '9':
                if plot_figure_9(args.results_dir, args.output_dir):
                    plotted += 1
                else:
                    failed += 1
            elif fig_num == '10':
                if plot_figure_10(args.results_dir, args.output_dir):
                    plotted += 1
                else:
                    failed += 1
            elif fig_num == '11':
                if plot_figure_11(args.results_dir, args.output_dir):
                    plotted += 1
                else:
                    failed += 1
            else:
                print('[WARN] Unknown figure number: {}'.format(fig_num))
        except Exception as e:
            print('[ERROR] Failed to plot figure {}: {}'.format(fig_num, e))
            failed += 1

    # خلاصه نهایی
    print('')
    print('=' * 60)
    print('PLOTTING SUMMARY')
    print('=' * 60)
    print('  Plotted: {}/{}'.format(plotted, len(figures)))
    print('  Failed:  {}/{}'.format(failed, len(figures)))
    print('  Output directory: {}'.format(args.output_dir))
    if plotted > 0:
        print('')
        print('Generated files:')
        for f in sorted(os.listdir(args.output_dir)):
            if f.endswith('.png'):
                fpath = os.path.join(args.output_dir, f)
                size_kb = os.path.getsize(fpath) / 1024.0
                print('  - {} ({:.1f} KB)'.format(f, size_kb))
    print('=' * 60)


if __name__ == '__main__':
    main()

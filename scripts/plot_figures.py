# -*- coding: utf-8 -*-
"""Plot all paper figures from post-processed CSV files.

Produces publication-quality PNG figures matching the layout of:
  - Fig. 5a  (stress-strain curves, validation sims)
  - Fig. 5b  (stiffness degradation E90/E90° vs strain)
  - Fig. 9a  (avg σ_x⁹⁰ vs time — ply number study)
  - Fig. 9b  (normalized E90 vs strain — ply number study)
  - Fig. 10a (avg σ_x⁹⁰ vs time — ply thickness study)
  - Fig. 10b (normalized E90 vs strain — ply thickness study)
  - Fig. 11a (normalized crack density vs strain — ply number)
  - Fig. 11b (normalized crack density vs strain — ply thickness)

Usage:
    python3 scripts/plot_figures.py                       # all figures
    python3 scripts/plot_figures.py --figures 5,9,10,11   # specific figures only
    python3 scripts/plot_figures.py --no-experiment       # skip experimental overlay

Requires:
    - matplotlib >= 3.0
    - results/<job_name>_summary.csv files (produced by postprocess_odb.py)

Optional:
    - data/experimental_fig5.csv (digitized via WebPlotDigitizer, see
      digitize_experimental.py for instructions)
"""
from __future__ import print_function

import argparse
import csv
import os
import sys

# Try to import matplotlib — fall back gracefully
try:
    import matplotlib
    matplotlib.use('Agg')  # non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print('ERROR: matplotlib is required. Install with: pip install matplotlib')
    sys.exit(1)

# Try numpy (optional — used for smoothing)
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Resolve repo paths
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
RESULTS_DIR = os.path.join(REPO_DIR, 'results')
DATA_DIR = os.path.join(REPO_DIR, 'data')

# Job names for each figure (must match config.JOBS)
FIG5_JOBS = ['val_090s', 'val_0902s', 'val_0904s']
FIG9_JOBS = ['pn_090n0', 'val_090s', 'val_0902s']
FIG9_LABELS = ['[0/90/0]', '[0/90]s', '[0/902]s']
FIG10_JOBS = ['pt_t90_020', 'pt_t90_060', 'pt_t90_100', 'pt_t90_140']
FIG10_LABELS = ['t90=20 µm', 't90=60 µm', 't90=100 µm', 't90=140 µm']
FIG11A_JOBS = FIG9_JOBS
FIG11A_LABELS = FIG9_LABELS
FIG11B_JOBS = ['pt_t90_020', 'pt_t90_140']
FIG11B_LABELS = ['t90=20 µm', 't90=140 µm']

# Publication-quality defaults
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.linewidth': 0.8,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linestyle': '--',
    'grid.linewidth': 0.5,
    'lines.linewidth': 1.8,
    'figure.dpi': 100,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})

# Color palette — distinct, colorblind-safe (Okabe-Ito inspired)
COLORS = {
    'blue':   '#0072B2',
    'orange': '#E69F00',
    'green':  '#009E73',
    'red':    '#D55E00',
    'purple': '#CC79A7',
    'gray':   '#555555',
    'cyan':   '#56B4E9',
    'yellow': '#F0E442',
}

LINESTYLES = ['-', '--', '-.', ':']
MARKERS = ['o', 's', '^', 'v', 'D', 'p']


# =============================================================================
# Data loading helpers
# =============================================================================

def load_summary_csv(job_name):
    """Load results/<job_name>_summary.csv and return as dict of lists."""
    path = os.path.join(RESULTS_DIR, job_name + '_summary.csv')
    if not os.path.exists(path):
        print('  WARNING: %s not found — skipping' % path)
        return None

    cols = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                if k not in cols:
                    cols[k] = []
                try:
                    cols[k].append(float(v))
                except (ValueError, TypeError):
                    cols[k].append(v)
    return cols


def load_experimental_data():
    """Load digitized experimental data from data/experimental_fig5.csv.

    Expected format (CSV):
        strain_pct, stress_090s, stress_0902s, stress_0904s,
                    E90norm_090s, E90norm_0902s, E90norm_0904s
    """
    path = os.path.join(DATA_DIR, 'experimental_fig5.csv')
    if not os.path.exists(path):
        return None
    cols = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                if k not in cols:
                    cols[k] = []
                try:
                    cols[k].append(float(v))
                except (ValueError, TypeError):
                    cols[k].append(v)
    print('  Loaded experimental data: %d points' % len(next(iter(cols.values()))))
    return cols


def smooth(x, y, window=5):
    """Simple moving-average smoothing for noisy E90 curves."""
    if not HAS_NUMPY or len(y) < window:
        return y
    y_arr = np.array(y, dtype=float)
    kernel = np.ones(window) / window
    y_smooth = np.convolve(y_arr, kernel, mode='same')
    return y_smooth.tolist()


# =============================================================================
# Figure 5: Validation — stress-strain + stiffness degradation
# =============================================================================

def plot_figure_5(show_experiment=True):
    """Fig. 5: (a) stress-strain, (b) stiffness degradation — 3 layups."""
    print('\n=== Figure 5: Validation ===')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    colors = [COLORS['blue'], COLORS['orange'], COLORS['green']]
    labels = ['[0/90]s', '[0/902]s', '[0/904]s']

    exp_data = load_experimental_data() if show_experiment else None

    for i, job in enumerate(FIG5_JOBS):
        data = load_summary_csv(job)
        if data is None:
            continue
        strain = [s * 100 for s in data.get('strain', [])]
        global_stress = data.get('global_stress_mpa', [])
        e90_norm = data.get('E90_normalized', [])

        axes[0].plot(strain, global_stress, color=colors[i],
                     linestyle='-', linewidth=2, label=labels[i] + ' (model)')
        axes[1].plot(strain, e90_norm, color=colors[i],
                     linestyle='-', linewidth=2, label=labels[i] + ' (model)')

    # Overlay experimental data if available
    if exp_data:
        exp_strain = exp_data.get('strain_pct', [])
        for i, label in enumerate(['stress_090s', 'stress_0902s', 'stress_0904s']):
            if label in exp_data:
                axes[0].plot(exp_strain, exp_data[label], color=colors[i],
                             linestyle='--', linewidth=1.2, alpha=0.7,
                             label=labels[i].replace('s', 's') + ' (exp)')
        for i, label in enumerate(['E90norm_090s', 'E90norm_0902s', 'E90norm_0904s']):
            if label in exp_data:
                axes[1].plot(exp_strain, exp_data[label], color=colors[i],
                             linestyle='--', linewidth=1.2, alpha=0.7,
                             label=labels[i].replace('s', 's') + ' (exp)')

    # Formatting
    axes[0].set_xlabel('Applied strain εx (%)')
    axes[0].set_ylabel('Stress (MPa)')
    axes[0].set_title('(a) Stress-strain curves')
    axes[0].set_xlim(0, 2.5)
    axes[0].set_ylim(bottom=0)
    axes[0].legend(loc='lower right', fontsize=8, framealpha=0.9)

    axes[1].set_xlabel('Applied strain εx (%)')
    axes[1].set_ylabel('E90 / E90° (normalized)')
    axes[1].set_title('(b) Stiffness degradation in 90° ply')
    axes[1].set_xlim(0, 2.5)
    axes[1].set_ylim(0, 1.1)
    axes[1].legend(loc='lower left', fontsize=8, framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(RESULTS_DIR, 'figure_05.png')
    plt.savefig(out_path)
    plt.close(fig)
    print('  Saved: %s' % out_path)


# =============================================================================
# Figure 9: Ply number study
# =============================================================================

def plot_figure_9():
    """Fig. 9: (a) avg σ_x⁹⁰ vs time, (b) normalized E90 vs strain."""
    print('\n=== Figure 9: Ply number study ===')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    colors = [COLORS['blue'], COLORS['orange'], COLORS['green']]

    for i, job in enumerate(FIG9_JOBS):
        data = load_summary_csv(job)
        if data is None:
            continue
        # Fig. 9a uses "Time" on x-axis (paper plots time, not strain, because
        # all sims share the same strain rate)
        time_vals = data.get('frame_value', [])
        sigma90 = data.get('sigma90_volumetric_mpa', [])
        strain = [s * 100 for s in data.get('strain', [])]
        e90_norm = smooth(None, data.get('E90_normalized', []), window=7)

        axes[0].plot(time_vals, sigma90, color=colors[i],
                     linestyle='-', linewidth=2, label=FIG9_LABELS[i])
        axes[1].plot(strain, e90_norm, color=colors[i],
                     linestyle='-', linewidth=2, label=FIG9_LABELS[i])

    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('σ̄x90 (MPa)')
    axes[0].set_title('(a) Averaged transverse stress in 90° ply')
    axes[0].set_xlim(0, max(time_vals) if time_vals else 1)
    axes[0].set_ylim(bottom=0)
    axes[0].legend(loc='upper right', fontsize=9, framealpha=0.9)

    axes[1].set_xlabel('Applied strain εx (%)')
    axes[1].set_ylabel('E90 / E90°')
    axes[1].set_title('(b) Normalized stiffness degradation')
    axes[1].set_xlim(0, 2.5)
    axes[1].set_ylim(0, 1.1)
    axes[1].legend(loc='lower left', fontsize=9, framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(RESULTS_DIR, 'figure_09.png')
    plt.savefig(out_path)
    plt.close(fig)
    print('  Saved: %s' % out_path)


# =============================================================================
# Figure 10: Ply thickness study
# =============================================================================

def plot_figure_10():
    """Fig. 10: (a) avg σ_x⁹⁰ vs time, (b) normalized E90 vs strain — 4 thicknesses."""
    print('\n=== Figure 10: Ply thickness study ===')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    colors = [COLORS['blue'], COLORS['orange'], COLORS['green'], COLORS['red']]
    linestyles = ['-', '--', '-.', ':']

    for i, job in enumerate(FIG10_JOBS):
        data = load_summary_csv(job)
        if data is None:
            continue
        time_vals = data.get('frame_value', [])
        sigma90 = data.get('sigma90_volumetric_mpa', [])
        strain = [s * 100 for s in data.get('strain', [])]
        e90_norm = smooth(None, data.get('E90_normalized', []), window=7)

        axes[0].plot(time_vals, sigma90, color=colors[i],
                     linestyle=linestyles[i], linewidth=2,
                     label='[0/90/0] ' + FIG10_LABELS[i])
        axes[1].plot(strain, e90_norm, color=colors[i],
                     linestyle=linestyles[i], linewidth=2,
                     label='[0/90/0] ' + FIG10_LABELS[i])

    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('σ̄x90 (MPa)')
    axes[0].set_title('(a) Averaged transverse stress in 90° ply')
    axes[0].set_xlim(0, max(time_vals) if time_vals else 1)
    axes[0].set_ylim(bottom=0)
    axes[0].legend(loc='upper right', fontsize=8, framealpha=0.9)

    axes[1].set_xlabel('Applied strain εx (%)')
    axes[1].set_ylabel('E90 / E90°')
    axes[1].set_title('(b) Normalized stiffness degradation')
    axes[1].set_xlim(0, 2.5)
    axes[1].set_ylim(0, 1.1)
    axes[1].legend(loc='lower left', fontsize=8, framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(RESULTS_DIR, 'figure_10.png')
    plt.savefig(out_path)
    plt.close(fig)
    print('  Saved: %s' % out_path)


# =============================================================================
# Figure 11: Normalized crack density
# =============================================================================

def plot_figure_11():
    """Fig. 11: (a) crack density — ply number, (b) crack density — ply thickness."""
    print('\n=== Figure 11: Crack density ===')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    colors = [COLORS['blue'], COLORS['orange'], COLORS['green'], COLORS['red']]
    linestyles = ['-', '--', '-.', ':']

    # Fig. 11a — ply number
    for i, job in enumerate(FIG11A_JOBS):
        data = load_summary_csv(job)
        if data is None:
            continue
        strain = [s * 100 for s in data.get('strain', [])]
        rho_norm = data.get('normalized_crack_density', [])
        axes[0].plot(strain, rho_norm, color=colors[i],
                     linestyle='-', linewidth=2,
                     label=FIG11A_LABELS[i])

    axes[0].set_xlabel('Strain (%)')
    axes[0].set_ylabel('Normalized crack density')
    axes[0].set_title('(a) Ply number study')
    axes[0].set_xlim(0, 1.0)
    axes[0].set_ylim(0, 1.2)
    axes[0].legend(loc='lower right', fontsize=9, framealpha=0.9)

    # Fig. 11b — ply thickness
    for i, job in enumerate(FIG11B_JOBS):
        data = load_summary_csv(job)
        if data is None:
            continue
        strain = [s * 100 for s in data.get('strain', [])]
        rho_norm = data.get('normalized_crack_density', [])
        axes[1].plot(strain, rho_norm, color=colors[i],
                     linestyle='-', linewidth=2,
                     label='[0/90/0] ' + FIG11B_LABELS[i])

    axes[1].set_xlabel('Strain (%)')
    axes[1].set_ylabel('Normalized crack density')
    axes[1].set_title('(b) Ply thickness study')
    axes[1].set_xlim(0, 1.0)
    axes[1].set_ylim(0, 1.2)
    axes[1].legend(loc='lower right', fontsize=9, framealpha=0.9)

    plt.tight_layout()
    out_path = os.path.join(RESULTS_DIR, 'figure_11.png')
    plt.savefig(out_path)
    plt.close(fig)
    print('  Saved: %s' % out_path)


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Plot all paper figures.')
    parser.add_argument('--figures', default='5,9,10,11',
                        help='Comma-separated figure numbers (default: 5,9,10,11)')
    parser.add_argument('--no-experiment', action='store_true',
                        help='Skip experimental data overlay (Fig. 5 only)')
    args = parser.parse_args()

    requested = set()
    for f in args.figures.split(','):
        f = f.strip()
        if f:
            requested.add(f)

    print('Results directory: %s' % RESULTS_DIR)
    print('Requested figures: %s' % sorted(requested))

    if not os.path.isdir(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

    if '5' in requested:
        plot_figure_5(show_experiment=not args.no_experiment)
    if '9' in requested:
        plot_figure_9()
    if '10' in requested:
        plot_figure_10()
    if '11' in requested:
        plot_figure_11()

    print('\nDone. Figures saved to: %s' % RESULTS_DIR)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""Plot Figure 6 — Crack morphology at 2.5% strain (4-panel layout).

Generates a 2×2 grid showing crack morphology for 4 layups:
  (a) [0/90]s    (b) [0/902]s    (c) [0/904]s    (d) [0/90/0]

Each panel shows:
  - Laminate outline (gray)
  - Cracked cohesive elements (red, SDEG >= 0.95)
  - Partially damaged elements (yellow, 0 < SDEG < 0.95)

Usage:
    python3 scripts/plot_figure_06.py
    python3 scripts/plot_figure_06.py --output results/figure_06.png

Requires: results/<job_name>_cracks.json files (from extract_crack_data.py)

Python 3 (uses matplotlib + numpy).
"""
from __future__ import print_function

import argparse
import json
import os
import sys

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
RESULTS_DIR = os.path.join(REPO_DIR, 'results')


def _load_crack_data(job_name):
    """Load crack data JSON for a job."""
    path = os.path.join(RESULTS_DIR, job_name + '_cracks.json')
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _plot_panel(ax, data, title, show_outline=True):
    """Plot one panel of crack morphology."""
    if not data or not data['frames']:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                transform=ax.transAxes, fontsize=14)
        ax.set_title(title, fontsize=11)
        return

    # Use last frame (2.5% strain)
    frame = data['frames'][-1]
    geom = data['geometry']
    L = geom['L']
    t_total = geom['total_thickness']

    # Draw laminate outline (light gray background)
    ax.fill_between([0, L], 0, t_total, color='#F0F0F0', edgecolor='black',
                    linewidth=1.0)

    # Draw ply boundaries
    t_0 = geom['t_0']
    t_90 = geom['t_90']
    ax.axhline(y=t_0, color='gray', linewidth=0.5, linestyle='-')
    ax.axhline(y=t_0 + t_90, color='gray', linewidth=0.5, linestyle='-')

    # Draw continuum element outlines (sample, for texture)
    if show_outline and frame.get('continuum_outline'):
        from matplotlib.patches import Polygon
        for elem in frame['continuum_outline'][:100]:
            corners = elem.get('corners', [])
            if len(corners) >= 3:
                poly = Polygon(corners, closed=True, fill=False,
                              edgecolor='#CCCCCC', linewidth=0.3)
                ax.add_patch(poly)

    # Draw cracked cohesive elements (red)
    from matplotlib.patches import Polygon
    for elem in frame['cracked_elements']:
        corners = elem.get('corners', [])
        if len(corners) >= 3:
            poly = Polygon(corners, closed=True, fill=True,
                          facecolor='red', edgecolor='darkred',
                          linewidth=0.5, alpha=0.9)
            ax.add_patch(poly)

    # Draw partially damaged elements (yellow)
    for elem in frame['partial_elements']:
        corners = elem.get('corners', [])
        if len(corners) >= 3:
            poly = Polygon(corners, closed=True, fill=True,
                          facecolor='yellow', edgecolor='orange',
                          linewidth=0.3, alpha=0.6)
            ax.add_patch(poly)

    # Set axes
    ax.set_xlim(0, L)
    ax.set_ylim(0, t_total)
    ax.set_xlabel('Length (mm)', fontsize=9)
    ax.set_ylabel('Thickness (mm)', fontsize=9)
    ax.set_title('%s (cracks=%d)' % (title, frame['n_cracked']), fontsize=11)
    ax.set_aspect('auto')
    ax.grid(True, alpha=0.2, linestyle='--')


def plot_figure_6(output_path=None):
    """Plot Figure 6: 4-panel crack morphology."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except ImportError as e:
        print('ERROR: matplotlib not installed: %s' % e)
        sys.exit(1)

    if output_path is None:
        output_path = os.path.join(RESULTS_DIR, 'figure_06.png')
    if not os.path.isdir(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

    # 4 layups for Figure 6
    panels = [
        ('val_090s',  '(a) [0/90]s'),
        ('val_0902s', '(b) [0/902]s'),
        ('val_0904s', '(c) [0/904]s'),
        ('pn_090n0',  '(d) [0/90/0]'),
    ]

    print('=' * 60)
    print('Plotting Figure 6: Crack morphology at 2.5% strain')
    print('=' * 60)

    # Check which data files exist
    missing = []
    for job_name, _ in panels:
        path = os.path.join(RESULTS_DIR, job_name + '_cracks.json')
        if not os.path.exists(path):
            missing.append(job_name)
            print('  WARNING: %s not found' % path)
            print('  Run: abaqus python scripts/extract_crack_data.py --odb abaqus_jobs/%s.odb' % job_name)

    if missing:
        print()
        print('Missing data files for: %s' % ', '.join(missing))
        print('Please run extract_crack_data.py for each job first.')
        print()
        print('Continuing with available data (missing panels will show "No data")...')

    # Create 2x2 grid
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))

    for idx, (job_name, title) in enumerate(panels):
        ax = axes[idx // 2][idx % 2]
        data = _load_crack_data(job_name)
        _plot_panel(ax, data, title)

    # Add legend
    legend_elements = [
        Patch(facecolor='red', edgecolor='darkred', label='Cracked (SDEG >= 0.95)'),
        Patch(facecolor='yellow', edgecolor='orange', alpha=0.6, label='Partial damage (0 < SDEG < 0.95)'),
        Patch(facecolor='#F0F0F0', edgecolor='black', label='Laminate'),
    ]
    fig.legend(handles=legend_elements, loc='lower center',
               ncol=3, fontsize=10, frameon=True,
               bbox_to_anchor=(0.5, -0.02))

    plt.suptitle('Transverse crack morphology at 2.5% strain',
                 fontsize=13, weight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    print()
    print('SUCCESS: Figure 6 saved to %s' % output_path)


def main():
    parser = argparse.ArgumentParser(description='Plot Figure 6: crack morphology')
    parser.add_argument('--output', default=None)
    args = parser.parse_args()
    plot_figure_6(args.output)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""Plot Figure 4 — Stochastic mesoscale FE model overview.

Generates a publication-quality figure showing:
  - The partitioned mesh of [0/904]s laminate
  - Vf (fiber volume fraction) color mapping in the 90° plies
  - 0° plies shown in a uniform color (Vf = 45%)
  - One cohesive crack-path column highlighted in red

This is built with matplotlib (not Abaqus), so it:
  - Works without opening Abaqus/CAE
  - Gives full control over colors and layout
  - Produces clean, publication-ready output

Usage:
    python3 scripts/plot_figure_04.py
    python3 scripts/plot_figure_04.py --job-name val_0904s
    python3 scripts/plot_figure_04.py --output results/figure_04.png

Python 3 (uses matplotlib + numpy).
"""
from __future__ import print_function

import argparse
import os
import sys

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
REPO_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config
from vf_field import generate_vf_field


def _layup_to_plies(job):
    """Convert job layup string to a list of (orientation, thickness_mm) tuples.

    For [0/904]s: [(0, 0.25), (90, 1.02), (0, 0.25)]  (90° block as single region)
    For [0/90/0]: [(0, 0.25), (90, 0.255), (0, 0.25)]
    """
    layup = job['layup']
    t0 = job['t0_mm']
    t90 = job['t90_mm']
    total = job['total_thickness_mm']

    if '0904' in layup or '904' in layup:
        # [0/904]s = 0° / 90°(×4) / 0°
        return [(0, t0), (90, t90), (0, t0)]
    elif '0902' in layup or '902' in layup:
        # [0/902]s = 0° / 90°(×2) / 0°
        return [(0, t0), (90, t90), (0, t0)]
    elif '090' in layup:
        # [0/90]s or [0/90/0]
        return [(0, t0), (90, t90), (0, t0)]
    else:
        return [(0, t0), (90, t90), (0, t0)]


def plot_figure_4(job_name='val_0904s', output_path=None):
    """Plot Figure 4: stochastic mesoscale model overview."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle, Polygon
        from matplotlib.collections import PatchCollection
        import matplotlib.colors as mcolors
        import numpy as np
    except ImportError as e:
        print('ERROR: required packages not installed: %s' % e)
        print('Install with: pip install matplotlib numpy')
        sys.exit(1)

    job = config.get_job_by_name(job_name)
    if job is None:
        print('ERROR: job %s not found in config' % job_name)
        sys.exit(1)

    L = config.GAUGE_LENGTH_MM
    rho_sat = job['rho_sat']
    seed = config.DEFAULT_SEED
    n_cols = max(1, int(round(rho_sat * L)))
    n_rows = config.N_THROUGH_THICKNESS_CELLS

    plies = _layup_to_plies(job)
    total_thickness = sum(p[1] for p in plies)

    # Generate Vf field
    vf_field = generate_vf_field(n_cols, n_rows, seed)

    if output_path is None:
        output_path = os.path.join(REPO_DIR, 'results', 'figure_04.png')
    if not os.path.isdir(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))

    print('=' * 60)
    print('Plotting Figure 4: %s' % job_name)
    print('=' * 60)
    print('  Layup: %s' % job['layup'])
    print('  L = %.1f mm' % L)
    print('  Total thickness = %.3f mm' % total_thickness)
    print('  Vf field: %d rows x %d cols' % (n_rows, n_cols))
    print('  Output: %s' % output_path)
    print('=' * 60)

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 5))

    # Compute ply y-boundaries
    ply_y = [0.0]
    for orientation, thickness in plies:
        ply_y.append(ply_y[-1] + thickness)

    # Color map for Vf (0-90%)
    cmap = plt.cm.RdYlBu_r  # red (high) -> yellow -> blue (low)
    norm = mcolors.Normalize(vmin=0, vmax=90)

    # Plot 0° plies (uniform color — light gray)
    for i, (orientation, thickness) in enumerate(plies):
        if orientation == 0:
            y_bottom = ply_y[i]
            y_top = ply_y[i + 1]
            rect = Rectangle((0, y_bottom), L, thickness,
                             facecolor='#E0E0E0', edgecolor='black',
                             linewidth=0.5, zorder=1)
            ax.add_patch(rect)
            # Label
            ax.text(L / 2, (y_bottom + y_top) / 2, '0° (Vf=45%%)',
                    ha='center', va='center', fontsize=10,
                    color='black', weight='bold')

    # Plot 90° ply with Vf color mapping
    for i, (orientation, thickness) in enumerate(plies):
        if orientation == 90:
            y_bottom_90 = ply_y[i]
            t90 = thickness
            row_thickness = t90 / n_rows
            dx = L / n_cols

            # Plot each cell as a colored rectangle
            for row_idx in range(n_rows):
                for col_idx in range(n_cols):
                    vf = vf_field[row_idx][col_idx]
                    x = col_idx * dx
                    y = y_bottom_90 + row_idx * row_thickness
                    color = cmap(norm(vf))
                    rect = Rectangle((x, y), dx, row_thickness,
                                     facecolor=color, edgecolor='none',
                                     linewidth=0, zorder=2)
                    ax.add_patch(rect)

            # Highlight one cohesive crack path column (red vertical line)
            # Choose a column in the middle for clarity
            highlight_col = n_cols // 2
            x_highlight = highlight_col * dx
            ax.plot([x_highlight, x_highlight],
                    [y_bottom_90, y_bottom_90 + t90],
                    color='red', linewidth=3, zorder=5,
                    label='Cohesive crack path')

            # Label
            ax.text(L / 2, y_bottom_90 + t90 / 2, '90° ply (stochastic Vf)',
                    ha='center', va='center', fontsize=11,
                    color='black', weight='bold',
                    bbox=dict(boxstyle='round,pad=0.3',
                              facecolor='white', alpha=0.7))

    # Add ply boundary lines
    for y in ply_y:
        ax.axhline(y=y, color='black', linewidth=0.8, zorder=3)

    # Set axes
    ax.set_xlim(0, L)
    ax.set_ylim(0, total_thickness)
    ax.set_xlabel('Length (mm)', fontsize=12)
    ax.set_ylabel('Thickness (mm)', fontsize=12)
    ax.set_title('Stochastic mesoscale FE model — %s layup' % job['layup'],
                 fontsize=13, weight='bold')

    # Aspect ratio: distort thickness for visibility
    # Real aspect ratio is too thin (70mm x 2.5mm = 28:1)
    # Use a distorted aspect for clarity
    ax.set_aspect('auto')

    # Add colorbar for Vf
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, orientation='vertical',
                        fraction=0.02, pad=0.02)
    cbar.set_label('Fiber Volume Fraction Vf (%)', fontsize=11)

    # Add legend
    ax.legend(loc='upper right', fontsize=10, framealpha=0.9)

    # Add annotations
    ax.annotate('Resin-rich\n(low Vf, blue)',
                xy=(L * 0.1, y_bottom_90 + 0.05 * n_rows * row_thickness),
                xytext=(L * 0.15, y_bottom_90 - 0.3),
                fontsize=9, color='blue',
                arrowprops=dict(arrowstyle='->', color='blue', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.2',
                          facecolor='lightyellow', alpha=0.8))

    ax.annotate('Fiber-rich\n(high Vf, red)',
                xy=(L * 0.5, y_bottom_90 + 0.5 * t90),
                xytext=(L * 0.6, y_bottom_90 + t90 + 0.2),
                fontsize=9, color='red',
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                bbox=dict(boxstyle='round,pad=0.2',
                          facecolor='lightyellow', alpha=0.8))

    # Grid (light)
    ax.grid(True, alpha=0.2, linestyle='--')

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    print()
    print('SUCCESS: Figure 4 saved to %s' % output_path)
    print()
    print('Description:')
    print('  - Gray regions: 0° plies (Vf = 45%% uniform)')
    print('  - Colored region: 90° ply with stochastic Vf distribution')
    print('  - Blue = low Vf (resin-rich, near interfaces)')
    print('  - Red = high Vf (fiber-rich, centerline)')
    print('  - Red vertical line: example cohesive crack path')


def main():
    parser = argparse.ArgumentParser(description='Plot Figure 4: model overview')
    parser.add_argument('--job-name', default='val_0904s',
                        help='Job name (default: val_0904s — best for showing Vf distribution)')
    parser.add_argument('--output', default=None,
                        help='Output PNG path (default: results/figure_04.png)')
    args = parser.parse_args()

    plot_figure_4(args.job_name, args.output)


if __name__ == '__main__':
    main()

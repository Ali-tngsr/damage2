# -*- coding: utf-8 -*-
"""
Plotting helper for the extracted CSV results.

Python 2.7 compatible.
Run with a normal Python environment:
    python plot_results.py results

It expects:
    global_stress_strain.csv
    normalized_stiffness.csv
    crack_count.csv
"""

from __future__ import division

import os
import sys
import csv

import matplotlib.pyplot as plt


def _read_csv(path):
    rows = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _col(rows, key):
    out = []
    for r in rows:
        try:
            out.append(float(r[key]))
        except Exception:
            out.append(0.0)
    return out


def plot_all(result_dir):
    global_path = os.path.join(result_dir, "global_stress_strain.csv")
    stiff_path = os.path.join(result_dir, "normalized_stiffness.csv")
    crack_path = os.path.join(result_dir, "crack_count.csv")

    if not os.path.isfile(global_path):
        raise IOError("Missing file: %s" % global_path)

    global_rows = _read_csv(global_path)
    strain = _col(global_rows, "strain")
    stress = _col(global_rows, "nominal_stress")

    plt.figure()
    plt.plot(strain, stress, linewidth=2)
    plt.xlabel("Engineering strain")
    plt.ylabel("Nominal stress")
    plt.title("Stress-strain response")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(result_dir, "fig_stress_strain.png"), dpi=300)

    if os.path.isfile(stiff_path):
        stiff_rows = _read_csv(stiff_path)
        s2 = _col(stiff_rows, "strain")
        e_norm = _col(stiff_rows, "E90_over_E0")
        plt.figure()
        plt.plot(s2, e_norm, linewidth=2)
        plt.xlabel("Engineering strain")
        plt.ylabel("E90 / E0")
        plt.title("Normalized stiffness degradation")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, "fig_stiffness.png"), dpi=300)

    if os.path.isfile(crack_path):
        crack_rows = _read_csv(crack_path)
        s3 = _col(crack_rows, "strain")
        cracks = _col(crack_rows, "crack_count")
        plt.figure()
        plt.plot(s3, cracks, linewidth=2)
        plt.xlabel("Engineering strain")
        plt.ylabel("Crack count")
        plt.title("Crack accumulation")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, "fig_crack_count.png"), dpi=300)

    plt.show()


def main():
    result_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    plot_all(result_dir)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Spatial fiber-volume-fraction field generator.

Python 2.7 compatible.
"""

from __future__ import division

import csv
import math
import random

try:
    import numpy as np
except ImportError:
    np = None


def generate_vf_field(n_cols, n_rows=5, seed=None):
    """
    Generate a physically biased Vf map for the 90-degree ply.

    The paper reports a resin-rich boundary region near the interfaces and a
    fiber-rich centerline. This generator encodes that trend without claiming
    exact reconstruction of the micrographs.

    Returns
    -------
    list of list
        Shape (n_rows, n_cols), values in percent.
    """
    rng = random.Random(seed)

    if n_rows != 5:
        raise ValueError("This workflow is written for 5 sub-cells through thickness.")

    field = [[0.0 for _ in range(n_cols)] for _ in range(n_rows)]

    for c in range(n_cols):
        field[0][c] = rng.uniform(0.0, 30.0)
        field[4][c] = rng.uniform(0.0, 30.0)
        field[1][c] = rng.uniform(20.0, 55.0)
        field[3][c] = rng.uniform(20.0, 55.0)
        field[2][c] = rng.uniform(45.0, 75.0)

    return field


def flatten_field(field):
    vals = []
    for row in field:
        vals.extend(row)
    return vals


def field_statistics(field):
    vals = flatten_field(field)
    n = float(len(vals))
    if n == 0:
        return {"min": None, "max": None, "mean": None, "std": None}

    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    return {
        "min": min(vals),
        "max": max(vals),
        "mean": mean,
        "std": math.sqrt(var),
    }


def save_field_csv(field, path):
    with open(path, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["row", "col", "vf_percent"])
        for i, row in enumerate(field):
            for j, vf in enumerate(row):
                writer.writerow([i, j, "%.6f" % vf])


def print_field_summary(field):
    stats = field_statistics(field)
    print("Vf field summary: min={min:.3f}, max={max:.3f}, mean={mean:.3f}, std={std:.3f}".format(**stats))

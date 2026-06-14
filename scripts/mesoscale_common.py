# -*- coding: utf-8 -*-
"""Shared, Abaqus-safe helpers for the mesoscale laminate scripts.

The Abaqus releases commonly used with this project run an old Python 2.7
interpreter.  Keep this module free of f-strings, dataclasses, pathlib,
pandas, and other modern-only dependencies.  The functions below are plain
Python so they can also be unit-tested with a normal Python interpreter.
"""
from __future__ import print_function

import csv
import os
import random

# Table 1 from the replication README.  Moduli are stored in GPa and converted
# to MPa by get_properties(..., units='MPa') because the model uses mm-MPa.
TABLE1_ROWS = (
    {'Vf': 0.0, 'E11': 1.70, 'nu12': 0.40, 'E22': 1.70, 'nu23': 0.40, 'YT': 20.0, 'G12': 0.61, 'G23': 0.61},
    {'Vf': 15.0, 'E11': 12.20, 'nu12': 0.64, 'E22': 2.48, 'nu23': 0.34, 'YT': 19.0, 'G12': 0.81, 'G23': 0.78},
    {'Vf': 30.0, 'E11': 22.73, 'nu12': 0.59, 'E22': 3.25, 'nu23': 0.34, 'YT': 18.0, 'G12': 1.09, 'G23': 1.02},
    {'Vf': 45.0, 'E11': 33.29, 'nu12': 0.54, 'E22': 4.45, 'nu23': 0.32, 'YT': 17.0, 'G12': 1.51, 'G23': 1.43},
    {'Vf': 60.0, 'E11': 43.80, 'nu12': 0.49, 'E22': 6.59, 'nu23': 0.28, 'YT': 16.0, 'G12': 2.21, 'G23': 2.21},
    {'Vf': 75.0, 'E11': 54.31, 'nu12': 0.45, 'E22': 10.89, 'nu23': 0.23, 'YT': 15.0, 'G12': 3.68, 'G23': 3.90},
    {'Vf': 90.0, 'E11': 64.85, 'nu12': 0.40, 'E22': 17.98, 'nu23': 0.16, 'YT': 14.0, 'G12': 6.15, 'G23': 6.80},
)
PROPERTY_NAMES = ('E11', 'nu12', 'E22', 'nu23', 'YT', 'G12', 'G23')
MODULUS_NAMES = ('E11', 'E22', 'G12', 'G23')


def _linear_interp(x_value, x_data, y_data):
    """Piecewise linear interpolation with end-value clamping."""
    x_value = float(x_value)
    if x_value <= x_data[0]:
        return float(y_data[0])
    if x_value >= x_data[-1]:
        return float(y_data[-1])

    for idx in range(1, len(x_data)):
        x0 = x_data[idx - 1]
        x1 = x_data[idx]
        if x_value <= x1:
            y0 = y_data[idx - 1]
            y1 = y_data[idx]
            ratio = (x_value - x0) / (x1 - x0)
            return float(y0 + ratio * (y1 - y0))
    return float(y_data[-1])


def get_properties(vf_target, units='MPa'):
    """Return interpolated material properties for a fiber volume fraction.

    Parameters
    ----------
    vf_target : float
        Fiber volume fraction in percent, clamped to the Table 1 range.
    units : str
        'GPa' returns Table 1 units.  'MPa' converts elastic moduli to MPa
        while keeping strengths in MPa, matching an Abaqus mm-MPa model.
    """
    vf_data = [row['Vf'] for row in TABLE1_ROWS]
    props = {}
    for name in PROPERTY_NAMES:
        data = [row[name] for row in TABLE1_ROWS]
        value = _linear_interp(vf_target, vf_data, data)
        if units == 'MPa' and name in MODULUS_NAMES:
            value *= 1000.0
        props[name] = value
    props['Vf'] = max(vf_data[0], min(float(vf_target), vf_data[-1]))
    return props


def assign_vf_field(n_cols, n_rows=5, seed=None):
    """Create the stochastic 90-degree-ply Vf field as nested Python lists."""
    if n_rows != 5:
        raise ValueError('The published mesoscale rule expects exactly 5 rows')
    rng = random.Random(seed)
    vf_field = []
    ranges = ((0.0, 30.0), (20.0, 55.0), (45.0, 75.0), (20.0, 55.0), (0.0, 30.0))
    for low, high in ranges:
        row = []
        for _idx in range(int(n_cols)):
            row.append(rng.uniform(low, high))
        vf_field.append(row)
    return vf_field


def rounded_vf(vf_value, decimals=1):
    """Round Vf for material caching without changing the spatial field itself."""
    return round(float(vf_value), int(decimals))


def safe_name(prefix, value):
    """Create an Abaqus-safe object name from a prefix and numeric value."""
    text = ('%s_%0.3f' % (prefix, float(value))).replace('-', 'm')
    return text.replace('.', '_')


def read_table_csv(csv_path):
    """Read a Table-1-style CSV for external checks without pandas."""
    rows = []
    with open(csv_path, 'r') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            converted = {}
            for key, value in row.items():
                converted[key] = float(value)
            rows.append(converted)
    return rows


def default_table_path():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data', 'table1_properties.csv'))

# -*- coding: utf-8 -*-
"""
Table 1 data and interpolation utilities for the thin-ply GF/PP study.

Python 2.7 compatible.
"""

from __future__ import division

try:
    import numpy as np
except ImportError:
    np = None

VF_DATA = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0]
TABLE_1 = {
    "E11": [1.70, 12.20, 22.73, 33.29, 43.80, 54.31, 64.85],
    "nu12": [0.40, 0.64, 0.59, 0.54, 0.49, 0.45, 0.40],
    "E22": [1.70, 2.48, 3.25, 4.45, 6.59, 10.89, 17.98],
    "nu23": [0.40, 0.34, 0.34, 0.32, 0.28, 0.23, 0.16],
    "YT": [20.0, 19.0, 18.0, 17.0, 16.0, 15.0, 14.0],
    "G12": [0.61, 0.81, 1.09, 1.51, 2.21, 3.68, 6.15],
    "G23": [0.61, 0.78, 1.02, 1.43, 2.21, 3.90, 6.80],
}

PROPERTY_ORDER = ["E11", "nu12", "E22", "nu23", "YT", "G12", "G23"]


def _interp1d_python(x_values, y_values, x):
    """Linear interpolation without NumPy."""
    if x <= x_values[0]:
        return float(y_values[0])
    if x >= x_values[-1]:
        return float(y_values[-1])

    for i in range(len(x_values) - 1):
        x0 = x_values[i]
        x1 = x_values[i + 1]
        if x0 <= x <= x1:
            y0 = y_values[i]
            y1 = y_values[i + 1]
            if x1 == x0:
                return float(y0)
            ratio = (x - x0) / float(x1 - x0)
            return float(y0 + ratio * (y1 - y0))

    return float(y_values[-1])


def interpolate_properties(vf):
    """
    Return a property dictionary for a target fiber volume fraction vf (%).

    Parameters
    ----------
    vf : float
        Fiber volume fraction in percent.

    Returns
    -------
    dict
        Keys: E11, nu12, E22, nu23, YT, G12, G23
    """
    props = {}
    if np is not None:
        vf_data = np.array(VF_DATA, dtype=float)
        for key in PROPERTY_ORDER:
            props[key] = float(np.interp(vf, vf_data, np.array(TABLE_1[key], dtype=float)))
    else:
        for key in PROPERTY_ORDER:
            props[key] = _interp1d_python(VF_DATA, TABLE_1[key], vf)
    return props


def to_engineering_constants_table(vf):
    """
    Abaqus engineering constants table.
    Returns values in MPa and dimensionless Poisson ratios.
    """
    p = interpolate_properties(vf)
    return (
        p["E11"] * 1000.0,
        p["E22"] * 1000.0,
        p["E22"] * 1000.0,
        p["nu12"],
        p["nu23"],
        p["nu12"],
        p["G12"] * 1000.0,
        p["G23"] * 1000.0,
        p["G12"] * 1000.0,
    )


def as_csv_rows():
    rows = []
    for vf in VF_DATA:
        p = interpolate_properties(vf)
        rows.append([
            vf, p["E11"], p["nu12"], p["E22"], p["nu23"], p["YT"], p["G12"], p["G23"]
        ])
    return rows

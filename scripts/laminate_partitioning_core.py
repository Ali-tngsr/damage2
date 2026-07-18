# -*- coding: utf-8 -*-
"""Pure-Python laminate partitioning helpers.

This module intentionally has no Abaqus imports so the crack-density,
partition-grid, and validation logic can be tested with CPython and reused by
Abaqus scripts.  Geometry units are mm throughout.
"""
from __future__ import print_function


EPS = 1.0e-9


def build_layup(layup_type, n90, t0, t90):
    """Return the bottom-to-top layup as ``[(angle_deg, thickness_mm), ...]``."""
    if n90 < 1:
        raise ValueError('n90 must be >= 1')
    if t0 <= 0.0 or t90 <= 0.0:
        raise ValueError('ply thicknesses must be positive')

    layup = [(0, float(t0))]
    if layup_type == 'symmetric':
        for _idx in range(int(n90)):
            layup.append((90, float(t90)))
        for _idx in range(int(n90)):
            layup.append((90, float(t90)))
    elif layup_type == 'asymmetric':
        for _idx in range(int(n90)):
            layup.append((90, float(t90)))
    else:
        raise ValueError("layup_type must be 'symmetric' or 'asymmetric'")
    layup.append((0, float(t0)))
    return layup


def ply_ranges(layup, angle_filter=None):
    """Return ``(ply_index, angle, y_min, y_max)`` ranges from bottom to top."""
    ranges = []
    y_start = 0.0
    for idx, item in enumerate(layup):
        angle = item[0]
        thickness = float(item[1])
        y_end = y_start + thickness
        if angle_filter is None or angle == angle_filter:
            ranges.append((idx, angle, y_start, y_end))
        y_start = y_end
    return ranges


def total_thickness(layup):
    total = 0.0
    for _angle, thickness in layup:
        total += float(thickness)
    return total


def total_90_thickness(layup):
    total = 0.0
    for angle, thickness in layup:
        if angle == 90:
            total += float(thickness)
    return total


def ninety_subcell_size(layup, n_cells_thickness):
    """Return through-thickness subcell size for 90 plies.

    All 90 plies must use a common thickness in this script.  That keeps the
    x-grid rectangular and makes every stochastic cell aspect ratio 1:1.
    """
    if n_cells_thickness < 1:
        raise ValueError('n_cells_thickness must be >= 1')
    sizes = []
    for angle, thickness in layup:
        if angle == 90:
            sizes.append(float(thickness) / float(n_cells_thickness))
    if not sizes:
        raise ValueError('layup must contain at least one 90-degree ply')
    first = sizes[0]
    for size in sizes[1:]:
        if abs(size - first) > max(1.0e-8, 1.0e-6 * first):
            raise ValueError('all 90 plies must have identical subcell size')
    return first


def partition_x_bounds(length, cell_size):
    """Return monotonically increasing x partition bounds including 0 and L."""
    if length <= 0.0 or cell_size <= 0.0:
        raise ValueError('length and cell_size must be positive')
    bounds = [0.0]
    x_pos = cell_size
    while x_pos < length - 1.0e-8:
        bounds.append(x_pos)
        x_pos += cell_size
    bounds.append(float(length))
    return bounds


def crack_count_from_density(rho_sat, t90_total, gauge_length, rounding='nearest', minimum=0):
    """Convert normalized crack-density saturation to an integer crack count.

    The literature convention used by this project is normally
    ``rho = N * L / t90`` (dimensionless normalized crack density).  Therefore
    ``N = rho * t90 / L``.  If a user supplies a physical density in cracks/mm,
    the correct conversion would instead be ``N = rho * L``; do not mix the two.
    """
    if rho_sat < 0.0 or t90_total <= 0.0 or gauge_length <= 0.0:
        raise ValueError('rho_sat must be non-negative; t90_total and gauge_length positive')
    raw_count = float(rho_sat) * float(t90_total) / float(gauge_length)
    if rounding == 'floor':
        count = int(raw_count)
    elif rounding == 'ceil':
        import math
        count = int(math.ceil(raw_count - EPS))
    elif rounding == 'nearest':
        count = int(round(raw_count))
    else:
        raise ValueError("rounding must be 'nearest', 'floor', or 'ceil'")
    if raw_count > 0.0 and minimum > 0:
        count = max(int(minimum), count)
    return count, raw_count


def crack_count_from_physical_density(cracks_per_mm, gauge_length, rounding='nearest', minimum=0):
    """Convert a physical lineal density [cracks/mm] to crack count N = rho*L."""
    if cracks_per_mm < 0.0 or gauge_length <= 0.0:
        raise ValueError('cracks_per_mm must be non-negative and gauge_length positive')
    raw_count = float(cracks_per_mm) * float(gauge_length)
    if rounding == 'floor':
        count = int(raw_count)
    elif rounding == 'ceil':
        import math
        count = int(math.ceil(raw_count - EPS))
    elif rounding == 'nearest':
        count = int(round(raw_count))
    else:
        raise ValueError("rounding must be 'nearest', 'floor', or 'ceil'")
    if raw_count > 0.0 and minimum > 0:
        count = max(int(minimum), count)
    return count, raw_count


def gauge_candidate_boundaries(x_bounds, length, gauge_length, include_ends=False):
    """Return partition boundaries inside the centered gauge section."""
    if gauge_length <= 0.0 or gauge_length > length + EPS:
        raise ValueError('gauge_length must be in (0, length]')
    x_start = 0.5 * (float(length) - float(gauge_length))
    x_end = x_start + float(gauge_length)
    candidates = []
    for x_pos in x_bounds:
        inside = (x_start - 1.0e-8) <= x_pos <= (x_end + 1.0e-8)
        if not inside:
            continue
        if not include_ends and (abs(x_pos) <= 1.0e-8 or abs(x_pos - length) <= 1.0e-8):
            continue
        candidates.append(x_pos)
    return candidates


def uniform_sample(values, count):
    """Select ``count`` nearly uniformly spaced values from an ordered list."""
    if count <= 0 or not values:
        return []
    count = min(int(count), len(values))
    if count == 1:
        return [values[len(values) // 2]]
    result = []
    last_idx = -1
    for idx in range(count):
        value_idx = int(round(idx * (len(values) - 1) / float(count - 1)))
        if value_idx <= last_idx:
            value_idx = min(last_idx + 1, len(values) - 1)
        result.append(values[value_idx])
        last_idx = value_idx
    return result


def crack_edge_find_points(crack_x_positions, layup, n_cells_thickness):
    """Return one findAt point per vertical edge segment through every 90 ply.

    A vertical crack path is split by horizontal ply/subcell partitions.  Abaqus
    ``edges.findAt`` needs a point on each segment; using only the ply midpoint
    selects only one segment and leaves the crack set partially through-thickness.
    """
    points = []
    for x_pos in crack_x_positions:
        for _ply_idx, _angle, y_min, y_max in ply_ranges(layup, 90):
            dy = (y_max - y_min) / float(n_cells_thickness)
            for row_idx in range(int(n_cells_thickness)):
                y_mid = y_min + (row_idx + 0.5) * dy
                points.append(((x_pos, y_mid, 0.0),))
    return points


def coverage_percent(selected_segments, expected_segments):
    if expected_segments <= 0:
        return 100.0
    return 100.0 * float(selected_segments) / float(expected_segments)

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from laminate_partitioning_core import (  # noqa: E402
    build_layup,
    crack_count_from_density,
    crack_count_from_physical_density,
    crack_edge_find_points,
    coverage_percent,
    gauge_candidate_boundaries,
    partition_x_bounds,
    uniform_sample,
)


def test_normalized_crack_density_formula_uses_division_by_gauge_length():
    count, raw = crack_count_from_density(140.0, 0.5, 70.0, minimum=1)
    assert raw == 1.0
    assert count == 1


def test_physical_density_formula_is_separate_from_normalized_density():
    count, raw = crack_count_from_physical_density(0.5, 70.0)
    assert raw == 35.0
    assert count == 35


def test_crack_edge_points_cover_every_90_ply_subcell_segment():
    layup = build_layup('symmetric', 1, 0.25, 0.25)
    points = crack_edge_find_points([10.0, 20.0], layup, 5)
    assert len(points) == 2 * 2 * 5
    y_values = [pt[0][1] for pt in points]
    assert min(y_values) > 0.25
    assert max(y_values) < 0.75
    assert coverage_percent(len(points), 20) == 100.0


def test_candidates_are_internal_gauge_partition_boundaries():
    bounds = partition_x_bounds(80.0, 5.0)
    candidates = gauge_candidate_boundaries(bounds, 80.0, 70.0, include_ends=False)
    assert candidates[0] == 5.0
    assert candidates[-1] == 75.0
    assert 0.0 not in candidates and 80.0 not in candidates
    assert uniform_sample(candidates, 3) == [5.0, 40.0, 75.0]

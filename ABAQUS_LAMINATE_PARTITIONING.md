# Abaqus laminate partitioning workflow

This repository now separates the Abaqus-dependent model-building script from
pure-Python geometry planning helpers:

- `scripts/abaqus_laminate_partitioning.py` creates the Abaqus 2D shell,
  partitions it, creates material/ply sets, and creates the crack-path edge set.
- `scripts/laminate_partitioning_core.py` computes layup ranges, rectangular
  partition bounds, crack counts, crack positions, and full-thickness edge
  selection points without importing Abaqus.

## Modeling assumptions

- Coordinates are in mm.
- The model is a 2D X-Y section of a laminate.
- 90-degree plies are divided through thickness into `n_cells_thickness`
  rows. The x partition pitch is the same as the 90-ply row thickness so cells
  in the 90-degree plies remain rectangular/square and independent of crack
  density.
- Crack paths are sampled from existing internal vertical partition boundaries
  inside the centered gauge section.
- Every selected crack path is represented by one Abaqus edge segment per
  90-degree ply subcell. This is required because horizontal subcell partitions
  split a through-thickness crack line into multiple edge objects.

## Crack-density convention

The implemented default assumes the literature saturation value is a normalized
quantity:

```text
rho = N * L / t90
N   = rho * t90 / L
```

where `N` is the integer number of crack paths, `L` is gauge length, and `t90`
is the total modeled 90-degree thickness. This equation is dimensionless and is
not the same as using a physical lineal density in cracks/mm. If a true physical
crack density is supplied, use `N = rho_cracks_per_mm * L` instead.

The helper returns both the raw floating-point value and the rounded integer.
The Abaqus script uses nearest-integer rounding and enforces one crack only when
the raw value is positive but rounds to zero.

## Run

From Abaqus/CAE or noGUI:

```bash
abaqus cae noGUI=scripts/abaqus_laminate_partitioning.py
```

Expected diagnostics include:

```text
Number of cracks: ...
90 ply total thickness: ... mm
Crack positions: [...]
Crack-set thickness coverage = 100.0% (... / ... segments)
```

If coverage is below 100%, the most likely causes are a partition tolerance
mismatch, missing vertical partition at a requested crack x-coordinate, or an
unexpected Abaqus geometry merge/suppression.

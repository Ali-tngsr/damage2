# Workflow — Single-Script Pipeline

This document describes the consolidated workflow used to reproduce the paper's figures. All Abaqus scripts are Python 2.7 compatible. The pipeline is driven by one file (`abaqus_laminate_partitioning.py`) which runs in two modes: `build` and `resume`.

## Pipeline Stages

```
[Phase 1]  BUILD  (8 jobs)
    └── abaqus cae noGUI=scripts/abaqus_laminate_partitioning.py
        (for each ACTIVE_JOB)
    └── produces Model_<job>.cae for each of 8 jobs

[Phase 2]  Manual cohesive insertion  (8 jobs, in CAE GUI)
    └── Mesh → Edit → Insert cohesive seams → select Potential_Crack_Edges
    └── verify Section Controls (viscosity 1e-4, thickness 0.001)
    └── save .cae

[Phase 3]  RESUME  (8 jobs)
    └── abaqus cae noGUI=scripts/abaqus_laminate_partitioning.py
        (set run_mode = 'resume', for each ACTIVE_JOB)
    └── produces input file <job>.inp, ready to submit

[Phase 4]  SUBMIT  (8 jobs)
    └── abaqus job=<job_name> cpus=4 interactive

[Phase 5]  Post-process  (8 jobs)
    └── abaqus python scripts/postprocess_odb.py --odb <job>.odb

[Phase 6]  Plot figures
    └── python scripts/plot_figures.py --figures 5,9,10,11
```

## Phase 1 — Build

For each of the 8 jobs:

1. Open `scripts/abaqus_laminate_partitioning.py` in a text editor.
2. Set:
   ```python
   run_mode = 'build'
   ACTIVE_JOB = 'val_090s'   # change to next job for each iteration
   ```
3. Run:
   ```
   abaqus cae noGUI=scripts/abaqus_laminate_partitioning.py
   ```
4. Verify `Model_<job>.cae` was created (typically 5–60 seconds per job).

**What BUILD does (per job):**
- Stage 1: Create 2D planar geometry (rectangle `L × total_thickness`)
- Stage 2: Horizontal partitions (ply boundaries + 90° sub-cells) + vertical partitions (cohesive paths)
- Stage 3: Create face sets (`Ply_0_Set`, `Set_90deg_Vf_*`, `Potential_Crack_Edges`)
- Stage 4: Create continuum materials (orthotropic, with 90° swap) + sections + assignments
- Stage 4.5: Create cohesive material + section (with viscosity via Section Controls)
- Stage 5: Apply `MaterialOrientation` (GLOBAL, AXIS_3)
- Stage 6: Generate mesh (CPE4R or CPS4R)
- Stage 7: Save `.cae`

## Phase 2 — Manual cohesive insertion (in CAE)

For each `Model_<job>.cae`:

1. Open in CAE:
   ```
   abaqus cae database=Model_val_090s.cae
   ```
2. Switch to **Mesh module**.
3. Menu: `Mesh → Edit...` → Category: **Mesh** → Method: **Insert cohesive seams**.
4. Select the geometric part `Laminate_<job>` (not any other part).
5. Click **Sets...** → select `Potential_Crack_Edges` → Done.
6. Abaqus creates `CohesiveSeam-1-Elements` set with COH2D4 elements.
7. **Property module** → verify section assignment:
   - Section `Cohesive_Sec` is assigned to `CohesiveSeam-1-Elements`
   - Edit `Cohesive_Sec`:
     - Initial thickness: **Specify** → `0.001`
     - Element Controls → Viscosity: **Specify** → `1e-4`
8. Save (`Ctrl+S`) and close CAE.

## Phase 3 — Resume

For each of the 8 jobs:

1. Open `scripts/abaqus_laminate_partitioning.py` in a text editor.
2. Set:
   ```python
   run_mode = 'resume'
   ACTIVE_JOB = 'val_090s'   # match the job you just edited in CAE
   ```
3. Run:
   ```
   abaqus cae noGUI=scripts/abaqus_laminate_partitioning.py
   ```
4. Verify `<job>.inp` was created (typically 10–30 seconds per job).

**What RESUME does (per job):**
- Stage 11: Process `CohesiveSeam-1-Elements`:
  - Force element type to `COH2D4`
  - Assign `Cohesive_Sec` to the seam set
- Stage 12: Create assembly + static step + BCs + job:
  - Instance from `Laminate_<job>` part
  - `StaticStep(name='Step-1', nlgeom=ON, initialInc=0.005, maxNumInc=10000)`
  - Field output: `S, E, U, RF, SDEG, STATUS, DMICRT` (frequency=20)
  - BCs: `Fix_Left_X` (u1=0), `Fix_Bottom_Y` (u2=0), `Pull_Right_X` (u1=strain×L)
  - Job with `numCpus=4, numDomains=4`
- Save `.cae` again.

## Phase 4 — Submit

For each job:
```
abaqus job=val_090s cpus=4 interactive
```

Or submit from CAE's Job Manager.

**Time estimate (4 CPUs, SCALE_FACTOR=0.25):**
- Validation jobs (`val_*`): 5–15 min each
- Thin-ply jobs (`pt_t90_*`): 5–20 min each
- **Total for 8 jobs: ~1–2 hours**

**Time estimate (4 CPUs, SCALE_FACTOR=1.0):**
- 1–2 hours per job
- **Total for 8 jobs: ~8–16 hours**

## Phase 5 — Post-process

For each `.odb`:
```
abaqus python scripts/postprocess_odb.py --odb val_090s.odb --output results/val_090s_summary.csv
```

**Output CSV columns:**
- `frame, frame_value, strain_pct`
- `sigma90_volumetric_mpa` — volumetric-averaged σ_x in 90° ply
- `global_stress_mpa` — total reaction force / area
- `E90_normalized` — E90 / E90_initial (secant stiffness)
- `crack_count, damaged_elements`
- `normalized_crack_density` — crack_count / (rho × L)

**Robustness:** If an ODB is missing or fails to open, the script prints a warning and exits gracefully — it does not produce a partial CSV.

## Phase 6 — Plot figures

```
python scripts/plot_figures.py --results-dir results --output-dir figures --figures 5,9,10,11
```

**Robustness:** `plot_figures.py` will plot whatever data is available. If some CSVs are missing, it skips those jobs and plots the rest. Each figure is independent — if one fails, the others still render.

**Output PNGs:**
- `figures/figure_05_stress_strain.png`
- `figures/figure_09_ply_number.png`
- `figures/figure_10_ply_thickness.png`
- `figures/figure_11_crack_density.png`

## Configuration tips

### Scaling down for limited hardware

At the top of `abaqus_laminate_partitioning.py`:
```python
SCALE_FACTOR = 0.25   # 1.0 = paper, 0.5 = half, 0.25 = quarter
```
- `SCALE_FACTOR = 0.25` → `L = 20 mm`, ~5 min/job (good for testing)
- `SCALE_FACTOR = 1.0`   → `L = 80 mm`, ~1 hour/job (paper-matching)

### Increasing NUM_MATERIAL_SETS

```python
NUM_MATERIAL_SETS = 10   # try 7 (exact Table 1), 20, 50
```
Properties are interpolated linearly from Table 1's 7 anchor points.

### Calibrating cohesive parameters

If results don't match the paper:
```python
cohesive_fracture_energy = 0.4    # increase from 0.2 if cracks propagate too fast
cohesive_viscosity = 1.0e-3       # increase from 1e-4 if convergence fails
```

## Troubleshooting

- **`Lost connection to driverLM`** → License server dropped. Disable sleep, restart FLEXlm service.
- **`Too many attempts`** → Convergence issue. Increase `cohesive_viscosity` to `1e-3`.
- **`Zero stiffness element`** → Cohesive section missing `Initial thickness: Specify → 0.001`.
- **`CohesiveSeam-1-Elements not found`** in resume mode → You forgot Phase 2 (manual insertion in CAE).
- **`NameError: name 'L' is not defined`** → Make sure you have the latest `postprocess_odb.py` (post-fix).
